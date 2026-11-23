"""Demo video editor (PLAN_05 D7, P6): chapter cards, captions, scene clips and the master video, with ffmpeg.

  python automation/demo_video/edit.py            -> 05_Report/presentation/video/
Inputs: video/raw/<scene>.webm recorded by director.py (live lab) and the Blender drone flythrough.
Cards, captions, thumbnail (C7) and end card (C8) are HTML pages in the deck style (D11), rendered to PNG by Edge.
Outputs: clips/<scene>.mp4 (one per scene, for the slides, < 20 MB), DC_Casablanca_demo.mp4 (master, 1080p30),
thumbnail.png, endcard.png, chapters.txt (start time of each chapter).
"""
import json
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
NET = HERE.parents[1]
ROOT = NET.parent
VID = ROOT / "05_Report" / "presentation" / "video"
RAW, CLIPS, TMP = VID / "raw", VID / "clips", VID / "_tmp"
DRONE = ROOT / "02_Blender" / "04_Renders" / "animation" / "DC_Drone_Flythrough.mp4"
FACTS = json.loads((ROOT / "05_Report" / "presentation" / "facts.json").read_text(encoding="utf-8"))
FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800&family=JetBrains+Mono:wght@500;700&display=swap"

# chapter, scene, caption (French), speed
STORY = [
    ("1 · Topologie", "S1_topology", "Le projet GNS3 en direct : 32 nœuds, zones TIA-942, état lu sur l’API du contrôleur", 1.0),
    ("2 · Réseau", "S3_network", "Commandes réelles depuis ADMIN-WS : eBGP vers 2 opérateurs, HSRP partagé, OSPF, LACP, trunks", 1.0),
    ("3 · Pare-feu", "S4_firewall", "pfSense FW-A : 5 VIP CARP maîtres, règles d’administration, NAT, journal des refus", 1.0),
    ("4 · Services", "S5_services", "Site DMZ joint depuis Internet par le NAT · flux VLAN 60 → administration refusé par l’ACL", 1.0),
    ("5 · Supervision NOC", "S6_noc", "Zabbix (18 hôtes), tableau Grafana du NOC, GTB et DCIM des 96 baies", 1.0),
    ("6 · Panne électrique T6", "S8_T6_power", "Coupure du chemin A : alarme, 96 baies en mode dégradé, chemin B seul actif, puis retour", 1.0),
    ("7 · Panne pare-feu T2", "S8_T2_fw", "Arrêt de FW-A pendant qu’une sonde interroge la GTB toutes les 0,5 s : FW-B prend le relais", 1.0),
    ("8 · Preuve", "S9_proof", "demo_check.py : 12 contrôles automatiques du laboratoire", 1.0),
]

CARD = """<html><head><meta charset="utf-8"><link rel="stylesheet" href="{f}"><style>
html,body{{margin:0;width:1920px;height:1080px;background:{bg};font-family:Inter;overflow:hidden}}
.k{{position:absolute;left:160px;top:380px;width:1600px}} .led{{width:180px;height:7px;background:#3FD0E8;border-radius:4px;box-shadow:0 0 28px rgba(63,208,232,.8)}}
h1{{font-size:{size}px;font-weight:800;color:#E8EEF2;margin:34px 0 18px;letter-spacing:-1px;line-height:1.05}} p{{font-size:34px;color:#A9B8C4;margin:0;line-height:1.4}}
.m{{font-family:'JetBrains Mono';font-size:24px;color:#3FD0E8;letter-spacing:2px;margin-top:26px}}
</style></head><body>{img}<div class="k"><div class="led"></div><h1>{t}</h1><p>{s}</p><p class="m">{m}</p></div></body></html>"""

CAP = """<html><head><meta charset="utf-8"><link rel="stylesheet" href="{f}"><style>
html,body{{margin:0;width:1920px;height:1080px;background:transparent;font-family:Inter}}
.c{{position:absolute;left:60px;right:60px;bottom:44px;background:rgba(11,16,21,.88);border:1px solid #2C3742;border-left:6px solid #3FD0E8;border-radius:12px;padding:18px 28px;display:flex;gap:26px;align-items:center}}
.c b{{font-size:24px;color:#3FD0E8;letter-spacing:2px;text-transform:uppercase;white-space:nowrap}} .c span{{font-size:30px;color:#E8EEF2}}
</style></head><body><div class="c"><b>{ch}</b><span>{cap}</span></div></body></html>"""


