"""Drive a node's VNC console (pfSense installer / VGA consoles, ADMIN-WS desktop).

  python automation/vnc.py FW-A shot  screenshots/10_fw-a_installer.png
  python automation/vnc.py FW-A keys  "enter" "down" "enter"        (vncdotool key names)
  python automation/vnc.py FW-A type  "8"                            (types text, no Enter)
  python automation/vnc.py FW-A line  "ifconfig em0"                 (types text + Enter)
  python automation/vnc.py FW-A click 640 400
"""
import sys
import time
from pathlib import Path

from vncdotool import api as vapi

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402


def connect(node_name):
    a = labctl.Gns3()
    p = a.project()
    n = a.node(p, node_name)
    host = n["console_host"] if n["console_host"] not in ("0.0.0.0", "unknown") else a.req("GET", "/computes/vm")["host"]
    port = n["console"]
    return vapi.connect(f"{host}::{port}", password=None, timeout=20)


def main(argv):
    node, op, args = argv[0], argv[1], argv[2:]
    c = connect(node)
    try:
        if op == "shot":
            Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
            c.refreshScreen()
            c.captureScreen(args[0])
            print("saved", args[0])
        elif op == "keys":
            for k in args:
                c.keyPress(k)
                time.sleep(0.4)
        elif op in ("type", "line"):
            for ch in args[0]:
                c.keyPress("space" if ch == " " else ch)
                time.sleep(0.05)
            if op == "line":
                c.keyPress("enter")
        elif op == "click":
            c.mouseMove(int(args[0]), int(args[1]))
            c.mousePress(1)
        else:
            print(__doc__)
    finally:
        c.disconnect()
        vapi.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
