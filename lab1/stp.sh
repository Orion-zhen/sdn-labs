#!/bin/bash
sudo ovs-vsctl set bridge edge1_1 stp_enable=true
sudo ovs-vsctl set bridge edge1_2 stp_enable=true
sudo ovs-vsctl set bridge edge2_1 stp_enable=true
sudo ovs-vsctl set bridge edge2_2 stp_enable=true
sudo ovs-vsctl set bridge edge3_1 stp_enable=true
sudo ovs-vsctl set bridge edge3_2 stp_enable=true
sudo ovs-vsctl set bridge edge4_1 stp_enable=true
sudo ovs-vsctl set bridge edge4_2 stp_enable=true
sudo ovs-vsctl set bridge aggr1_1 stp_enable=true
sudo ovs-vsctl set bridge aggr1_2 stp_enable=true
sudo ovs-vsctl set bridge aggr2_1 stp_enable=true
sudo ovs-vsctl set bridge aggr2_2 stp_enable=true
sudo ovs-vsctl set bridge aggr3_1 stp_enable=true
sudo ovs-vsctl set bridge aggr3_2 stp_enable=true
sudo ovs-vsctl set bridge aggr4_1 stp_enable=true
sudo ovs-vsctl set bridge aggr4_2 stp_enable=true
sudo ovs-vsctl set bridge core1 stp_enable=true
sudo ovs-vsctl set bridge core2 stp_enable=true
sudo ovs-vsctl set bridge core3 stp_enable=true
sudo ovs-vsctl set bridge core4 stp_enable=true
sudo ovs-vsctl del-fail-mode edge1_1
sudo ovs-vsctl del-fail-mode edge1_2
sudo ovs-vsctl del-fail-mode edge2_1
sudo ovs-vsctl del-fail-mode edge2_2
sudo ovs-vsctl del-fail-mode edge3_1
sudo ovs-vsctl del-fail-mode edge3_2
sudo ovs-vsctl del-fail-mode edge4_1
sudo ovs-vsctl del-fail-mode edge4_2
sudo ovs-vsctl del-fail-mode aggr1_1
sudo ovs-vsctl del-fail-mode aggr1_2
sudo ovs-vsctl del-fail-mode aggr2_1
sudo ovs-vsctl del-fail-mode aggr2_2
sudo ovs-vsctl del-fail-mode aggr3_1
sudo ovs-vsctl del-fail-mode aggr3_2
sudo ovs-vsctl del-fail-mode aggr4_1
sudo ovs-vsctl del-fail-mode aggr4_2
sudo ovs-vsctl del-fail-mode core1
sudo ovs-vsctl del-fail-mode core2
sudo ovs-vsctl del-fail-mode core3
sudo ovs-vsctl del-fail-mode core4
