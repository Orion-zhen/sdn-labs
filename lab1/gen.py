with open("./stp.sh", "w") as f:
    f.write("#!/bin/bash\n")
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl set bridge edge{i}_{j} stp_enable=true\n")
    
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl set bridge aggr{i}_{j} stp_enable=true\n")
    
    f.write("sudo ovs-vsctl set bridge core1 stp_enable=true\n")
    f.write("sudo ovs-vsctl set bridge core2 stp_enable=true\n")
    f.write("sudo ovs-vsctl set bridge core3 stp_enable=true\n")
    f.write("sudo ovs-vsctl set bridge core4 stp_enable=true\n")