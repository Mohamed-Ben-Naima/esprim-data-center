"""Build the lab's custom Docker images inside the GNS3 VM and smoke-test them.

  python automation/build_images.py [name ...]      (default: all images under docker/)
Images are tagged dc/<name>:<TAGS[name]> (default 1.0). The frr-isp context embeds configs/ISP-A and configs/ISP-B (generated);
the admin-ws context embeds configs/docker/ADMIN-WS.ssh_config and ADMIN-WS.portal.html (generated).
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
TAGS = {"syslog": "1.1"}           # bumped when an image changes behaviour (deploy_containers.SPEC uses the same tag)
_SELFTEST = "selftest:pbkdf2_sha256$1000$73656c66$" + __import__("hashlib").pbkdf2_hmac(
    "sha256", b"selftest", bytes.fromhex("73656c66"), 1000).hex()

SMOKE = {
    "admin-ws": ("docker run --rm --entrypoint sh dc/admin-ws:1.0 -c 'for b in ssh firefox-esr curl snmpget dig nc logger; do "
                 "command -v $b >/dev/null || { echo MISSING $b; exit 1; }; done; ssh -G core-a | grep -E \"^(hostname|user) \"; "
                 "test -s /usr/share/dc-portal/index.html && sh -n /usr/local/bin/ssh && echo SMOKE-OK'"),
    "frr-isp": "docker run --rm --entrypoint sh dc/frr-isp:1.0 -c 'ls /config/*/frr.conf && bash -n /usr/local/bin/isp-start.sh && echo SMOKE-OK'",
    "syslog": ("docker run --rm --entrypoint rsyslogd dc/syslog:1.1 -N1 -f /etc/rsyslog.conf 2>&1 | tail -2; "
               f"cid=$(docker run -d --rm -e 'VIEWER_AUTH={_SELFTEST}' dc/syslog:1.1); sleep 3; "
               "docker exec $cid python3 /opt/viewer/selftest.py && rc=0 || rc=$?; docker rm -f $cid >/dev/null; "
               "[ $rc -eq 0 ] && echo SMOKE-OK"),
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
        if name == "admin-ws":
            for src, dst in (("ADMIN-WS.ssh_config", "ssh_config"), ("ADMIN-WS.portal.html", "portal.html")):
                data = (NET / "configs" / "docker" / src).read_bytes().replace(b"\r\n", b"\n")
                info = tarfile.TarInfo(dst)
                info.size, info.mode = len(data), 0o644
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
    tag = TAGS.get(name, TAG)
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / f"{name}.tgz"
        t.write_bytes(context_tar(name))
        gns3vm.put(t, f"/tmp/ctx_{name}.tgz")
    out = gns3vm.run(f"""set -e
rm -rf /tmp/ctx_{name}; mkdir -p /tmp/ctx_{name}; tar -xzf /tmp/ctx_{name}.tgz -C /tmp/ctx_{name}
docker build -q -t dc/{name}:{tag} /tmp/ctx_{name}
docker image inspect dc/{name}:{tag} -f 'size={{{{.Size}}}}'
{SMOKE.get(name, 'echo SMOKE-OK')}
rm -rf /tmp/ctx_{name} /tmp/ctx_{name}.tgz""")
    ok = "SMOKE-OK" in out
    print(f"== dc/{name}:{tag}  {'OK' if ok else 'FAILED'}\n" + "\n".join("   " + l for l in out.strip().splitlines()[-24:]))
    return ok


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.name for p in DOCKER.iterdir() if (p / "Dockerfile").exists())
    results = {n: build(n) for n in names}
    sys.exit(0 if all(results.values()) else 1)
