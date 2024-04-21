from ryu.base import app_manager 
from ryu.controller import ofp_event 
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER 
from ryu.controller.handler import set_ev_cls 
from ryu.ofproto import ofproto_v1_3 
from ryu.lib.packet import packet 
from ryu.lib.packet import ethernet 
class Switch(app_manager.RyuApp): 
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION] 
    def __init__(self, *args, **kwargs): 
        super(Switch, self).__init__(*args, **kwargs)
        # maybe you need a global data structure to save the mapping 
        
    def add_flow(self, datapath, priority, match, actions,idle_timeout=0,hard_timeout=0):
        dp = datapath 
        ofp = dp.ofproto 
        parser = dp.ofproto_parser 
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)] 
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, 
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
        						match=match,instructions=inst) 
        dp.send_msg(mod) 
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER) 
    def switch_features_handler(self, ev): 
        msg = ev.msg 
        dp = msg.datapath 
        ofp = dp.ofproto 
        parser = dp.ofproto_parser
        match = parser.OFPMatch() 
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,ofp.OFPCML_NO_BUFFER)] 
        self.add_flow(dp, 0, match, actions)
        
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER) 
    def packet_in_handler(self, ev): 
        msg = ev.msg 
        dp = msg.datapath 
        ofp = dp.ofproto 
        parser = dp.ofproto_parser 
        
        # the identity of switch 
        dpid = dp.id 
        self.mac_to_port.setdefault(dpid,{}) 
        # the port that receive the packet 
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data) 
        eth_pkt = pkt.get_protocol(ethernet.ethernet) 
        # get the mac 
        dst = eth_pkt.dst 
        src = eth_pkt.src 
        # we can use the logger to print some useful information 
        self.logger.info('packet: %s %s %s %s', dpid, src, dst, in_port)
        
        # you need to code here to avoid the direct flooding 
        # having fun 
        # :)