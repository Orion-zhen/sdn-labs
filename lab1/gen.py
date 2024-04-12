with open("./stp.sh", "w") as f:
    f.write("#!/bin/bash\n")
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl set bridge edge{i}_{j} stp_enable=true\n")
    
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl set bridge aggr{i}_{j} stp_enable=true\n")
            
    for i in range(1, 5):
        f.write(f"sudo ovs-vsctl set bridge core{i} stp_enable=true\n")
    
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl del-fail-mode edge{i}_{j}\n")
            
    for i in range(1, 5):
        for j in range(1, 3):
            f.write(f"sudo ovs-vsctl del-fail-mode aggr{i}_{j}\n")

    for i in range(1, 5):
        f.write(f"sudo ovs-vsctl del-fail-mode core{i}\n")
    