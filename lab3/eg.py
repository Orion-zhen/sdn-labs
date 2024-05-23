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

    def __init__(self, *args, **kwargs):
        super(Switch, self).__init__(*args, **kwargs)
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

        in_port = msg.match["in_port"]
        # get the source mac address
        eth_src = eth_pkt.src
        # learn a mac and port relation avoid FLOOD
        if eth_src not in self.mac_to_port[dpid].keys():
            self.mac_to_port[dpid][eth_src] = in_port

        # if is lldp call function to handle
        if isinstance(lldp_pkt, lldp.lldp):
            # print('handle a lldp packet {}'.format(lldp_pkt))
            self.handle_lldp(lldp_pkt, msg)

        # if is arp call function to handle
        if isinstance(arp_pkt, arp.arp):
            print(f"handle an arp packet {arp_pkt}")
            self.handle_arp(arp_pkt, msg)

        # if is ipv4 call function to handle
        if isinstance(ipv4_pkt, ipv4.ipv4):
            print(f"handle an ipv4 packet {ipv4_pkt}")
            print(f"eth_src is {eth_src} and eth_dst is {eth_pkt.dst}")
            self.handle_ipv4(ipv4_pkt, msg)

    @set_ev_cls(ofp_event.EventOFPEchoReply, MAIN_DISPATCHER)
    def echo_reply_handler(self, ev):
        # calcualte the echo delay for every datapath
        dpid = ev.msg.datapath.id
        now = time.time()
        self.echo_delay[dpid] = now - self.echo_start[dpid]
        # print('echo_delay is {}'.format(self.echo_delay))

    def handle_lldp(self, lldp_pkt, msg):
        dpid = msg.datapath.id
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
        except LLDPPacket.LLDPUnknownFormat as e:
            # This handler can receive all the packtes which can be
            # not-LLDP packet. Ignore it silently
            print("receive a lldp unkown format")
            return
        if self.switches is None:
            self.switches = lookup_service_brick("switches")
        # print('lldp switches {}'.format(self.switches))
        for port in self.switches.ports.keys():
            if src_dpid == port.dpid and src_port_no == port.port_no:
                self.lldp_delay[(src_dpid, dpid)] = self.switches.ports[port].delay
                # if src_dpid == 7 and dpid == 8:
                #     print(
                #         "lldp delay between 7 and 8 is{}".format(
                #             self.lldp_delay[(src_dpid, dpid)]
                #         )
                #     )

    def handle_arp(self, arp_pkt, msg):
        out_port = None
        eth_dst = None
        dpid = msg.datapath.id
        ofp = msg.datapath.ofproto
        parser = msg.datapath.ofproto_parser
        in_port = msg.match["in_port"]

        # determin if a switch-host link
        host = True
        for tmp in self.switch_switch[dpid].keys():
            if in_port == self.switch_switch[dpid][tmp]:
                host = False
                break

        if host:
            arp_src_ip = arp_pkt.src_ip
            self.switch_host[dpid][arp_src_ip] = in_port

        if arp_pkt.opcode == arp.ARP_REQUEST:
            arp_dst_ip = arp_pkt.dst_ip
            arp_src_mac = arp_pkt.src_mac

            if arp_src_mac not in self.arp_in_port[dpid].keys():
                self.arp_in_port[dpid].setdefault(arp_src_mac, {})
                self.arp_in_port[dpid][arp_src_mac][arp_dst_ip] = in_port
            else:
                if arp_dst_ip not in self.arp_in_port[dpid][arp_src_mac].keys():
                    self.arp_in_port[dpid][arp_src_mac][arp_dst_ip] = in_port
                else:
                    if in_port != self.arp_in_port[dpid][arp_src_mac][arp_dst_ip]:
                        print("Drop an arp request to avoid loop storm.")
                        return

            out_port = ofp.OFPP_FLOOD

        else:
            pkt = packet.Packet(msg.data)
            eth_pkt = pkt.get_protocol(ethernet.ethernet)
            eth_dst = eth_pkt.dst

            if eth_dst in self.mac_to_port[dpid].keys():
                out_port = self.mac_to_port[dpid][eth_dst]
            else:
                out_port = ofp.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst)
            self.add_flow(msg.datapath, 10, match, actions, 90, 180)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
            out = parser.OFPPacketOut(
                datapath=msg.datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data,
            )
            msg.datapath.send_msg(out)

    def handle_ipv4(self, ipv4_pkt, msg):
        ofp = msg.datapath.ofproto
        parser = msg.datapath.ofproto_parser

        ipv4_src = ipv4_pkt.src
        ipv4_dst = ipv4_pkt.dst

        dpid_begin = None
        dpid_final = None
        port_begin = None
        port_final = None

        find_begin = False
        for dpid in self.switch_host.keys():
            for ip in self.switch_host[dpid].keys():
                if ip == ipv4_src:
                    port_begin = self.switch_host[dpid][ip]
                    dpid_begin = dpid
                    find_begin = True
                    break
            if find_begin:
                break

        find_final = False
        for dpid in self.switch_host.keys():
            for ip in self.switch_host[dpid].keys():
                if ip == ipv4_dst:
                    port_final = self.switch_host[dpid][ip]
                    dpid_final = dpid
                    find_final = True
                    break
            if find_final:
                break

        short_path = nx.dijkstra_path(self.topo_map, dpid_begin, dpid_final)
        min_delay = nx.dijkstra_path_length(self.topo_map, dpid_begin, dpid_final)
        print(f"Fastest path found: {short_path}, delay is {min_delay * 1000}")

        path = str(ipv4_src) + " -> " + str(port_begin) + ":s" + str(dpid_begin)

        for i in range(0, len(short_path)):
            cur_switch = short_path[i]
            if i == 0:
                next_switch = short_path[i + 1]
                port = self.switch_switch[cur_switch][next_switch]
                path = path + ":" + str(port) + " -> "

                # backwrd
                out_port = port_begin
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_dst, ipv4_dst=ipv4_src
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

                # forward
                out_port = self.switch_switch[cur_switch][next_switch]
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_src, ipv4_dst=ipv4_dst
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

            elif i == len(short_path) - 1:
                pre_switch = short_path[i - 1]
                port = self.switch_switch[cur_switch][pre_switch]
                path = path + str(port) + ":" + str(cur_switch)

                # backward
                out_port = port
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_dst, ipv4_dst=ipv4_src
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

                # forward
                out_port = port_final
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_src, ipv4_dst=ipv4_dst
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

            else:
                pre_switch = short_path[i - 1]
                next_switch = short_path[i + 1]
                port1 = self.switch_switch[cur_switch][pre_switch]
                port2 = self.switch_switch[cur_switch][next_switch]
                path = (
                    path
                    + str(port1)
                    + ":"
                    + str(cur_switch)
                    + ":"
                    + str(port2)
                    + " -> "
                )

                # backward
                out_port = port1
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_dst, ipv4_dst=ipv4_src
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

                # forward
                out_port = port2
                actions = [parser.OFPActionOutput(out_port)]
                match = parser.OFPMatch(
                    eth_type=0x800, ipv4_src=ipv4_src, ipv4_dst=ipv4_dst
                )
                self.add_flow(self.datapath[cur_switch], 20, match, actions, 300, 600)

        path = path + ":" + str(port_final) + " -> " + str(ipv4_dst)
        print(path)

        out_port = self.switch_switch[short_path[0]][short_path[1]]
        actions = [parser.OFPActionOutput(out_port)]
        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(
            datapath=msg.datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=actions,
            data=data,
        )
        msg.datapath.send_msg(out)

    def get_topology(self):
        while True:
            switch_list = get_switch(self)
            for switch in switch_list:
                self.switch_switch.setdefault(switch.dp.id, {})
            link_list = get_link(self)
            for link in link_list:
                self.switch_switch[link.src.dpid][link.dst.dpid] = link.src.port_no
                self.topo_map.add_edge(link.src.dpid, link.dst.dpid)

            hub.sleep(GET_TOPOLOGY_INTERVAL)

    def send_echo_request(self):
        while True:
            for dp in self.datapath.values():
                data = None
                parser = dp.ofproto_parser
                req = parser.OFPEchoRequest(dp, data)
                dp.send_msg(req)

                self.echo_start[dp.id] = time.time()

            hub.sleep(SEND_ECHO_REQUEST_INTERVAL)

    def get_delay(self):
        while True:
            for edge in self.topo_map.edges:
                weight = (
                    self.lldp_delay[(edge[0], edge[1])]
                    + self.lldp_delay[(edge[1], edge[0])]
                    - self.echo_delay[edge[0]]
                    - self.echo_delay[edge[1]]
                ) / 2

                if weight < 0:
                    weight = 0

                self.topo_map[edge[0]][edge[1]]["weight"] = weight

            print("get delay thread done!")
            hub.sleep(GET_DELAY_INTERVAL)
