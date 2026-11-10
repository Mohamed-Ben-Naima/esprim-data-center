"""Bring the extended ACLs of a running Cisco device in line with configs/<DEV>.cfg, line by line (no reload).

  python automation/acl_sync.py CORE-A ACL-VLAN40-IN ACL-VLAN20-IN   # named ACLs
  python automation/acl_sync.py CORE-A                                # every extended ACL of the generated config
  python automation/acl_sync.py CORE-A --check                        # show the differences only

Why: `labctl.py push` replays the whole configuration, which adds new ACL entries after the final deny instead of in
place. Here each ACL is read live (`show ip access-lists`), entries absent from the generated config are removed
(`no <seq>`), and missing entries are inserted with a sequence number between their generated neighbours, so the ACL
never disappears and is never open while it changes. Then `write memory`.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labctl  # noqa: E402

NET = Path(__file__).resolve().parents[1]
# IOS prints well-known ports by name; compare on numbers
PORTS = {"www": "80", "domain": "53", "ntp": "123", "snmp": "161", "snmptrap": "162", "syslog": "514", "ftp": "21",
         "telnet": "23", "smtp": "25", "bootps": "67", "bootpc": "68", "tftp": "69", "sunrpc": "111", "ssh": "22"}


def norm(line):
    line = re.sub(r"\s*\(\d+ match(es)?\)", "", line).strip()
    line = re.sub(r"\beq (\S+)", lambda m: f"eq {PORTS.get(m.group(1), m.group(1))}", line)
    return " ".join(line.split())


def generated(dev):
    acls, cur = {}, None
    for ln in (NET / "configs" / f"{dev}.cfg").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^ip access-list extended (\S+)", ln)
        if m:
            cur = acls.setdefault(m.group(1), [])
        elif cur is not None and ln.startswith(" ") and not ln.strip().startswith("remark"):
            cur.append(ln.strip())
        elif not ln.startswith(" "):
            cur = None
    return acls


def live(ios, name):
    out = ios.cmd(f"show ip access-lists {name}")
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^\s+(\d+) (.+)$", out, re.M)]


def plan(want, have):
    """-> config lines (inside the ACL) that turn `have` [(seq, text)] into `want` [text]."""
    have_n = {norm(t): s for s, t in have}
    want_n = [norm(t) for t in want]
    cmds = [f"no {s}" for s, t in have if norm(t) not in want_n]
    kept = {t: s for t, s in have_n.items() if t in want_n}
    for i, (w, raw) in enumerate(zip(want_n, want)):
        if w in kept:
            continue
        prev = max([kept[x] for x in want_n[:i] if x in kept] or [0])
        nxt = min([kept[x] for x in want_n[i + 1:] if x in kept] or [prev + 20])
        seq = prev + 1
        if seq >= nxt:
            raise SystemExit(f"no free sequence number between {prev} and {nxt} for {raw!r}: run 'ip access-list "
                             f"resequence' on the device first")
        kept[w] = seq
        cmds.append(f"{seq} {raw}")
    return cmds


def main(argv):
    dev, names = argv[0], [a for a in argv[1:] if not a.startswith("--")]
    check = "--check" in argv
    gen = generated(dev)
    names = names or sorted(gen)
    api = labctl.Gns3()
    p = api.open(api.project())
    u, pw, en = labctl.creds()
    with labctl.Console.for_node(api, p, dev) as c:
        ios = labctl.Ios(c, u, pw, en)
        ios.login()
        todo = []
        for name in names:
            cmds = plan(gen[name], live(ios, name))
            print(f"{dev} {name}: {'in line' if not cmds else f'{len(cmds)} change(s)'}")
            for x in cmds:
                print(f"   {x}")
            if cmds:
                todo += [f"ip access-list extended {name}", *cmds, "exit"]
        if todo and not check:
            errs = ios.push_config("\n".join(todo))
            ios.save()
            print(f"{dev}: applied and saved, {len(errs)} rejected line(s)")
            for l, e in errs:
                print(f"   {l!r} -> {e}")
            again = [n for n in names if plan(gen[n], live(ios, n))]
            print(f"{dev}: re-check {'OK, all in line' if not again else f'still different: {again}'}")
            return 1 if again or errs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
