"""Turn the GNS3 node SRV-BCK-01 into the TrueNAS SCALE appliance (PLAN_04 NAS.2) - idempotent, via the GNS3 API.

  python automation/nas_node.py              # create / check the node
  python automation/nas_node.py --installed  # after the installation: ISO removed, RAM = servers.SRV-BCK-01.ram

The old Ubuntu node (never deployed) is deleted and re-created with the same name, position and links: boot disk and
two data disks (thin qcow2 from the GNS3 empty images, SATA so the disks have serial numbers for ZFS), the ISO in the
CD-ROM, two virtio NICs (eth0 -> LEAF-B1, eth1 -> LEAF-B2), VNC console for the installer. Boot order "cd": the empty
disk fails, so the first boot is the installer; once installed, the disk boots.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
INV = yaml.safe_load((NET / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
NAME = "SRV-BCK-01"
T, S = INV["truenas"], INV["servers"][NAME]
BOOT, DATA = f"empty{T['disks']['boot_gb']}G.qcow2", f"empty{T['disks']['data_gb']}G.qcow2"


def wanted(installed):
    return {"ram": S["ram"] if installed else T["install_ram"], "cpus": S["cpus"], "adapters": 2,
            "adapter_type": "virtio-net-pci", "hda_disk_image": BOOT, "hda_disk_interface": "sata",
            "hdb_disk_image": DATA, "hdb_disk_interface": "sata", "hdd_disk_image": DATA, "hdd_disk_interface": "sata",
            "cdrom_image": "" if installed else T["iso"], "boot_priority": "cd", "options": "-cpu host",
            "on_close": "shutdown_signal"}


def main():
    installed = "--installed" in sys.argv
    api = labctl.Gns3()
    p = api.open(api.project())
    pid = p["project_id"]
    n = api.node(p, NAME)
    if n["properties"].get("hda_disk_image") != BOOT:            # still the old Ubuntu node
        if n["status"] != "stopped":
            api.stop(p, n)
        peers = []
        for l in api.links(p):
            ends = l["nodes"]
            if any(e["node_id"] == n["node_id"] for e in ends):
                other = next(e for e in ends if e["node_id"] != n["node_id"])
                peers.append((other["node_id"], other["adapter_number"], other["port_number"],
                              next(e for e in ends if e["node_id"] == n["node_id"])["adapter_number"]))
        api.req("DELETE", f"/projects/{pid}/nodes/{n['node_id']}")
        new = api.req("POST", f"/projects/{pid}/nodes", {
            "name": NAME, "compute_id": "vm", "node_type": "qemu", "console_type": "vnc", "x": n["x"], "y": n["y"],
            "symbol": n["symbol"], "port_name_format": "eth{0}",
            "properties": {"qemu_path": "/usr/bin/qemu-system-x86_64", "platform": "x86_64", "linked_clone": True,
                           **wanted(installed)}})
        for node_id, a, port, mine in peers:                       # eth0 -> LEAF-B1 Gi0/2, eth1 -> LEAF-B2 Gi0/2
            api.req("POST", f"/projects/{pid}/links", {"nodes": [
                {"node_id": new["node_id"], "adapter_number": mine, "port_number": 0},
                {"node_id": node_id, "adapter_number": a, "port_number": port}]})
        print(f"{NAME}: re-created as TrueNAS ({len(peers)} links restored)")
        n = api.node(p, NAME)
    diff = {k: v for k, v in wanted(installed).items() if n["properties"].get(k) != v}
    if diff:
        if n["status"] != "stopped":
            sys.exit(f"{NAME} must be stopped to change {sorted(diff)}")
        api.update_node(p, n, {"properties": diff})
        print(f"{NAME}: updated {sorted(diff)}")
    n = api.node(p, NAME)
    links = [l for l in api.links(p) if any(e["node_id"] == n["node_id"] for e in l["nodes"])]
    pr = n["properties"]
    print(f"{NAME}: {n['status']}, console {n['console_type']}:{n['console']}, ram {pr['ram']} MB, {pr['cpus']} vCPU, "
          f"disks {pr['hda_disk_image']} + {pr['hdb_disk_image']} + {pr['hdd_disk_image']}, cdrom '{pr['cdrom_image']}', "
          f"{len(links)} links")


if __name__ == "__main__":
    main()
