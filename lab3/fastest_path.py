from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, lldp
from ryu.base.app_manager import lookup_service_brick
from ryu.topology.api import get_switch, get_link
from ryu.topology.switches import LLDPPacket
from ryu.lib import hub
import networkx as nx
import time

GET_TOPOLOGY_INTERVAL = 4
SEND_ECHO_REQUEST_INTERVAL = 0.1
GET_DELAY_INTERVAL = 4


class Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)

        self.mac_to_port = {}
        self.arp_in_port = {}

        self.topo_map = nx.Graph()

        # link between switches
        # switch_switch[dpid][linked_dpid] = port
        self.switch_switch = {}

        # link between host and switch
        # switch_host[dpid][host_ip] = port
        self.switch_host = {}

        # datapath[dpid] = datapath
        self.datapath = {}

        # remain uninitialized until lldp_handler called
        # all switches for lookup_service_brick()
        self.switches = None

        # lldp_delay[(dpid, linked_dpid)] = seconds
        self.lldp_delay = {}

        # echo_delay[dpid] = seconds
        self.echo_delay = {}

        # echo_start[dpid] = timestamp
        self.echo_start = {}

        # shortest_paths[(start, end)] = [sw1, sw2, ...]
        self.shortest_paths = {}

        self.topo_thread = hub.spawn(self.get_topology)
        self.delay_thread = hub.spawn(self.get_delay)
        self.echo_thread = hub.spawn(self.send_echo_request)

    def add_flow(
        self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0
    ):
        dp = datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            match=match,
            instructions=inst,
        )
        dp.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        # record the datapath
        self.datapath[dpid] = dp
        # init for self learning
        self.mac_to_port.setdefault(dpid, {})
        # init to avoid arp storm
        self.arp_in_port.setdefault(dpid, {})
        self.switch_host.setdefault(dpid, {})

        pkt = packet.Packet(msg.data)
        # try to get different protocols
        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        lldp_pkt = pkt.get_protocol(lldp.lldp)
        arp_pkt = pkt.get_protocol(arp.arp)
        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)

        # self learning
        in_port = msg.match["in_port"]
        eth_src = eth_pkt.src
        if eth_src not in self.mac_to_port[dpid]:
            self.mac_to_port[dpid][eth_src] = in_port

        if lldp_pkt is not None:
            self.lldp_handler(lldp_pkt, msg)

        if arp_pkt is not None:
            self.arp_handler(arp_pkt, msg)

        if ipv4_pkt is not None:
            self.ipv4_handler(ipv4_pkt, msg)

    def lldp_handler(self, lldp_pkt, msg):
        dp = msg.datapath
        dpid = dp.id
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
        except LLDPPacket.LLDPUnknownFormat:
            print(f"encountered unknown format of LLDP packet")
            return

        if self.switches is None:
            self.switches = lookup_service_brick("switches")

        for port in self.switches.port:
            if src_dpid == port.dpid and src_port_no == port.port_no:
                self.lldp_delay[(src_dpid, dpid)] = self.switches.ports[port].delay

    def arp_handler(self, arp_pkt, msg):
        dp = msg.datapath
        dpid = dp.id
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        in_port = msg.match["in_port"]

        # determin if a switch-host link
        is_host = True
        for tmp in self.switch_switch[dpid]:
            if in_port == self.switch_switch[dpid][tmp]:
                is_host = False
                break
        if is_host:
            arp_src_ip = arp_pkt.src_ip
            self.switch_host[dpid][arp_src_ip] = in_port

        if arp_pkt.opcode == arp.ARP_REQUEST:
            arp_dst_ip = arp_pkt.dst_ip
            arp_src_mac = arp_pkt.src_mac

            if arp_src_mac not in self.arp_in_port[dpid]:
                self.arp_in_port[dpid].setdfault(arp_src_mac, {})
                self.arp_in_port[dpid][arp_src_mac][arp_dst_ip] = in_port
            elif arp_dst_ip not in self.arp_in_port[dpid][arp_src_mac]:
                self.arp_in_port[dpid][arp_src_mac][arp_dst_ip] = in_port
            else:
                print(
                    f"SW[{dpid}] packet in port {in_port}, but should be {self.arp_in_port[dpid][arp_src_mac][arp_dst_ip]}. DROP"
                )
                return
            out_port = ofp.OFPP_FLOOD

        else:
            pkt = packet.Packet(msg.data)
            eth_pkt = pkt.get_protocol(ethernet.ethernet)
            eth_dst = eth_pkt.dst

            if eth_dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][eth_dst]
            else:
                out_port = ofp.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=ofp.OFPP_ANY, eth_dst=eth_dst)
            self.add_flow(dp, 10, match, actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        dp.send_msg(out)

    def ipv4_handler(self, ipv4_pkt, msg):
        pass

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        ofp = dp.ofproto
        desc = msg.desc
        port_no = desc.port_no
        state = desc.state

        if msg.reason == ofp.OFPPR_ADD:
            reson = "ADD"
        elif msg.reason == ofp.OFPPR_DELETE:
            reson = "DELETE"
        elif msg.reason == ofp.OFPPR_MODIFY:
            reson = "MODIFY"
            if state == ofp.OFPSPS_LINK_DOWN:
                # if port is down, remove the link
                linked_switch = None
                for switch in self.switch_switch[dpid]:
                    if self.switch_switch[dpid][switch] == port_no:
                        linked_switch = switch
                        break
                try:
                    self.topo_map.remove_edge(dpid, linked_switch)
                except:
                    print(f"{dpid} port {port_no} is already down")
                print(f"{dpid} port {port_no} is down")

                # delete flow entry
                for ip, path in self.shortest_paths.items():
                    if dpid in path and linked_switch in path:
                        self.delete_flow_entry(path, ip[0], ip[1])
            elif state == ofp.OFPSPS_LIVE:
                # if port is up, update the link
                for ip_src, ip_dst in self.shortest_paths.keys():
                    dpid_begin = None
                    dpid_final = None
                    find_begin = False
                    for dpid in self.switch_host:
                        for ip in self.switch_host[dpid]:
                            if ip == ip_src:
                                dpid_begin = dpid
                                find_begin = True
                                break
                        if find_begin:
                            break
                    find_final = False
                    for dpid in self.switch_host:
                        for ip in self.switch_host[dpid]:
                            if ip == ip_dst:
                                dpid_final = dpid
                                find_final = True
                                break
                        if find_final:
                            break

                    new_path = nx.dijkstra_path(self.topo_map, dpid_begin, dpid_final)
                    old_path = self.shortest_paths[(ip_src, ip_dst)]
                    if new_path != old_path:
                        print("update a path")
                        self.delete_flow_entry(old_path, ip_src, ip_dst)
        else:
            reson = "UNKNOWN"

        print(f"{dpid} port {port_no} is {reson}")

    @set_ev_cls(ofp_event.EventOFPEchoReply, MAIN_DISPATCHER)
    def echo_reply_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        # record the delay
        self.echo_delay[dpid] = time.time() - self.echo_start[dpid]
        print(f"echo delay is {self.echo_delay}")

    def get_topology(self):
        # peridically get topology
        while True:
            # get all switches
            switches = get_switch(self)
            for switch in switches:
                self.switch_switch.setdefault(switch.dp.id, {})
            # get all links
            links = get_link(self)
            for link in links:
                self.switch_switch[link.src.dpid][link.dst.dpid] = link.src.port_no
                self.topo_map.add_edge(link.src.dpid, link.dst.dpid)
            print(self.topo_map.edges)
            # sleep
            hub.sleep(GET_TOPOLOGY_INTERVAL)

    def get_delay(self):
        # periodically get delay
        while True:
            for edge in self.topo_map.edges:
                # calculate the link delay
                weight = (
                    self.lldp_delay[(edge[0], edge[1])]
                    + self.lldp_delay[(edge[1], edge[0])]
                    - self.echo_delay[edge[0]]
                    - self.echo_delay[edge[1]]
                )
                weight /= 2.0
                if weight < 0.0:
                    weight = 0.0

                # G[src][dst]["weight"] = weight
                self.topo_map[edge[0]][edge[1]]["weight"] = weight

            # sleep
            hub.sleep(GET_DELAY_INTERVAL)

    def send_echo_request(self):
        # periodically send echo request
        while True:
            # send echo request to each dp and record start time
            for dpid in self.datapath:
                data = None
                dp = self.datapath[dpid]
                parser = dp.ofproto_parser
                req = parser.OFPEchoRequest(dp, data)
                dp.send_msg(req)

                self.echo_start[dpid] = time.time()

            # sleep
            hub.sleep(SEND_ECHO_REQUEST_INTERVAL)

    def delete_flow_entry(self, path, src_ip, dst_ip):
        print(f"Removing flow entry from {path[0]} to {path[-1]}")
        # reset to rebuild mac2port and arpinport
        self.mac_to_port.clear()
        self.arp_in_port.clear()

        # delete all flow entries
        for dpid in path:
            dp = self.datapath[dpid]
            parser = dp.ofproto_parser
            ofp = dp.ofproto

            # one side
            match = parser.OFPMatch(
                eth_type=0x0800,  # ipv4 only
                ipv4_src=src_ip,
                ipv4_dst=dst_ip,
            )

            mod = parser.OFPFFlowMod(
                datapath=dp,
                cookie=0,
                cookie_msask=0,
                table_id=0,
                command=ofp.OFPFC_DELETE,
                idle_timeout=0,
                priority=1,
                buffer_id=ofp.OFPCML_NO_BUFFER,
                out_port=ofp.OFPP_ANY,
                out_group=ofp.OFPG_ANY,
                flags=0,
                match=match,
                instructions=[],
            )
            dp.send_msg(mod)

            # reverse side
            match = parser.OFPMatch(
                eth_type=0x0800,  # ipv4 only
                ipv4_src=dst_ip,
                ipv4_dst=src_ip,
            )

            mod = parser.OFPFFlowMod(
                datapath=dp,
                cookie=0,
                cookie_msask=0,
                table_id=0,
                command=ofp.OFPFC_DELETE,
                idle_timeout=0,
                priority=1,
                buffer_id=ofp.OFPCML_NO_BUFFER,
                out_port=ofp.OFPP_ANY,
                out_group=ofp.OFPG_ANY,
                flags=0,
                match=match,
                instructions=[],
            )
            dp.send_msg(mod)

        # reset all to avoid strange behavior
        for dpid in self.datapath:
            dp = self.datapath[dpid]
            parser = dp.ofproto_parser
            ofp = dp.ofproto

            match = parser.OFPMatch(in_port=ofp.OFPP_ANY)
            mod = parser.OFPFlowMod(
                datapath=dp,
                cookie=0,
                cookie_mask=0,
                table_id=0,
                command=ofp.OFPFC_DELETE,
                idle_timeout=0,
                hard_timeout=0,
                priority=10,
                flags=0,
                buffer_id=ofp.OFPCML_NO_BUFFER,
                match=match,
                instructions=[],
            )
            dp.send_msg(mod)