def ff(*args):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def render_pngs():
    from playwright.sync_api import sync_playwright
    TMP.mkdir(parents=True, exist_ok=True)
    hero = (ROOT / "02_Blender/04_Renders/stills/01_Hero_SouthEast.png").as_uri()
    bgimg = (f'<img src="{hero}" style="position:absolute;inset:0;width:1920px;height:1080px;object-fit:cover">'
             '<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(10,14,19,.95),rgba(10,14,19,.75) 55%,rgba(10,14,19,.2))"></div>')
    vl = FACTS["tests"]["verify_lab"]
    pages = {
        "title": CARD.format(f=FONTS, bg="#0D1217", size=110, img=bgimg, t="Data Center Casablanca",
                             s="Démonstration du laboratoire GNS3 : réseau, sécurité, supervision et pannes provoquées",
                             m="ANSI/TIA-942 RATED-3 · TOUT CE QUI SUIT EST LE LABO EN DIRECT, ENREGISTRÉ LE 23/11/2026"),
        "thumbnail": CARD.format(f=FONTS, bg="#0D1217", size=120, img=bgimg, t="DC Casablanca<br>démo en direct",
                                 s=f"{FACTS['lab']['nodes']} nœuds GNS3 · pannes provoquées · {vl['pass']}/{vl['pass']} tests",
                                 m="VIDÉO DE DÉMONSTRATION · 8 CHAPITRES"),
        "endcard": CARD.format(f=FONTS, bg="#0D1217", size=96, img=bgimg, t="Tout est réel, tout est rejouable",
                               s=f"verify_lab : {vl['pass']} PASS, {vl['fail']} FAIL · demo_check : 12/12 · bascule pare-feu 3,0 s mesurée",
                               m="SCRIPTS : 03_NETWORK/AUTOMATION · PREUVES : REPORT/EVIDENCE"),
    }
    for ch, _, _, _ in STORY:
        n, t = ch.split(" · ", 1)
        pages[f"card_{n}"] = CARD.format(f=FONTS, bg="#12181F", size=120, img="", t=escape(t), s=f"Chapitre {n}", m="DC CASABLANCA · LABO EN DIRECT")
    for ch, sc, cap, _ in STORY:
        pages[f"cap_{sc}"] = CAP.format(f=FONTS, ch=escape(ch.split(" · ", 1)[1]), cap=escape(cap))
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for name, html in pages.items():
            f = TMP / f"{name}.html"
            f.write_text(html, encoding="utf-8")
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(400)
            pg.screenshot(path=str(TMP / f"{name}.png"), omit_background=name.startswith("cap_"))
        b.close()
    (VID / "thumbnail.png").write_bytes((TMP / "thumbnail.png").read_bytes())
    (VID / "endcard.png").write_bytes((TMP / "endcard.png").read_bytes())


ENC = ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30"]


def still(png, seconds, out):
    ff("-loop", "1", "-t", str(seconds), "-i", str(png), "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo",
       "-vf", f"fade=in:0:12,fade=out:st={seconds - 0.4}:d=0.4,format=yuv420p", *ENC, "-crf", "18", "-c:a", "aac", "-shortest", str(out))


def main():
    CLIPS.mkdir(parents=True, exist_ok=True)
    render_pngs()
    parts, chapters, t = [], [], 0.0
    # S0: drone flythrough with the title over it
    s0 = TMP / "s0.mp4"
    ff("-i", str(DRONE), "-loop", "1", "-i", str(TMP / "title.png"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
       "-filter_complex", "[0:v]scale=1920:1080,fps=30,trim=0:20,setpts=PTS-STARTPTS[v];[1:v]format=rgba,colorchannelmixer=aa=0.92[t];"
       "[v][t]overlay=0:0:enable='between(t,1.5,20)',fade=in:0:15,fade=out:st=19.4:d=0.6[o]",
       "-map", "[o]", "-map", "2:a", "-t", "20", *ENC, "-crf", "18", "-c:a", "aac", "-shortest", str(s0))
    parts.append(s0)
    chapters.append(("0:00", "Ouverture – campus en 3D (Blender)"))
    t += dur(s0)
    for i, (ch, sc, cap, speed) in enumerate(STORY):
        src = RAW / f"{sc}.webm"
        if not src.exists():
            print("   missing", src.name, "- skipped")
            continue
        n = ch.split(" · ", 1)[0]
        card = TMP / f"card_{n}.mp4"
        still(TMP / f"card_{n}.png", 2.5, card)
        body = TMP / f"{sc}.mp4"
        d = dur(src) / speed
        ff("-i", str(src), "-loop", "1", "-i", str(TMP / f"cap_{sc}.png"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", f"[0:v]setpts=PTS/{speed},scale=1920:1080,fps=30[v];[1:v]format=rgba,fade=out:st=6.5:d=0.6:alpha=1[c];"
                              f"[v][c]overlay=0:0:shortest=1:enable='lt(t,7.2)',"
                              f"fade=in:0:9,fade=out:st={max(0.1, d - 0.4):.2f}:d=0.4[o]",
           "-map", "[o]", "-map", "2:a", "-t", f"{d:.2f}", *ENC, "-crf", "19", "-c:a", "aac", "-shortest", str(body))
        clip = CLIPS / f"{sc}.mp4"
        ff("-i", str(body), "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip))
        m, s = divmod(int(t), 60)
        chapters.append((f"{m}:{s:02d}", ch))
        parts += [card, body]
        t += dur(card) + dur(body)
        print(f"   {ch}: {d:.0f} s, clip {clip.stat().st_size / 1e6:.1f} MB", flush=True)
    end = TMP / "end.mp4"
    still(TMP / "endcard.png", 5, end)
    parts.append(end)
    lst = TMP / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    master = VID / "DC_Casablanca_demo.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-movflags", "+faststart", str(master))
    (VID / "chapters.txt").write_text("".join(f"{a}  {b}\n" for a, b in chapters), encoding="utf-8")
    print(f"master {master.name}: {dur(master) / 60:.1f} min, {master.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
