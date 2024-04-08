from mininet.node import Controller, OVSSwitch
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.cli import CLI
import os


class FatTree(Topo):
    def __init__(self, *args, **params):
        super().__init__(*args, **params)

    def build(self):
        # Pod1
        h1_1 = self.addHost("h1_1")
        h1_2 = self.addHost("h1_2")
        edge1_1 = self.addSwitch("edge1_1")
        self.addLink(h1_1, edge1_1)
        self.addLink(h1_2, edge1_1)
        h1_3 = self.addHost("h1_3")
        h1_4 = self.addHost("h1_4")
        edge1_2 = self.addSwitch("edge1_2")
        self.addLink(h1_3, edge1_2)
        self.addLink(h1_4, edge1_2)
        aggr1_1 = self.addSwitch("aggr1_1")
        aggr1_2 = self.addSwitch("aggr1_2")
        self.addLink(edge1_1, aggr1_1)
        self.addLink(edge1_2, aggr1_1)
        self.addLink(edge1_1, aggr1_2)
        self.addLink(edge1_2, aggr1_2)

        # Pod2
        h2_1 = self.addHost("h2_1")
        h2_2 = self.addHost("h2_2")
        edge2_1 = self.addSwitch("edge2_1")
        self.addLink(h2_1, edge2_1)
        self.addLink(h2_2, edge2_1)
        h2_3 = self.addHost("h2_3")
        h2_4 = self.addHost("h2_4")
        edge2_2 = self.addSwitch("edge2_2")
        self.addLink(h2_3, edge2_2)
        self.addLink(h2_4, edge2_2)
        aggr2_1 = self.addSwitch("aggr2_1")
        aggr2_2 = self.addSwitch("aggr2_2")
        self.addLink(edge2_1, aggr2_1)
        self.addLink(edge2_2, aggr2_1)
        self.addLink(edge2_1, aggr2_2)
        self.addLink(edge2_2, aggr2_2)

        # Pod3
        h3_1 = self.addHost("h3_1")
        h3_2 = self.addHost("h3_2")
        edge3_1 = self.addSwitch("edge3_1")
        self.addLink(h3_1, edge3_1)
        self.addLink(h3_2, edge3_1)
        h3_3 = self.addHost("h3_3")
        h3_4 = self.addHost("h3_4")
        edge3_2 = self.addSwitch("edge3_2")
        self.addLink(h3_3, edge3_2)
        self.addLink(h3_4, edge3_2)
        aggr3_1 = self.addSwitch("aggr3_1")
        aggr3_2 = self.addSwitch("aggr3_2")
        self.addLink(edge3_1, aggr3_1)
        self.addLink(edge3_2, aggr3_1)
        self.addLink(edge3_1, aggr3_2)
        self.addLink(edge3_2, aggr3_2)

        # Pod4
        h4_1 = self.addHost("h4_1")
        h4_2 = self.addHost("h4_2")
        edge4_1 = self.addSwitch("edge4_1")
        self.addLink(h4_1, edge4_1)
        self.addLink(h4_2, edge4_1)
        h4_3 = self.addHost("h4_3")
        h4_4 = self.addHost("h4_4")
        edge4_2 = self.addSwitch("edge4_2")
        self.addLink(h4_3, edge4_2)
        self.addLink(h4_4, edge4_2)
        aggr4_1 = self.addSwitch("aggr4_1")
        aggr4_2 = self.addSwitch("aggr4_2")
        self.addLink(edge4_1, aggr4_1)
        self.addLink(edge4_2, aggr4_1)
        self.addLink(edge4_1, aggr4_2)
        self.addLink(edge4_2, aggr4_2)

        # Core
        core1 = self.addSwitch("core1")
        core2 = self.addSwitch("core2")
        core3 = self.addSwitch("core3")
        core4 = self.addSwitch("core4")

        self.addLink(aggr1_1, core1)
        self.addLink(aggr1_1, core2)
        self.addLink(aggr1_2, core3)
        self.addLink(aggr1_2, core4)

        self.addLink(aggr2_1, core1)
        self.addLink(aggr2_1, core2)
        self.addLink(aggr2_2, core3)
        self.addLink(aggr2_2, core4)

        self.addLink(aggr3_1, core1)
        self.addLink(aggr3_1, core2)
        self.addLink(aggr3_2, core3)
        self.addLink(aggr3_2, core4)

        self.addLink(aggr4_1, core1)
        self.addLink(aggr4_1, core2)
        self.addLink(aggr4_2, core3)
        self.addLink(aggr4_2, core4)


def main():
    setLogLevel("info")
    topo = FatTree()

    net = Mininet(topo=topo, controller=Controller, switch=OVSSwitch)
    net.start()

    # aggr1_1 = net.get('aggr1_1')
    # for port in aggr1_1.intfList():
    #     print(port.link)

    # configuring static flow table
    # generally speaking, port 1&2 are south ports, while port3&4 are north ports
    # edge switch upward flows
    os.system("ovs-ofctl add-flow edge1_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge1_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge1_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge1_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge2_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge2_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge2_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge2_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge3_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge3_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge3_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge3_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge4_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge4_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow edge4_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow edge4_2 in_port=2,actions=output:1,output:3,output:4")
    # edge switch downward flows
    os.system("ovs-ofctl add-flow edge1_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge1_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge1_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge1_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge2_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge2_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge2_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge2_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge3_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge3_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge3_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge3_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge4_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge4_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge4_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow edge4_2 in_port=4,actions=output:1,output:2")
    # aggr switch upward flows
    os.system("ovs-ofctl add-flow aggr1_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr1_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr1_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr1_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr2_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr2_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr2_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr2_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr3_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr3_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr3_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr3_2 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr4_1 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr4_1 in_port=2,actions=output:1,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr4_2 in_port=1,actions=output:2,output:3,output:4")
    os.system("ovs-ofctl add-flow aggr4_2 in_port=2,actions=output:1,output:3,output:4")
    # aggr switch downward flows
    os.system("ovs-ofctl add-flow aggr1_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr1_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr1_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr1_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr2_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr2_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr2_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr2_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr3_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr3_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr3_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr3_2 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr4_1 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr4_1 in_port=4,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr4_2 in_port=3,actions=output:1,output:2")
    os.system("ovs-ofctl add-flow aggr4_2 in_port=4,actions=output:1,output:2")
    # for core switches, there is no upward flow, just flood!

    # os.system('ovs-ofctl dump-flows edge1_1')
    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
