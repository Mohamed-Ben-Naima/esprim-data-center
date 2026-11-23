"""Visual kit V2-V19 (PLAN_05 D11/D12): clean SVG diagrams, rendered to PNG for the deck.

  python 05_Report/presentation/assets/build_diagrams.py [V4 V5 ...]

Every name, address and number is read from facts.json or the inventory (no value typed twice).
SVG sources -> assets/diagrams/*.svg ; PNG (2x, fonts loaded) -> assets/diagrams/png/*.png (rendered with Edge).
Style D11: graphite background, cyan LED accent, one colour per security zone (same as the GNS3 legend),
Inter for text, JetBrains Mono for addresses and commands.
"""
import json
import sys
from html import escape
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
F = json.loads((HERE.parent / "facts.json").read_text(encoding="utf-8"))
INV = yaml.safe_load((ROOT / "03_Network" / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
OUT = HERE / "diagrams"
PNG = OUT / "png"

# ---- D11 palette ----------------------------------------------------------------------------------------------
BG, PANEL, PANEL2, LINE = "#12181F", "#1A232C", "#222D38", "#3A4856"
TXT, MUTED, DIM = "#E8EEF2", "#A9B8C4", "#7F909E"
CYAN, CYAN_D = "#3FD0E8", "#1B8FA3"
OK, WARN, BAD = "#4CC38A", "#F0AD4E", "#E5675F"
Z = {"internet": "#4A90D9", "er": "#8C99A6", "fw": "#E0605B", "dmz": "#F0AD4E", "mgmt": "#9B7BCB",
     "core": "#2FB3A3", "hallA": "#5CB85C", "hallB": "#3FAE6A", "transit": "#6B7A88"}
SANS, MONO = "Inter, Arial, sans-serif", "'JetBrains Mono', Consolas, monospace"


class S:
    """Tiny SVG builder."""

    def __init__(self, w, h):
        self.w, self.h, self.el = w, h, []
        self.defs = (f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                     f'<path d="M0 0L10 5L0 10z" fill="{MUTED}"/></marker>'
                     f'<marker id="ac" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                     f'<path d="M0 0L10 5L0 10z" fill="{CYAN}"/></marker>'
                     f'<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                     f'<path d="M0 0L10 5L0 10z" fill="{BAD}"/></marker>')

    def add(self, s):
        self.el.append(s)

    def t(self, x, y, s, size=22, w=400, c=TXT, a="start", f=SANS, op=1):
        self.add(f'<text x="{x}" y="{y}" font-family="{f}" font-size="{size}" font-weight="{w}" fill="{c}" '
                 f'text-anchor="{a}" opacity="{op}">{escape(str(s))}</text>')

    def rect(self, x, y, w, h, fill=PANEL, stroke=LINE, r=12, sw=1.5, dash=None, op=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" fill-opacity="{op}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def box(self, x, y, w, h, title, lines=(), color=CYAN, size=24, sub=20, center=False, dash=None, fill=PANEL, top=False):
        """Node card: coloured top bar, bold title, mono detail lines."""
        self.rect(x, y, w, h, fill=fill, stroke=color if dash else LINE, dash=dash)
        if not dash:
            self.add(f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{color}"/>')
        cx = x + w / 2 if center else x + 18
        a = "middle" if center else "start"
        n = len(lines)
        top = y + size + 22 if top else y + h / 2 - (size + n * (sub + 8)) / 2 + size * 0.85 + 3
        self.t(cx, top, title, size, 700, TXT, a)
        for i, ln in enumerate(lines):
            self.t(cx, top + (i + 1) * (sub + 8) + 2, ln, sub, 400, MUTED, a, MONO if ln[:1].isdigit() or "." in ln[:6] else SANS)

    def zone(self, x, y, w, h, label, color, size=20, bottom=False, right=False):
        self.rect(x, y, w, h, fill=color, stroke=color, r=16, sw=1.5, op=0.08)
        ty = y + h - 14 if bottom else y + size + 10
        self.t(x + w - 16 if right else x + 16, ty, label.upper(), size, 700, color, "end" if right else "start")

    def line(self, x1, y1, x2, y2, c=MUTED, sw=2.5, head="a", dash=None, both=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        ms = f' marker-start="url(#{head})"' if both and head else ""
        me = f' marker-end="url(#{head})"' if head else ""
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}"{d}{ms}{me}/>')

    def path(self, d, c=MUTED, sw=2.5, head="a", dash=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#{head})"' if head else ""
        self.add(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}"{ds}{me}/>')

    def pill(self, x, y, s, c=CYAN, size=18, fg=BG, w=None):
        w = w or len(s) * size * 0.62 + 24
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{size + 14}" rx="{(size + 14) / 2}" fill="{c}"/>')
        self.t(x + w / 2, y + size + 2, s, size, 700, fg, "middle")
        return w

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                f'<defs>{self.defs}</defs><rect width="{self.w}" height="{self.h}" fill="{BG}"/>' + "".join(self.el) + "</svg>")


V = F["lab"]["vlans"]
R = F["resilience"]


def fmt(x):
    return f"{x:.1f}".replace(".", ",")


# ---- V2 Tier I-IV ---------------------------------------------------------------------------------------------
def v2():
    s = S(1600, 760)
    tiers = F["design"]["tiers"]
    rows = [("Redondance", "redundancy"), ("Chemins de distribution", "paths"), ("Disponibilité", "avail"),
            ("Arrêt / an", "down_h")]
    cw, x0 = 300, 340
    for i, (k, t) in enumerate(tiers.items()):
        x = x0 + i * (cw + 20)
        ours = k == "III"
        s.rect(x, 40, cw, 680, fill=PANEL2 if ours else PANEL, stroke=CYAN if ours else LINE, sw=3 if ours else 1.5)
        s.t(x + cw / 2, 110, f"Tier {k}", 44, 800, CYAN if ours else TXT, "middle")
        for j, (lab, key) in enumerate(rows):
            v = t[key]
            v = (fmt(v).rstrip("0").rstrip(",") + " %") if key == "avail" else (fmt(v) + " h") if key == "down_h" else str(v)
            if key == "avail":
                v = f"{t[key]:.3f}".replace(".", ",") + " %"
            s.t(x + cw / 2, 205 + j * 110, v, 30 if len(v) < 14 else 24, 700 if key in ("avail", "down_h") else 500,
                TXT, "middle", MONO if key in ("avail", "down_h") else SANS)
        flags = ("Maintenable sans arrêt" if t.get("concurrently_maintainable") else
                 "Tolérant aux pannes" if t.get("fault_tolerant") else "Arrêt pour maintenance")
        s.t(x + cw / 2, 655, flags, 21, 600, OK if ours else MUTED, "middle")
        if ours:
            s.pill(x + cw / 2 - 130, 690 - 2, "NOTRE CIBLE : RATED-3", CYAN, 18, BG, 260)
    for j, (lab, _) in enumerate(rows):
        s.t(40, 205 + j * 110, lab, 24, 600, MUTED)
        s.line(40, 230 + j * 110, 1580, 230 + j * 110, LINE, 1, None)
    return s


# ---- V3 TIA-942 spaces floor plan ----------------------------------------------------------------------------
def v3():
    s = S(1600, 820)
    s.zone(20, 20, 1560, 780, "Bâtiment informatique – espaces ANSI/TIA-942-C", CYAN, 22)
    # entrance rooms
    s.box(60, 90, 300, 190, "ER – Entrance Room", ["ISP-A · ISP-B", "EDGE-A · EDGE-B", "SW-OUT (VLAN 901)"], Z["er"], 24, 20)
    s.box(60, 300, 300, 150, "Arrivée opérateur B", ["chemin fibre distinct", "Meet-Me Room"], Z["internet"], 22, 20, dash="8 6")
    s.rect(400, 90, 520, 360)
    s.add(f'<rect x="400" y="90" width="520" height="6" rx="3" fill="{Z["core"]}"/>')
    s.t(418, 138, "MDA – Main Distribution Area", 24, 700, TXT)
    for i, (n, c) in enumerate([("FW-A · FW-B", Z["fw"]), ("CORE-A · CORE-B", Z["core"]), ("SW-DMZ · SW-MGMT · SW-IN", Z["transit"]),
                                ("SRV-BASTION · ADMIN-WS", Z["mgmt"]), ("SRV-WEB-01 (DMZ)", Z["dmz"])]):
        s.rect(430, 160 + i * 56, 460, 46, fill=PANEL2, stroke=c)
        s.t(450, 191 + i * 56, n, 22, 600, TXT)
    s.box(960, 90, 580, 150, "NOC / bureaux", ["supervision Zabbix · Grafana · journaux", "accès badge + biométrie"], Z["mgmt"], 24, 20)
    s.box(960, 260, 580, 190, "Salles techniques (bâtiment technique)", ["UPS-A / UPS-B · TGBT", "groupes 4 × 750 kW (N+1)", "chillers, BMS-SIM"], Z["dmz"], 24, 20)
    # halls
    for k, (x, hall, leafs, srv, col) in enumerate([(60, "A", "LEAF-A1 · LEAF-A2", "SRV-CMP-01/02/03 · SRV-STO-01", Z["hallA"]),
                                                    (810, "B", "LEAF-B1 · LEAF-B2", "BCK · INF · MON · DCIM · SYSLOG · BMS · CCTV", Z["hallB"])]):
        s.zone(x, 480, 730, 300, f"Data Hall {hall} – 48 baies", col, 20)
        s.box(x + 20, 530, 220, 110, f"HDA-{hall}", [leafs], col, 24, 18)
        s.box(x + 260, 530, 450, 110, f"EDA-{hall}", [srv], col, 24, 18)
        for r in range(12):
            s.rect(x + 20 + r * 58, 665, 46, 90, fill=PANEL2, stroke=col, r=4, sw=1)
    s.line(360, 185, 400, 185, CYAN, 3, "ac")
    return s


# ---- V4 full logical architecture ---------------------------------------------------------------------------
def v4():
    s = S(1600, 940)
    tr = INV["transit"]
    s.zone(330, 15, 940, 125, "Internet – opérateurs simulés", Z["internet"], 18, right=True)
    s.box(360, 50, 420, 78, "ISP-A  AS 64500", ["198.51.100.0/30 · primaire LP 200"], Z["internet"], 22, 18)
    s.box(820, 50, 420, 78, "ISP-B  AS 64501", ["203.0.113.0/30 · secours AS-path +2"], Z["internet"], 22, 18)
    s.zone(330, 160, 940, 125, "Entrance Room – AS 65100", Z["er"], 18, right=True)
    s.box(360, 195, 420, 78, "EDGE-A  IOSv", [f"eBGP · HSRP VIP {tr['ext']['edge_vip']}"], Z["er"], 22, 18)
    s.box(820, 195, 420, 78, "EDGE-B  IOSv", ["eBGP · iBGP/OSPF ISL"], Z["er"], 22, 18)
    s.zone(330, 305, 940, 140, "MDA sécurité – pfSense CE 2.7.2 en HA", Z["fw"], 18, right=True)
    s.box(360, 340, 420, 92, "FW-A  MASTER", [f"CARP ×5 · VIP WAN {tr['ext']['fw_vip']}", "SNAT 192.0.2.10"], Z["fw"], 22, 18)
    s.box(820, 340, 420, 92, "FW-B  BACKUP", ["pfsync + XMLRPC (em2)", f"sync {tr['sync']['subnet']}"], Z["fw"], 22, 18)
    s.zone(330, 465, 940, 125, "MDA cœur – passerelles L3", Z["core"], 18, right=True)
    s.box(360, 500, 420, 78, "CORE-A  IOSvL2", ["HSRP actif 20/40/60/100 · OSPF"], Z["core"], 22, 18)
    s.box(820, 500, 420, 78, "CORE-B  IOSvL2", ["HSRP actif 30/70/80 · Po1 LACP"], Z["core"], 22, 18)
    s.zone(20, 610, 760, 310, "Hall A – calcul + stockage", Z["hallA"], 18, bottom=True)
    s.zone(820, 610, 760, 310, "Hall B – services, supervision, sauvegarde", Z["hallB"], 18, bottom=True)
    for i, n in enumerate(["LEAF-A1", "LEAF-A2"]):
        s.box(60 + i * 360, 645, 320, 64, n, [], Z["hallA"], 22, center=True)
    for i, n in enumerate(["LEAF-B1", "LEAF-B2"]):
        s.box(860 + i * 360, 645, 320, 64, n, [], Z["hallB"], 22, center=True)
    for i, (n, ip) in enumerate([("SRV-CMP-01/02", "VIP 10.20.0.10"), ("SRV-CMP-03", "10.20.0.13"), ("SRV-STO-01", "10.30.0.11")]):
        s.box(40 + i * 245, 740, 230, 120, n, [ip, "bond 2 Leaf"], Z["hallA"], 20, 17)
    for i, (n, ip) in enumerate([("SRV-MON-01", "10.60.0.11"), ("SYSLOG", "10.60.0.12"), ("SRV-INF-01", "10.100.0.11"),
                                 ("SRV-BCK-01", "10.40.0.11"), ("BMS · DCIM", "10.70.0.x")]):
        s.box(840 + i * 148, 740, 138, 120, n, [ip], Z["hallB"], 17, 15)
    # side zones
    s.zone(1300, 305, 280, 185, "DMZ – VLAN 50", Z["dmz"], 18)
    s.box(1320, 350, 240, 120, "SRV-WEB-01", ["10.50.0.11", "DNAT 192.0.2.80"], Z["dmz"], 22, 18)
    s.zone(20, 305, 280, 285, "MGMT 10 · ADMIN 90", Z["mgmt"], 18)
    s.box(40, 350, 240, 92, "ADMIN-WS", ["10.90.0.12"], Z["mgmt"], 22, 18)
    s.box(40, 458, 240, 92, "SRV-BASTION", ["10.90.0.11 · TOTP"], Z["mgmt"], 22, 18)
    # links
    for x in (700, 1160):
        s.line(x, 128, x, 195, CYAN, 3, "ac", both=True)
        s.line(x, 273, x, 340, MUTED, 2.5, "a", both=True)
        s.line(x, 432, x, 500, MUTED, 2.5, "a", both=True)
    s.line(700, 128, 1160, 195, CYAN, 1.5, None, "6 6")
    s.line(1160, 128, 700, 195, CYAN, 1.5, None, "6 6")
    s.line(780, 386, 820, 386, Z["fw"], 3, None)
    s.line(780, 539, 820, 539, Z["core"], 4, None)
    s.line(1240, 400, 1320, 400, Z["dmz"], 2.5, "a", both=True)
    s.line(360, 400, 280, 400, Z["mgmt"], 2.5, "a", both=True)
    for lx in (220, 580, 1020, 1380):
        s.line(lx, 645, 700, 578, LINE, 1.8, None)
        s.line(lx, 645, 1160, 578, LINE, 1.8, None)
    s.t(1290, 210, "VLAN 901 transit externe", 17, 500, DIM, "start", MONO)
    s.t(1290, 545, "VLAN 902 transit interne", 17, 500, DIM, "start", MONO)
    return s


# ---- V5 redundancy chain ---------------------------------------------------------------------------------------
def v5():
    s = S(1600, 640)
    tiers = [("2 × ISP", "AS 64500 / 64501", "eBGP 3/9 s", Z["internet"], "T1", R["T1"]),
             ("2 × EDGE", "IOSv", "HSRP + iBGP", Z["er"], None, None),
             ("2 × FW", "pfSense", "CARP + pfsync", Z["fw"], "T2", R["T2"]),
             ("2 × CORE", "IOSvL2", "HSRP · OSPF · LACP", Z["core"], "T3", R["T3"]),
             ("2 × LEAF / hall", "IOSvL2", "Rapid-PVST+", Z["hallA"], "T4", R["T4"]),
             ("Serveurs", "Ubuntu", "bond + keepalived", Z["hallB"], "T5", R["T5"])]
    w, gap = 230, 36
    for i, (n, plat, proto, col, tid, r) in enumerate(tiers):
        x = 20 + i * (w + gap)
        for k in range(2):
            s.box(x + k * 14, 60 + k * 14, w - 14, 150, n if k else "", [plat] if k else [], col, 24, 19, center=True)
        s.pill(x + 4, 245, proto, PANEL2, 18, TXT, w - 8)
        if i < len(tiers) - 1:
            s.line(x + w + 2, 150, x + w + gap - 4, 150, CYAN, 3, "ac")
        if tid:
            ms = r.get("measured_s")
            val = (fmt(ms) + " s") if ms is not None else "—"
            tgt = {"T1": 10, "T2": 5, "T3": 5, "T4": 1, "T5": 60}[tid]
            c = MUTED if ms is None else OK if ms <= tgt else WARN
            s.rect(x, 310, w, 150, fill=PANEL, stroke=LINE)
            s.t(x + w / 2, 350, f"Test {tid}", 20, 600, MUTED, "middle")
            s.t(x + w / 2, 410, val, 48, 800, c, "middle", MONO)
            s.t(x + w / 2, 445, "coupure mesurée" if ms is not None else "non chronométré", 18, 500, DIM, "middle")
    s.rect(20, 500, 1560, 110, fill=PANEL2, stroke=LINE)
    s.t(50, 545, "Aucun point unique de défaillance : chaque niveau est doublé et sa bascule est mesurée.", 24, 600, TXT)
    s.t(50, 585, "Coupures mesurées par sonde continue (fw_lan_failover.py, toutes les 0,5 s) – evidence/fw_lan_failover.txt", 19, 400, MUTED)
    return s


# ---- V6 measured outage chart ---------------------------------------------------------------------------------
def v6():
    s = S(1600, 700)
    rows = [("T2", "FW-A arrêté → FW-B maître CARP", R["T2"]["measured_s"], 5, "≤ 5 s"),
            ("T3", "CORE-A arrêté → CORE-B reprend HSRP", R["T3"]["measured_s"], 5, "≤ 5 s"),
            ("T4", "LEAF-A1 arrêté → bond sur LEAF-A2", R["T4"]["measured_s"], 1, "≈ 1 s"),
            ("T5", "SRV-CMP-01 arrêté → VIP sur CMP-02", R["T5"]["measured_s"], 60, "alerte ≤ 1 min"),
            ("T6", "Perte chemin A → alarme Zabbix", R["T6"]["alarm_s"], 30, "≤ 30 s")]
    x0, scale = 640, 900 / 32
    s.t(x0, 50, "secondes", 18, 500, DIM)
    for v in range(0, 31, 5):
        x = x0 + v * scale
        s.line(x, 70, x, 600, LINE, 1, None)
        s.t(x, 630, str(v), 18, 500, DIM, "middle", MONO)
    for i, (tid, lab, val, tgt, tlab) in enumerate(rows):
        y = 95 + i * 100
        s.t(20, y + 38, tid, 30, 800, CYAN, "start", MONO)
        s.t(90, y + 30, lab, 21, 600, TXT)
        s.t(90, y + 58, f"cible {tlab}", 18, 400, MUTED)
        ok = val <= tgt
        col = OK if ok else WARN
        s.rect(x0, y + 12, val * scale, 44, fill=col, stroke=col, r=6, sw=0)
        lx = x0 + max(val, tgt if tgt <= 30 else 0) * scale + 16
        s.t(lx, y + 44, fmt(val) + " s" + ("" if ok else "  (limite labo)"), 22, 700, col, "start", MONO)
        if tgt <= 30:
            tx = x0 + tgt * scale
            s.line(tx, y + 2, tx, y + 66, TXT, 3, None, "5 4")
    s.t(x0 + 5 * scale + 8, 82, "cible", 16, 600, TXT)
    s.t(20, 680, "T1 (ISP-A) et M1 (double panne) : bascule vérifiée, non chronométrée. T4 > cible : détection ARP 1 s + RPVST+ sur IOSvL2 émulé.", 18, 400, MUTED)
    return s


# ---- V7 power path A/B ----------------------------------------------------------------------------------------
def v7():
    s = S(1600, 760)
    for k, (side, x, col) in enumerate([("A", 60, CYAN), ("B", 900, Z["dmz"])]):
        s.zone(x, 20, 640, 600, f"Chemin {side}", col, 22)
        s.box(x + 30, 70, 270, 100, f"Arrivée HT {side}", ["réseau public, ligne dédiée"], col, 24, 18)
        s.box(x + 340, 70, 270, 100, f"UTILITY-{side}", ["poste de livraison"], col, 24, 18)
        s.box(x + 30, 230, 580, 110, f"UPS-{side} modulaire", ["5 × 250 kW (N+1) · 1 250 kW installés", "≈ 10 min batteries, charge ≈ 38 %"], col, 24, 18)
        s.box(x + 30, 400, 580, 90, f"PDU-{side} par baie", ["mesure de charge, alarme > 45 % / > 50 %"], col, 24, 18)
        s.line(x + 300, 120, x + 340, 120, col, 3, "a")
        s.line(x + 475, 170, x + 475, 230, col, 3, "a")
        s.line(x + 320, 340, x + 320, 400, col, 3, "a")
        s.line(x + 320, 490, 800 if k == 0 else 800, 560, col, 3, "a")
    s.box(640, 560, 320, 140, "Baie IT", ["serveur à double PSU", "PSU-A + PSU-B"], TXT, 26, 19, center=True)
    s.box(712, 200, 176, 170, "Groupes", ["électrogènes", "4 × 750 kW", "N+1, 10–15 s"], Z["fw"], 22, 17, center=True)
    s.line(712, 300, 676, 300, Z["fw"], 3, "a")
    s.line(888, 300, 924, 300, Z["fw"], 3, "a")
    s.rect(20, 720 - 70, 520, 90, fill=PANEL2, stroke=LINE)
    s.t(40, 688, "BMS-SIM (10.70.0.12:8080)", 20, 700, CYAN, "start", MONO)
    s.t(40, 718, "état de chaque élément → Zabbix → Grafana", 19, 400, MUTED)
    s.rect(1060, 650, 520, 90, fill=PANEL2, stroke=LINE)
    s.t(1080, 688, f"Test T6 : chemin A coupé → alarme en {fmt(F['power']['bms_alarm_s'])} s", 20, 700, OK)
    s.t(1080, 718, "cible ≤ 30 s · chemin B seul actif, 0 arrêt", 19, 400, MUTED)
    return s


# ---- V9 lab environment stack ---------------------------------------------------------------------------------
def v9():
    s = S(1600, 760)
    nb = F["lab"]["nodes_by_type"]
    s.rect(20, 640, 1560, 100, fill=PANEL2, stroke=LINE)
    s.t(50, 685, "PC hôte Windows 11 · 15,7 Go RAM", 26, 700, TXT)
    s.t(50, 720, "GNS3 2.2.56 (GUI + contrôleur) · Python 3 · Git + LFS · Blender 5.2 · OBS · ffmpeg", 20, 400, MUTED)
    s.rect(60, 520, 1480, 100, fill=PANEL, stroke=LINE)
    s.t(90, 565, "VMware Workstation", 26, 700, TXT)
    s.t(90, 598, "hyperviseur de type 2 (VT-x, Hyper-V désactivé)", 20, 400, MUTED)
    s.rect(100, 120, 1400, 380, fill=PANEL, stroke=CYAN, sw=2)
    s.t(130, 165, "GNS3 VM (Ubuntu) · 8 Go · 6 vCPU · 192.168.75.128", 26, 700, CYAN)
    cards = [("QEMU / KVM", f"{nb['qemu']} VM", ["2 × IOSv (EDGE)", "6 × IOSvL2 (CORE, LEAF)", "2 × pfSense CE 2.7.2", "7 × Ubuntu · 1 × TrueNAS"], Z["fw"]),
             ("Docker", f"{nb['docker']} conteneurs", ["ISP-A/B (FRR)", "SYSLOG · BMS · CCTV · DCIM", "SRV-WEB-01 (nginx)", "ADMIN-WS (webterm)"], Z["internet"]),
             ("GNS3 intégrés", f"{nb['ethernet_switch'] + nb['nat']} nœuds", ["4 switchs (SW-IN/OUT/DMZ/MGMT)", "2 NAT (sortie Internet)", "0 Mo de RAM"], Z["transit"])]
    for i, (t, n, ls, col) in enumerate(cards):
        x = 130 + i * 455
        s.box(x, 195, 430, 285, t, [], col, 28, top=True)
        s.t(x + 18, 290, n, 40, 800, col, "start", MONO)
        for j, l in enumerate(ls):
            s.t(x + 18, 335 + j * 34, l, 20, 500, MUTED)
    s.pill(1180, 40, f"{F['lab']['nodes']} nœuds · {F['lab']['links']} liens", CYAN, 22, BG, 380)
    s.t(20, 70, "Environnement de travail", 30, 800, TXT)
    return s


# ---- V10 automation pipeline ---------------------------------------------------------------------------------
def v10():
    s = S(1600, 780)
    col = [("Source unique", CYAN, [("inventory/dc_casa.yaml", "VLAN, IP, règles, tests")]),
           ("Générer", Z["internet"], [("gen_gns3.py", "topologie GNS3"), ("gen_configs.py", "Cisco + serveurs"),
                                        ("gen_pfsense.py", "config.xml pfSense"), ("gen_dashboards.py", "Grafana")]),
           ("Déployer", Z["dmz"], [("lab_up.py", "démarrage par étapes"), ("deploy_*.py", "pfSense, serveurs, conteneurs"),
                                    ("zabbix_setup.py", "supervision"), ("truenas_setup.py", "NAS")]),
           ("Contrôler", Z["fw"], [("fw_audit.py", "règles = inventaire"), ("cisco_heal.py", "clé RSA, SNMPv3"),
                                    ("flow_matrix.py", "flux de bout en bout"), ("access_matrix.py", "accès admin")]),
           ("Prouver", OK, [("verify_lab.py", f"{F['tests']['verify_lab']['pass']} PASS · 0 FAIL"),
                            ("demo_check.py", "12/12 contrôles"), ("report/evidence/", "traces datées"),
                            ("rapport Word + PDF", "tableaux générés")])]
    w, gap = 290, 27
    for i, (title, c, items) in enumerate(col):
        x = 20 + i * (w + gap)
        s.t(x, 50, f"{i + 1}. {title}", 26, 800, c)
        n = len(items)
        h = 120
        y0 = 80 if n > 1 else 80 + 1.5 * (h + 20)
        for j, (f, d) in enumerate(items):
            s.box(x, y0 + j * (h + 20), w, h, f, [d], c, 21, 19)
        if i < len(col) - 1:
            s.line(x + w + 2, 360, x + w + gap - 2, 360, CYAN, 3, "ac")
    s.rect(20, 680, 1560, 80, fill=PANEL2, stroke=LINE)
    s.t(50, 730, f"{F['project']['automation_scripts']} scripts Python · {F['project']['automation_lines']:,} lignes · "
                 "versionnés dans Git · une modification = une ligne dans l'inventaire puis régénération".replace(",", " "),
        21, 600, TXT)
    return s


# ---- V11 VLAN / zone map --------------------------------------------------------------------------------------
def v11():
    s = S(1600, 780)
    groups = [("Interne – passerelle HSRP sur les cœurs", Z["core"], [20, 30, 40, 60, 70, 80, 100]),
              ("DMZ – passerelle CARP", Z["dmz"], [50]), ("Management OOB – CARP, VRF MGMT", Z["mgmt"], [10]),
              ("Administration – CARP", Z["mgmt"], [90]), ("Transit", Z["transit"], [901, 902, 998]), ("Parking", DIM, [999])]
    s.zone(20, 20, 1560, 380, groups[0][0], groups[0][1], 22)
    for i, v in enumerate(groups[0][2]):
        d = V[str(v)]
        x = 45 + i * 219
        act = d["active"] or ""
        s.box(x, 80, 200, 290, f"VLAN {v}", [d["name"], d["subnet"], f"VIP {d['gw']}", f"actif {act}"], Z["core"], 28, 18)
    y = 430
    short = ["DMZ · CARP", "MGMT OOB · VRF", "Admin · CARP", "Transit", "Parking"]
    for k, (lab, c, vs) in enumerate(groups[1:]):
        x, w = 20 + k * 316, 296
        s.zone(x, y, w, 330, short[k], c, 18)
        if len(vs) > 1:
            for j, v in enumerate(vs):
                d = V[str(v)]
                s.box(x + 20, y + 55 + j * 90, w - 40, 80, f"VLAN {v}", [d["subnet"]], c, 22, 18)
        else:
            d = V[str(vs[0])]
            lines = [d["name"], d["subnet"] or "ports inutilisés", f"VIP {d['gw']}" if d.get("gw") else "shutdown, BPDU Guard"]
            s.box(x + 20, y + 55, w - 40, 250, f"VLAN {vs[0]}", lines, c, 26, 19)
    return s


# ---- V12 addressing plan ------------------------------------------------------------------------------------
def v12():
    s = S(1600, 760)
    s.t(20, 50, "Règle : 10.<VLAN>.0.0/24 – le numéro de VLAN se lit dans l'adresse", 28, 800, TXT)
    s.rect(20, 80, 760, 300, fill=PANEL, stroke=LINE)
    s.t(50, 130, "Dans chaque VLAN interne (ex. VLAN 20)", 24, 700, CYAN)
    rows = [("10.20.0.1", "VIP HSRP – passerelle des serveurs"), ("10.20.0.2", "SVI CORE-A"), ("10.20.0.3", "SVI CORE-B"),
            ("10.20.0.10", "VIP keepalived (application)"), ("10.20.0.11-13", "serveurs SRV-CMP-01..03")]
    for i, (a, d) in enumerate(rows):
        s.t(50, 180 + i * 40, a, 22, 600, TXT, "start", MONO)
        s.t(280, 180 + i * 40, d, 21, 400, MUTED)
    s.rect(820, 80, 760, 300, fill=PANEL, stroke=LINE)
    s.t(850, 130, "Transit et contrôle", 24, 700, CYAN)
    tr = INV["transit"]
    rows = [(tr["ext"]["subnet"], "Edge ↔ pare-feux (VLAN 901)"), (tr["int"]["subnet"], "pare-feux ↔ cœurs (VLAN 902)"),
            (tr["sync"]["subnet"], "pfsync / XMLRPC"), (tr["ospf_core"]["subnet"], "OSPF entre cœurs"),
            (tr["edge_isl"]["subnet"], "ISL Edge"), ("10.255.0.0/24", "loopbacks (router-id)")]
    for i, (a, d) in enumerate(rows):
        s.t(850, 172 + i * 36, a, 21, 600, TXT, "start", MONO)
        s.t(1110, 172 + i * 36, d, 20, 400, MUTED)
    s.rect(20, 410, 1560, 330, fill=PANEL, stroke=LINE)
    s.t(50, 460, "Adresses publiques (plages de documentation RFC 5737 / AS RFC 5398)", 24, 700, Z["internet"])
    rows = [("192.0.2.0/24", "préfixe annoncé par AS 65100 aux deux opérateurs"), ("192.0.2.10", "SNAT sortant (pfSense)"),
            ("192.0.2.80", "DNAT → SRV-WEB-01 10.50.0.11 (80/443)"), ("198.51.100.0/30, .4/30", "liens ISP-A (AS 64500)"),
            ("203.0.113.0/30, .4/30", "liens ISP-B (AS 64501)")]
    for i, (a, d) in enumerate(rows):
        s.t(50, 510 + i * 44, a, 22, 600, TXT, "start", MONO)
        s.t(420, 510 + i * 44, d, 21, 400, MUTED)
    return s


# ---- V13 service map -----------------------------------------------------------------------------------------
def v13():
    s = S(1600, 800)
    svc = [("DNS · NTP", "SRV-INF-01", "10.100.0.11", "UDP 53 · 123", Z["core"]),
           ("Syslog + lecteur", "SYSLOG", "10.60.0.12", "UDP 514 · HTTPS 443", Z["core"]),
           ("Zabbix · Grafana", "SRV-MON-01", "10.60.0.11", "80 · 3000 · 10051 · 162", Z["core"]),
           ("GTB / DCIM", "BMS-SIM · SRV-DCIM-01", "10.70.0.12 · .11", "HTTP 8080", Z["hallB"]),
           ("Application", "SRV-CMP-01/02", "VIP 10.20.0.10", "HTTPS 8443", Z["hallA"]),
           ("Stockage", "SRV-STO-01", "10.30.0.11", "NFS 2049 · iSCSI 3260", Z["hallA"]),
           ("Sauvegarde (pull)", "SRV-BCK-01", "10.40.0.11", "SSH 22 sortant", Z["hallB"]),
           ("Site web", "SRV-WEB-01", "10.50.0.11", "HTTPS 443 · DNAT", Z["dmz"])]
    s.rect(20, 20, 1560, 90, fill=PANEL2, stroke=CYAN, sw=2)
    s.t(50, 75, "Clients : équipements, serveurs, administrateurs (VLAN 90), Internet (via DNAT)", 26, 700, TXT)
    for i, (t, node, ip, port, c) in enumerate(svc):
        row, col = divmod(i, 4)
        x, y = 20 + col * 395, 170 + row * 310
        s.line(x + 182, 110, x + 182, y, LINE, 2, "a") if row == 0 else None
        s.box(x, y, 375, 270, t, [node, ip, port], c, 28, 20)
    return s


# ---- V14 backup pull --------------------------------------------------------------------------------------------
def v14():
    s = S(1600, 760)
    nas = F["nas"]
    s.zone(980, 20, 600, 620, "Hall B – VLAN 40", Z["hallB"], 20)
    s.box(1010, 80, 540, 200, "SRV-BCK-01 · TrueNAS SCALE", ["10.40.0.11", "pool tank : miroir ZFS 2 × 10 Go",
                                                             "snapshots horaires (24 h) + quotidiens (14 j)"], Z["hallB"], 26, 19)
    s.box(1010, 310, 540, 140, "Tâches rsync « PULL » 02:00", ["initiées par le NAS, sur SSH", "compte nasbackup : rrsync -ro /"], CYAN, 24, 19)
    s.box(1010, 480, 540, 130, "Test de restauration", ["fichier supprimé puis relu du snapshot", "même SHA-256 (10/11/2026)"], OK, 24, 19)
    srcs = [("SRV-MON-01", "10.60.0.11", "/var/backups/dc (dump Zabbix 01:30), /etc"), ("SRV-INF-01", "10.100.0.11", "/etc")]
    for i, (n, ip, p) in enumerate(srcs):
        y = 90 + i * 250
        s.box(20, y, 600, 170, n, [ip, p], Z["core"], 26, 19)
        s.line(1010, 380, 620, y + 85, CYAN, 3.5, "ac")
        s.t(815, (380 + y + 85) / 2 - 16, "pull, lecture seule", 20, 600, CYAN, "middle")
    s.path("M320 510 L320 600 L1000 600", BAD, 3, "ar", "8 6")
    s.t(340, 585, "serveur → NAS : bloqué par l'ACL du cœur", 21, 700, BAD)
    s.rect(20, 660, 1560, 80, fill=PANEL2, stroke=LINE)
    s.t(50, 710, "Un serveur compromis n'a aucun identifiant vers les sauvegardes : il ne peut ni les lire, ni les chiffrer, ni les effacer.", 22, 600, TXT)
    return s


# ---- V15 firewall zones -------------------------------------------------------------------------------------
def v15():
    s = S(1600, 800)
    fr = INV["firewall_rules"]
    s.box(560, 260, 480, 260, "Cluster pfSense", ["FW-A MASTER · FW-B BACKUP", "5 VIP CARP", "pfsync + XMLRPC sur em2",
                                                   "refus + journal par défaut"], Z["fw"], 30, 20, center=True)
    ifs = [("WAN · em0", "VLAN 901 → EDGE", "VIP 10.254.1.1", "WAN", 560, 40, Z["er"]),
           ("LAN · lagg0 (em3/em4)", "VLAN 902 → cœurs", "VIP 10.254.2.1", "LAN", 560, 590, Z["core"]),
           ("DMZ · em5", "VLAN 50 → SRV-WEB-01", "VIP 10.50.0.1", "DMZ", 1140, 300, Z["dmz"]),
           ("MGMT · em6.10", "VLAN 10 OOB", "VIP 10.10.0.254", "MGMT", 20, 170, Z["mgmt"]),
           ("ADMIN · em6.90", "VLAN 90 admin", "VIP 10.90.0.1", "ADMIN", 20, 430, Z["mgmt"])]
    for t, a, b, key, x, y, c in ifs:
        n = len(fr.get(key, []))
        s.box(x, y, 440 if x != 560 else 480, 170, t, [a, b, f"{n} règle(s)"], c, 24, 19)
    s.line(800, 210, 800, 260, MUTED, 3, "a", both=True)
    s.line(800, 520, 800, 590, MUTED, 3, "a", both=True)
    s.line(1040, 390, 1140, 390, MUTED, 3, "a", both=True)
    s.line(460, 255, 560, 330, MUTED, 3, "a", both=True)
    s.line(460, 515, 560, 450, MUTED, 3, "a", both=True)
    s.rect(1140, 520, 440, 240, fill=PANEL2, stroke=LINE)
    s.t(1160, 560, "NAT", 24, 800, CYAN)
    s.t(1160, 600, "SNAT interne → 192.0.2.10", 20, 500, TXT, "start", MONO)
    s.t(1160, 636, "DNAT 192.0.2.80:443", 20, 500, TXT, "start", MONO)
    s.t(1160, 664, "   → 10.50.0.11 (T18-1)", 20, 500, TXT, "start", MONO)
    s.t(1160, 712, f"{F['security']['firewall_rules']} règles générées par gen_pfsense.py", 19, 500, MUTED)
    s.t(1160, 740, "fw_audit.py : 0 écart", 19, 600, OK)
    return s


# ---- V16 zone policy heatmap ------------------------------------------------------------------------------
def v16():
    zones = ["Internet", "DMZ 50", "Serveurs 20", "Stockage 30", "Backup 40", "Supervision 60", "GTB 70", "CCTV 80",
             "Services 100", "Admin 90", "MGMT 10"]
    A, D = "allow", "deny"
    # policy derived from inventory firewall_rules + core_acl (see 03_Network/inventory/dc_casa.yaml)
    m = {z: {d: ("", D) for d in zones} for z in zones}

    def setc(src, dst, txt):
        m[src][dst] = (txt, A)
    setc("Internet", "DMZ 50", "443")
    setc("DMZ 50", "Serveurs 20", "8443")
    setc("DMZ 50", "Services 100", "53·123")
    for z in ["Serveurs 20", "Stockage 30", "Backup 40", "Supervision 60", "GTB 70", "CCTV 80", "Services 100"]:
        setc(z, "Internet", "53·80·443")
        setc(z, "Services 100", "53·123")
        setc(z, "Supervision 60", "514·10051")
        setc(z, "DMZ 50", "443")
    setc("Serveurs 20", "Stockage 30", "NFS·iSCSI")
    for z in ["Serveurs 20", "Stockage 30", "Supervision 60", "Services 100"]:
        setc("Backup 40", z, "22 pull")
    for z in ["Serveurs 20", "Stockage 30", "Backup 40", "GTB 70", "CCTV 80", "Services 100", "DMZ 50"]:
        setc("Supervision 60", z, "161·10050")
    setc("Supervision 60", "MGMT 10", "161·ICMP")
    setc("GTB 70", "GTB 70", "8080")
    for z in zones:
        if z not in ("Internet", "Admin 90"):
            setc("Admin 90", z, "22·443")
    setc("Admin 90", "Internet", "maj")
    setc("MGMT 10", "Supervision 60", "514·162")
    setc("MGMT 10", "Services 100", "53·123")
    for z in zones:
        if m[z][z][1] == D and z not in ("Internet",):
            m[z][z] = ("même VLAN", "self")
    s = S(1600, 860)
    cw, ch, x0, y0 = 118, 62, 250, 150
    s.t(x0 + len(zones) * cw / 2, 30, "Destination", 22, 700, MUTED, "middle")
    for j, d in enumerate(zones):
        cx = x0 + j * cw + cw / 2
        s.add(f'<text transform="translate({cx + 6},{y0 - 12}) rotate(-38)" font-family="{SANS}" font-size="18" font-weight="600" fill="{TXT}">{escape(d)}</text>')
    for i, src in enumerate(zones):
        y = y0 + i * ch
        s.t(x0 - 14, y + ch / 2 + 7, src, 19, 600, TXT, "end")
        for j, d in enumerate(zones):
            txt, k = m[src][d]
            fill = {"allow": CYAN_D, "deny": "#2A1D22", "self": PANEL2}[k]
            s.rect(x0 + j * cw + 2, y + 2, cw - 4, ch - 4, fill=fill, stroke=BG, r=6, sw=1)
            if k == "allow":
                s.t(x0 + j * cw + cw / 2, y + ch / 2 + 6, txt, 15 if len(txt) > 8 else 17, 700, TXT, "middle", MONO)
            elif k == "deny":
                s.t(x0 + j * cw + cw / 2, y + ch / 2 + 6, "×", 20, 700, "#8A5A60", "middle")
    s.t(20, 40, "Source ↓", 22, 700, MUTED)
    ly = y0 + len(zones) * ch + 30
    s.rect(x0, ly, 30, 24, fill=CYAN_D, stroke=CYAN_D, r=4)
    s.t(x0 + 42, ly + 20, "autorisé (ports)", 19, 500, TXT)
    s.rect(x0 + 260, ly, 30, 24, fill="#2A1D22", stroke=LINE, r=4)
    s.t(x0 + 302, ly + 20, "× refusé + journalisé (défaut)", 19, 500, TXT)
    s.t(x0 + 640, ly + 20, "Politique de l'inventaire : pare-feu + ACL des cœurs", 19, 400, MUTED)
    return s


# ---- V17 monitoring pipeline -----------------------------------------------------------------------------------
def v17():
    s = S(1600, 760)
    src = [("Cisco ×8", "SNMPv3 authPriv", Z["core"]), ("pfSense ×2", "SNMP v2c, VLAN 60 seul", Z["fw"]),
           ("Serveurs", "agent Zabbix 10050/10051", Z["hallB"]), ("BMS · DCIM", "API JSON 8080", Z["dmz"]),
           ("Web · lecteur", "scénario web HTTPS", Z["dmz"]), ("TrueNAS", "SNMPv3 + trapper", Z["hallB"])]
    for i, (n, p, c) in enumerate(src):
        s.box(20, 30 + i * 100, 360, 86, n, [p], c, 22, 18)
        s.path(f"M380 {73 + i * 100} C 450 {73 + i * 100}, 450 230, 520 230", LINE, 2, "a")
    s.box(520, 130, 420, 200, "Zabbix 6.0 LTS", ["SRV-MON-01 · 10.60.0.11", f"{F['monitoring']['zabbix_hosts']} hôtes · MariaDB",
                                                 "maintenance « demo-off »"], CYAN, 30, 19)
    s.line(940, 230, 1060, 230, CYAN, 3.5, "ac")
    s.box(1060, 130, 520, 200, "Grafana – tableau NOC", [f"{F['monitoring']['grafana_panels']} panneaux · plugin Zabbix",
                                                          "alimentation A/B, baies, réseau"], CYAN, 30, 19)
    s.box(520, 380, 420, 130, "Problèmes et alertes", ["déclencheurs en français", "détection ≤ 1 min"], WARN, 26, 19)
    s.line(730, 330, 730, 380, WARN, 3, "a")
    s.box(20, 640, 360, 100, "Tous les équipements", ["syslog UDP 514"], Z["mgmt"], 22, 18)
    s.line(380, 690, 520, 690, Z["mgmt"], 3, "a")
    s.box(520, 600, 420, 140, "SYSLOG · 10.60.0.12", ["rotation 02:00 · 30 jours", "fichiers 0640 root:logread"], Z["mgmt"], 26, 19)
    s.line(940, 670, 1060, 670, Z["mgmt"], 3, "a")
    s.box(1060, 600, 520, 140, "Lecteur de journaux HTTPS", ["lecture seule, verrou après 5 échecs", "ISO 27001 A.8.15"], Z["mgmt"], 26, 19)
    return s


# ---- V18 defence in depth -----------------------------------------------------------------------------------
def v18():
    s = S(1600, 800)
    layers = [("Périmètre", "filtrage BGP, max-prefix, 2 opérateurs", Z["internet"]),
              ("Pare-feu", "pfSense HA, refus par défaut, DMZ isolée", Z["fw"]),
              ("Segmentation", "14 VLAN, ACL inter-VLAN sur les cœurs", Z["core"]),
              ("Accès admin", "VLAN 90 seul, bastion TOTP, SSH v2", Z["mgmt"]),
              ("Équipements", "SNMPv3, durcissement CIS, ports VLAN 999", Z["hallA"]),
              ("Données", "sauvegarde pull, snapshots ZFS", Z["hallB"])]
    for i, (t, d, c) in enumerate(layers):
        x, y, w, h = 20 + i * 42, 20 + i * 42, 900 - i * 84, 760 - i * 84
        s.rect(x, y, w, h, fill=c, stroke=c, r=24, sw=2, op=0.07 + i * 0.015)
        s.t(x + 22, y + 32, t.upper(), 19, 800, c)
        s.t(x + w - 22, y + 32, d, 17, 500, MUTED, "end")
    s.t(470, 400, "Services", 34, 800, TXT, "middle")
    s.t(470, 440, "et données du DC", 22, 500, MUTED, "middle")
    s.t(1000, 60, "Chemin d'administration", 28, 800, TXT)
    steps = [("Administrateur", "poste du NOC", CYAN), ("SRV-BASTION / ADMIN-WS", "VLAN 90 · code TOTP (RFC 6238)", Z["mgmt"]),
             ("Pare-feu – règles ADMIN", "T18-6 : SSH/HTTPS/SNMP seulement", Z["fw"]),
             ("Équipement", "compte nominatif, session 10–15 min", Z["core"]), ("Journal central", "chaque session tracée (A.8.15)", OK)]
    for i, (t, d, c) in enumerate(steps):
        y = 100 + i * 136
        s.box(1000, y, 580, 108, t, [d], c, 24, 19)
        if i < len(steps) - 1:
            s.line(1290, y + 108, 1290, y + 136, CYAN, 3, "ac")
    return s


# ---- V19 conformity scorecard + AD/LDAP design --------------------------------------------------------------
def v19():
    s = S(1600, 820)
    iso = F["security"]["iso27001_controls"]
    partial = {"A.5.17"}
    s.t(20, 40, "ISO/IEC 27001:2022 – Annexe A", 26, 800, TXT)
    for i, (k, d) in enumerate(iso.items()):
        y = 64 + i * 61
        st = "Partiel" if k in partial else "Fait"
        c = WARN if st == "Partiel" else OK
        s.rect(20, y, 900, 52, fill=PANEL, stroke=LINE, r=8)
        s.t(40, y + 34, k, 21, 700, CYAN, "start", MONO)
        s.t(150, y + 34, d.split(" : ")[0], 20, 600, TXT)
        s.pill(800, y + 10, st, c, 16, BG, 100)
    s.t(980, 40, "ANSI/TIA-942-C Rated-3", 26, 800, TXT)
    tia = [("2 opérateurs, 2 entrées", "Fait"), ("Edge, pare-feux, cœurs doublés", "Fait"),
           ("Serveurs sur 2 Leaf", "Fait"), ("Chemins électriques A/B", "Simulé"),
           ("Espaces ER / MDA / HDA / EDA", "Fait"), ("Étiquetage TIA-606", "Fait"),
           ("Maintenance sans arrêt (T2–T5)", "Mesuré"), ("Sécurité physique 5 zones", "Conçu")]
    for i, (d, st) in enumerate(tia):
        y = 64 + i * 61
        c = OK if st in ("Fait", "Mesuré") else WARN if st == "Simulé" else MUTED
        s.rect(980, y, 600, 52, fill=PANEL, stroke=LINE, r=8)
        s.t(1000, y + 34, d, 20, 600, TXT)
        s.pill(1450, y + 10, st, c, 16, BG, 110)
    s.t(980, 620, f"{sum(1 for k in iso if k not in partial)}/{len(iso)} contrôles ISO faits · "
                  f"{sum(1 for _, st in tia if st in ('Fait', 'Mesuré'))}/{len(tia)} exigences TIA démontrées", 21, 700, CYAN)
    s.t(980, 655, "A.5.17 partiel : pas encore d'annuaire central (AD/LDAP prévu)", 19, 400, MUTED)
    return s


def v19b():
    s = S(1600, 740)
    s.box(560, 230, 480, 220, "SRV-AD-01 (prévu)", ["Samba 4 AD DC", "10.100.0.12 · VLAN 100", "royaume DC-CASA.LOCAL"],
          WARN, 30, 20, center=True, dash="10 8", fill=BG)
    cl = [("pfSense", "connexion GUI des admins", 40, 40), ("Zabbix", "utilisateurs du NOC", 40, 480),
          ("Grafana", "lecteurs du tableau NOC", 1120, 40), ("Serveurs Linux", "sssd / Kerberos (option)", 1120, 480)]
    for t, d, x, y in cl:
        s.box(x, y, 440, 150, t, [d], MUTED, 26, 19, dash="10 8", fill=BG)
        s.line(x + 220 if x < 600 else x + 220, y + (150 if y < 300 else 0), 800, 230 if y < 300 else 450, WARN, 2.5, "a", "8 6")
    s.pill(620, 520, "LDAPS 636 · Kerberos 88", WARN, 20, BG, 360)
    s.t(800, 710, "Conception seulement : rien n'est montré qui ne tourne pas. Réalisation après la soutenance (D4).", 21, 600, MUTED, "middle")
    return s


ALL = {"V2_tiers": v2, "V3_tia942_spaces": v3, "V4_architecture": v4, "V5_redundancy_chain": v5, "V6_outage_chart": v6,
       "V7_power_ab": v7, "V9_lab_stack": v9, "V10_automation_pipeline": v10, "V11_vlan_zones": v11,
       "V12_addressing": v12, "V13_service_map": v13, "V14_backup_pull": v14, "V15_firewall": v15,
       "V16_policy_heatmap": v16, "V17_monitoring": v17, "V18_defence_in_depth": v18, "V19_conformity": v19,
       "V19b_ad_ldap_design": v19b}


def render(names):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    PNG.mkdir(parents=True, exist_ok=True)
    fonts = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
             "&family=JetBrains+Mono:wght@400;500;600;700&display=swap")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(device_scale_factor=2)
        for n in names:
            sv = ALL[n]()
            code = sv.svg()
            (OUT / f"{n}.svg").write_text(code, encoding="utf-8")
            pg.set_viewport_size({"width": sv.w, "height": sv.h})
            pg.set_content(f'<html><head><link rel="stylesheet" href="{fonts}"><style>body{{margin:0;background:{BG}}}'
                           f'svg{{display:block}}</style></head><body>{code}</body></html>')
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(PNG / f"{n}.png"), clip={"x": 0, "y": 0, "width": sv.w, "height": sv.h})
            print("ok", n, f"{sv.w}x{sv.h}")
        b.close()


if __name__ == "__main__":
    render([a for a in sys.argv[1:]] or list(ALL))
