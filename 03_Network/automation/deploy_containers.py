"""Attach the custom images to the GNS3 docker nodes and push their network configuration (idempotent).

GNS3 cannot change the image of an existing docker node, so a node whose image differs is re-created:
its links are recorded, the node is deleted and created again (same name, position, console, symbol)
with the new image/environment/volumes, then its links are restored on the same ports.
Finally /etc/network/interfaces is written through the node-files API
(persisted under project-files/docker/<node-id>/etc/network/).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
ENV_COMMON = "TZ=Africa/Casablanca"
SPEC = {   # node: (image, extra env, volumes, adapters, interfaces file)
    "ISP-A":       ("dc/frr-isp:1.0", "ISP_NAME=ISP-A", [], 3, "ISP-A/interfaces"),
    "ISP-B":       ("dc/frr-isp:1.0", "ISP_NAME=ISP-B", [], 3, "ISP-B/interfaces"),
    "SYSLOG":      ("dc/syslog:1.0", "", ["/var/log/remote"], 1, "docker/SYSLOG.interfaces"),
    "BMS-SIM":     ("dc/bms-sim:1.0", "SYSLOG_HOST=10.60.0.12", [], 1, "docker/BMS-SIM.interfaces"),
    "CCTV-SIM":    ("dc/cctv-sim:1.0", "SYSLOG_HOST=10.60.0.12", [], 1, "docker/CCTV-SIM.interfaces"),
    "SRV-DCIM-01": ("dc/dcim:1.0", "SYSLOG_HOST=10.60.0.12\nBMS_URL=http://10.70.0.12:8080/api/state", [], 2, "docker/SRV-DCIM-01.interfaces"),
    "SRV-WEB-01":  ("dc/web:1.0", "", [], 1, "docker/SRV-WEB-01.interfaces"),
    "ADMIN-WS":    ("gns3/webterm:latest", "", ["/root"], 1, "docker/ADMIN-WS.interfaces"),
}

api = labctl.Gns3()
P = api.open(api.project())
PID = P["project_id"]


def node_links(n):
    """[(local adapter, local port, peer node name, peer adapter, peer port)] for node n."""
    names = {x["node_id"]: x["name"] for x in api.nodes(P)}
    out = []
    for l in api.links(P):
        ends = l["nodes"]
        for i, e in enumerate(ends):
            if e["node_id"] == n["node_id"]:
                o = ends[1 - i]
                out.append((e["adapter_number"], e["port_number"], names[o["node_id"]], o["adapter_number"], o["port_number"]))
    return out


def recreate(n, image, environment, vols, adapters):
    links = node_links(n)
    if n["status"] != "stopped":
        api.stop(P, n)
    api.req("DELETE", f"/projects/{PID}/nodes/{n['node_id']}")
    body = {"name": n["name"], "node_type": "docker", "compute_id": n["compute_id"], "x": n["x"], "y": n["y"],
            "symbol": n["symbol"], "console_type": n["console_type"], "label": n["label"],
            "properties": {"image": image, "environment": environment, "extra_volumes": vols, "adapters": adapters,
                           "console_resolution": n["properties"].get("console_resolution", "1280x800"),
                           "start_command": "", "extra_hosts": ""}}
    new = api.req("POST", f"/projects/{PID}/nodes", body)
    peers = {x["name"]: x["node_id"] for x in api.nodes(P)}
    for a, p, peer, pa, pp in links:
        api.req("POST", f"/projects/{PID}/links", {"nodes": [
            {"node_id": new["node_id"], "adapter_number": a, "port_number": p},
            {"node_id": peers[peer], "adapter_number": pa, "port_number": pp}]})
    return new, len(links)


for name, (image, env, vols, adapters, ifile) in SPEC.items():
    n = api.node(P, name)
    pr = n["properties"]
    environment = "\n".join(x for x in (ENV_COMMON, env) if x)
    action = "unchanged"
    if pr.get("image") != image:
        n, k = recreate(n, image, environment, vols, adapters)
        action = f"re-created ({k} link(s) restored)"
    else:
        diff = {k: v for k, v in {"environment": environment, "extra_volumes": vols, "adapters": adapters}.items() if pr.get(k) != v}
        if diff:
            if n["status"] != "stopped":
                api.stop(P, n)
            api.update_node(P, n, {"properties": diff})
            action = "updated " + ",".join(diff)
    text = (NET / "configs" / ifile).read_text(encoding="utf-8").replace("\r\n", "\n")
    api.write_node_file(P, n, "etc/network/interfaces", text)
    got = api.node(P, name)["properties"]["image"]
    print(f"{name:12} {got:22} {action:36} interfaces <- configs/{ifile}")
