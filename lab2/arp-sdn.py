# type: ignore
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp
from ryu.lib.packet import ether_types
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import networkx as nx

ETHERNET = ethernet.ethernet.__name__
ETHERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
ARP = arp.arp.__name__


class Switch_Dict(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Switch_Dict, self).__init__(*args, **kwargs)
        # links between switches and hosts
        # switch_id -> {host_ip -> host_mac}
        self.switch_to_host = {}
        # links between switches
        # switch_id -> {switch_id -> out_port}
        self.switch_to_switch = {}
        # switch entities
        self.dp = {}
        # an api to get the topo of switches
        self.topo_api = self
        # the topo graph
        self.G = nx.Graph()

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
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        # the identity of switch
        dpid = dp.id
        self.dp[dpid] = dp

        self.switch_to_host.setdefault(dpid, {})

        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)

        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        if eth_pkt.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        if eth_pkt.ethertype == ether_types.ETH_TYPE_IPV6:
            return

        # get the mac
        eth_dst = eth_pkt.dst
        eth_src = eth_pkt.src

        arp_pkt = pkt.get_protocol(arp.arp)
        # deal with arp request
        if arp_pkt and arp_pkt.opcode == arp.ARP_REQUEST:
            arp_src_ip = arp_pkt.src_ip
            arp_src_mac = arp_pkt.src_mac

            arp_dst_ip = arp_pkt.dst_ip

            # the switch knows the mac
            if arp_src_ip in self.switch_to_host[dpid]:
                # construct an arp reply
                reply_eth_dst = None
                # traverse to find the corresponding mac
                for switch in self.switch_to_host:
                    if arp_dst_ip in self.switch_to_host[switch]:
                        reply_eth_dst = self.switch_to_host[switch][arp_dst_ip]["mac"]
                        break
                if reply_eth_dst == None:
                    print(f"No MAC address found for IP {arp_dst_ip}")
                    return

                arp_reply = packet.Packet()
                # ethernet protocol
                arp_reply.add_protocol(
                    ethernet.ethernet(
                        ethertype=eth_pkt.ethertype,
                        dst=eth_src,
                        src=reply_eth_dst,
                    )
                )
                # arp protocol
                arp_reply.add_protocol(
                    arp.arp(
                        opcode=arp.ARP_REPLY,
                        src_mac=reply_eth_dst,
                        src_ip=arp_dst_ip,
                        dst_mac=arp_src_mac,
                        dst_ip=arp_src_ip,
                    )
                )
                # serialize an object to raw binary string
                arp_reply.serialize()
                actions = [parser.OFPActionOutput(in_port)]
                out = parser.OFPPacketOut(
                    datapath=dp,
                    buffer_id=ofp.OFP_NO_BUFFER,
                    in_port=ofp.OFPP_CONTROLLER,
                    actions=actions,
                    data=arp_reply.data,
                )
                dp.send_msg(out)
                print(f"ARP reply sent to {arp_src_ip}")
            # the switch doesn't know the mac
            else:
                self.switch_to_host[dpid].setdefault(arp_src_ip, {})
                self.switch_to_host[dpid][arp_src_ip]["mac"] = arp_src_mac
                self.switch_to_host[dpid][arp_src_ip]["port"] = in_port
                print(
                    f"SW[{dpid}] Learned to Host {arp_src_ip} | {arp_src_mac} @ port {in_port}"
                )
                # add a flow table entity
                actions = [parser.OFPActionOutput(in_port)]
                match = parser.OFPMatch(eth_dst=arp_src_mac)
                self.add_flow(dp, 10, match, actions)
            return

        # deal with others
        # find the last hop switch to the target host
        dst_dpid = None
        found = False
        for switch in self.switch_to_host:
            for host in self.switch_to_host[switch]:
                if eth_dst == self.switch_to_host[switch][host]["mac"]:
                    dst_dpid = switch
                    found = True
                    break
            if found:
                break

        # failed to find
        if dst_dpid == None:
            return

        shortest_path = nx.shortest_path(self.G, dpid, dst_dpid)
        print(f"[{dpid}] -> [{dst_dpid}] Shortest path: {shortest_path}")
        # configure flow table alongside the path
        for i in range(len(shortest_path) - 1):
            cur = shortest_path[i]
            next = shortest_path[i + 1]
            out_port = self.switch_to_switch[cur][next]

            actions = [parser.OFPActionOutput(out_port)]
            match = parser.OFPMatch(eth_dst=eth_dst)
            self.add_flow(self.dp[cur], 20, match, actions)
            print(f"Add flow to SW[{cur}]")

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        # send to next hop
        cur = shortest_path[0]
        next = shortest_path[1]
        out_port = self.switch_to_switch[cur][next]
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        dp.send_msg(out)

    @set_ev_cls(event.EventSwitchEnter)
    def get_topo(self, ev):
        # configure switches
        switch_list = get_switch(self.topo_api)
        node = []
        print("Switch List:")
        for sw in switch_list:
            node.append(sw.dp.id)
            # init switch links btw
            self.switch_to_switch.setdefault(sw.dp.id, {})
            print(sw.dp.id)
        self.G.add_nodes_from(node)

        # configure links
        link_list = get_link(self.topo_api)
        edge = []
        print("Link List:")
        for link in link_list:
            src = link.src.dpid
            dst = link.dst.dpid
            edge.append((src, dst))
            self.switch_to_switch[src][dst] = link.src.port_no
            self.switch_to_switch[dst][src] = link.dst.port_no
            print(f"{src} -> {dst}")
        self.G.add_edges_from(edge)
