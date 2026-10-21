"""Attach the offline repository ISO (built by build_repo.sh) as the second virtio disk of server VMs.

  python automation/attach_repo.py SRV-BASTION SRV-MON-01 ...      (nodes are stopped, updated, restarted)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

ISO = "dc-lab-repo-focal-v2.iso"     # build_repo.sh now builds v3 (+ plugins/): switch once it is built (PLAN_02 GRF.2)
api = labctl.Gns3()
P = api.project()
for name in sys.argv[1:]:
    n = api.node(P, name)
    if n["properties"].get("hdb_disk_image") == ISO:
        print(f"{name}: already attached")
    else:
        if n["status"] != "stopped":
            api.stop(P, n)
            time.sleep(3)
        api.update_node(P, n, {"properties": {"hdb_disk_image": ISO, "hdb_disk_interface": "virtio"}})
        print(f"{name}: {ISO} attached as hdb (virtio)")
    if api.node(P, name)["status"] != "started":
        api.start(P, api.node(P, name))
        print(f"{name}: started")
