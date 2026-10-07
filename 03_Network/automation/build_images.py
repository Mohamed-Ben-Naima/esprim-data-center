"""Build the lab's custom Docker images inside the GNS3 VM and smoke-test them.

  python automation/build_images.py [name ...]      (default: all images under docker/)
Images are tagged dc/<name>:1.0. The frr-isp context embeds configs/ISP-A and configs/ISP-B (generated).
"""
import io
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gns3vm  # noqa: E402

NET = Path(__file__).resolve().parents[1]
DOCKER = NET / "docker"
TAG = "1.0"

SMOKE = {
    "frr-isp": "docker run --rm --entrypoint sh dc/frr-isp:1.0 -c 'ls /config/*/frr.conf && bash -n /usr/local/bin/isp-start.sh && echo SMOKE-OK'",
    "syslog": "docker run --rm dc/syslog:1.0 rsyslogd -N1 -f /etc/rsyslog.conf 2>&1 | tail -2 && echo SMOKE-OK",
    "web": "docker run --rm dc/web:1.0 nginx -t 2>&1 | tail -2 && echo SMOKE-OK",
    "bms-sim": ("cid=$(docker run -d --rm -e SYSLOG_HOST=127.0.0.1 dc/bms-sim:1.0); sleep 2; "
                "docker exec $cid python -c \"import urllib.request as u,json;"
                "s=json.load(u.urlopen('http://127.0.0.1:8080/api/set?UTILITY-A=DOWN&UPS-A=DOWN&GENERATOR=DOWN'));"
                "print(s['paths'],s['status'],[a['id'] for a in s['alarms']])\"; docker rm -f $cid >/dev/null; echo SMOKE-OK"),
    "cctv-sim": "docker run --rm --entrypoint python dc/cctv-sim:1.0 -c 'import ast;ast.parse(open(\"/app/app.py\").read());print(\"SMOKE-OK\")'",
    "dcim": ("cid=$(docker run -d --rm -e BMS_URL=http://127.0.0.1:1/x dc/dcim:1.0); sleep 2; "
             "docker exec $cid python -c \"import urllib.request as u,json;s=json.load(u.urlopen('http://127.0.0.1:8080/api/summary'));"
             "print(s['racks'],s['it_load_kw'],s['by_type'])\"; docker rm -f $cid >/dev/null; echo SMOKE-OK"),
}


def context_tar(name):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in sorted((DOCKER / name).rglob("*")):
            if f.is_file():
                data = f.read_bytes().replace(b"\r\n", b"\n")
                info = tarfile.TarInfo(str(f.relative_to(DOCKER / name)).replace("\\", "/"))
                info.size, info.mode = len(data), 0o755 if f.suffix in (".sh",) else 0o644
                tar.addfile(info, io.BytesIO(data))
        if name == "frr-isp":
            for isp in ("ISP-A", "ISP-B"):
                for f in ("frr.conf", "daemons"):
                    data = (NET / "configs" / isp / f).read_bytes().replace(b"\r\n", b"\n")
                    info = tarfile.TarInfo(f"config/{isp}/{f}")
                    info.size, info.mode = len(data), 0o644
                    tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def build(name):
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / f"{name}.tgz"
        t.write_bytes(context_tar(name))
        gns3vm.put(t, f"/tmp/ctx_{name}.tgz")
    out = gns3vm.run(f"""set -e
rm -rf /tmp/ctx_{name}; mkdir -p /tmp/ctx_{name}; tar -xzf /tmp/ctx_{name}.tgz -C /tmp/ctx_{name}
docker build -q -t dc/{name}:{TAG} /tmp/ctx_{name}
docker image inspect dc/{name}:{TAG} -f 'size={{{{.Size}}}}'
{SMOKE.get(name, 'echo SMOKE-OK')}
rm -rf /tmp/ctx_{name} /tmp/ctx_{name}.tgz""")
    ok = "SMOKE-OK" in out
    print(f"== dc/{name}:{TAG}  {'OK' if ok else 'FAILED'}\n" + "\n".join("   " + l for l in out.strip().splitlines()[-6:]))
    return ok


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.name for p in DOCKER.iterdir() if (p / "Dockerfile").exists())
    results = {n: build(n) for n in names}
    sys.exit(0 if all(results.values()) else 1)
