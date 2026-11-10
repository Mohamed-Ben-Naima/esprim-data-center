"""lab_proxy – open the lab's web interfaces from the physical PC (SOCKS5 proxy into the administration zone).

  python automation/lab_proxy.py start | stop | status        (on the Windows host)
  python automation/lab_proxy.py open [URL ...]               (Edge window that browses through the proxy)

The proxy runs inside the GNS3 VM. It listens on the VM's host-only address (192.168.75.128:1080, reachable from the
physical PC only) and opens every outgoing connection from the network namespace of the ADMIN-WS container: traffic
enters the lab as the admin workstation (10.90.0.12, VLAN 90) and is filtered by the pfSense ADMIN rules like any
administrator. Lab-only helper, no authentication; restart it after ADMIN-WS is restarted.
"""
import ctypes
import os
import select
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

LISTEN = ("192.168.75.128", 1080)
NODE = "ADMIN-WS"
REMOTE = "/tmp/lab_proxy.py"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PAGES = ["https://10.90.0.1/", "http://10.60.0.11/", "http://10.60.0.11:3000/", "http://10.70.0.12:8080/",
         "http://10.70.0.11:8080/", "https://10.50.0.11/", "https://10.60.0.12/"]


# ------------------------------------------------------------------------------------------ inside the GNS3 VM
def recv_exact(s, n):
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise ConnectionError("closed")
        data += chunk
    return data


def relay(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 300)
            if not r:
                return
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except OSError:
        pass


def handle(client):
    upstream = None
    try:
        client.settimeout(15)
        ver, nmethods = recv_exact(client, 2)
        recv_exact(client, nmethods)
        client.sendall(b"\x05\x00")                                   # no authentication
        ver, cmd, _, atyp = recv_exact(client, 4)
        if atyp == 1:
            host = socket.inet_ntoa(recv_exact(client, 4))
        elif atyp == 3:
            host = recv_exact(client, recv_exact(client, 1)[0]).decode()
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(client, 16))
        else:
            return
        port = struct.unpack("!H", recv_exact(client, 2))[0]
        if cmd != 1:                                                  # CONNECT only
            client.sendall(b"\x05\x07\x00\x01" + bytes(6)); return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.sendall(b"\x05\x05\x00\x01" + bytes(6)); return
        client.sendall(b"\x05\x00\x00\x01" + bytes(6))
        client.settimeout(None); upstream.settimeout(None)
        relay(client, upstream)
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        for s in (client, upstream):
            if s:
                try:
                    s.close()
                except OSError:
                    pass


def serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)          # created in the VM's own namespace
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN); srv.listen(64)
    cid = subprocess.check_output(["docker", "ps", "-q", "--filter", f"name={NODE}"], text=True).split()
    if not cid:
        sys.exit(f"{NODE} container is not running")
    pid = subprocess.check_output(["docker", "inspect", "-f", "{{.State.Pid}}", cid[0]], text=True).strip()
    fd = os.open(f"/proc/{pid}/ns/net", os.O_RDONLY)
    if ctypes.CDLL("libc.so.6", use_errno=True).setns(fd, 0x40000000) != 0:      # CLONE_NEWNET
        sys.exit(f"setns failed: {os.strerror(ctypes.get_errno())}")
    print(f"SOCKS5 on {LISTEN[0]}:{LISTEN[1]} -> network namespace of {NODE} (pid {pid})", flush=True)
    while True:                                                       # threads inherit the container namespace
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


# ------------------------------------------------------------------------------------------ on the Windows host
def host(op, args):
    sys.path.insert(0, str(Path(__file__).parent))
    import gns3vm
    if op == "open":
        profile = Path(os.environ.get("TEMP", ".")) / "dc-casa-lab-browser"
        subprocess.Popen([EDGE, f"--proxy-server=socks5://{LISTEN[0]}:{LISTEN[1]}", f"--user-data-dir={profile}",
                          "--ignore-certificate-errors", "--no-first-run", *(args or PAGES)])
        return
    if op in ("stop", "start"):
        gns3vm.run("sudo pkill -f 'lab_proxy.py serve'; true", sudo=True)
    if op == "start":
        gns3vm.put(Path(__file__), REMOTE)
        gns3vm.run(f"sudo sh -c 'nohup setsid python3 {REMOTE} serve > /tmp/lab_proxy.log 2>&1 &'; sleep 2", sudo=True)
    print(gns3vm.run("ss -ltn | grep ':1080 ' || echo 'proxy not running'; cat /tmp/lab_proxy.log 2>/dev/null").strip())


if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    if op == "serve":
        serve()
    elif op in ("start", "stop", "status", "open"):
        host(op, sys.argv[2:])
    else:
        print(__doc__)
