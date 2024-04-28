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

ETHERNET = ethernet.ethernet.__name__
ETHERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
ARP = arp.arp.__name__


class Switch_Dict(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Switch_Dict, self).__init__(*args, **kwargs)
        # (dpid, src_mac, dst_ip)=>in_port, you may use it in mission 2
        self.arp_in_port = {}
        # maybe you need a global data structure to save the mapping
        # just data structure in mission 1
        self.mac_to_port = {}

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
        self.mac_to_port.setdefault(dpid, {})
        # dpid, src_mac, dst_ip -> in_port
        self.arp_in_port.setdefault(dpid, {})

        # the port that receive the packet
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

        # self.logger.info(
        #     "Pkt-in: SW(%s) Src(%s) Dst(%s) InPort(%s)", dpid, eth_src, eth_dst, in_port
        # )

        # get protocols
        header_list = dict(
            (p.protocol_name, p) for p in pkt.protocols if type(p) != str
        )
        if eth_dst == ETHERNET_MULTICAST and ARP in header_list:
            # you need to code here to avoid broadcast loop to finish mission 2
            arp_pkt = pkt.get_protocol(arp.arp)

            # ARP request packet
            if arp_pkt.opcode == arp.ARP_REQUEST:
                req_dst_ip = arp_pkt.dst_ip
                arp_src_mac = arp_pkt.src_mac

                # learned the mac in mapping
                if arp_src_mac in self.arp_in_port[dpid]:
                    # learned the ip in mapping
                    if req_dst_ip in self.arp_in_port[dpid][arp_src_mac]:
                        # different in_port, just drop
                        if in_port != self.arp_in_port[dpid][arp_src_mac][req_dst_ip]:
                            match = parser.OFPMatch(
                                in_port=in_port,
                                arp_op=arp.ARP_REQUEST,
                                arp_tpa=req_dst_ip,
                                arp_sha=arp_src_mac,
                            )
                            actions = []
                            # higher than self-learning
                            self.add_flow(dp, 20, match, actions)

                            # debug message
                            print(
                                f"SW[{dpid}] packet in port {in_port}, but should be {self.arp_in_port[dpid][arp_src_mac][req_dst_ip]}. DROP"
                            )

                            out = parser.OFPPacketOut(
                                datapath=dp,
                                buffer_id=msg.buffer_id,
                                in_port=in_port,
                                actions=[],
                                data=None,
                            )
                            dp.send_msg(out)
                            return

                    # no req_dst_ip in mapping
                    else:
                        # learn the req_dst_ip and in_port
                        self.arp_in_port[dpid][arp_src_mac].setdefault(req_dst_ip, {})
                        self.arp_in_port[dpid][arp_src_mac][req_dst_ip] = in_port
                # no arp_src_mac in mapping
                else:
                    self.arp_in_port[dpid].setdefault(arp_src_mac, {})
                    self.arp_in_port[dpid][arp_src_mac][req_dst_ip] = in_port

        # self-learning
        # you need to code here to avoid the direct flooding
        # having fun
        # :)
        # just code in mission 1
        self.mac_to_port[dpid][eth_src] = in_port
        if eth_dst in self.mac_to_port[dpid]:
            # have learned the mac-port mapping
            out_port = self.mac_to_port[dpid][eth_dst]
        else:
            # no, just flood
            out_port = ofp.OFPP_FLOOD
        # output the packet
        actions = [parser.OFPActionOutput(out_port)]

        # if learned a new mapping, add the flow table to switch
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst)
            # set priority to 10 to avoid flow table shadowing
            self.add_flow(dp, 10, match, actions)

        data = None
        # for flow tables, in-time send is necessary
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
