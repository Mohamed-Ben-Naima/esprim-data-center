"""Assembly of the live walkthrough (PLAN_06 P6): long cut + jury cut, voiceover, burned-in subtitles, .srt.

  python automation/demo_video/edit2.py [long|jury|both] [--only id,id] [--cards]
Inputs: video/raw2/<rec>.webm + <rec>.json (marks = narration ids, walkthrough.py), video/vo/<id>.mp3 (voice.py),
narration.yaml. For each segment: the raw picture between its mark and the next narration mark of the same
recording is fitted to its voiceover (speed 0.75-2x, else freeze the last frame / let the picture run on);
timelapse segments (speed: auto) are compressed to the voice and get a "x N" badge; split recordings (A0) are
hstacked. Each segment carries an ASS file: subtitles = the spoken text in chunks of <= 2 lines, timed on the voice,
plus a top-left node badge (node / role / test). Every segment is encoded alone (BelowNormal priority, same codec
settings) and the cut is a concat -c copy (a single big encode was OOM-killed in PLAN_05).
Outputs (05_Report/presentation/video/): DC_Casablanca_walkthrough.mp4 (+ .srt, _chapters.txt),
DC_Casablanca_demo_5min.mp4 (+ .srt, _chapters.txt), clips_v2/<id>.mp4, thumbnail_v2.png.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from html import escape
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
NET = HERE.parents[1]
ROOT = NET.parent
VID = ROOT / "05_Report" / "presentation" / "video"
RAW, RAW2, VO, CLIPS, TMP = VID / "raw", VID / "raw2", VID / "vo", VID / "clips_v2", VID / "_tmp2"
FACTS = json.loads((ROOT / "05_Report" / "presentation" / "facts.json").read_text(encoding="utf-8"))
SEGS = yaml.safe_load((HERE / "narration.yaml").read_text(encoding="utf-8"))["segments"]
IDS = {s["id"] for s in SEGS}
SPLIT = {"A0": ("A0_left_gns3", "A0_right_labup")}
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
PAD_BEFORE, PAD_AFTER = 0.35, 0.9          # silence around each voice line (s)
ACT_TITLES = {0: "Acte 0 · Démarrage à froid", 1: "Acte 1 · Réseau, sécurité, services, SOC",
              "1b": "Acte 1b · Supervision NOC et pannes (prises du 23/11)",
              2: "Acte 2 · Calcul", 3: "Acte 3 · Stockage et sauvegarde"}


def ff(args, cwd=None):
    for attempt in range(2):
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, cwd=cwd,
                           creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        if not r.returncode:
            return
        time.sleep(3)
    raise RuntimeError(r.stderr[-2000:])


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def texts():
    return json.loads((VO / "texts.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ subtitles
def chunks(text, width=42, lines=2):
    """Split a spoken text into subtitle cues of <= `lines` lines of <= `width` chars, cutting at punctuation first."""
    words, cues, cur = text.split(), [], ""
    limit = width * lines
    for w in words:
        nxt = (cur + " " + w).strip()
        if len(nxt) > limit:
            cues.append(cur)
            cur = w
        else:
            cur = nxt
            if re.search(r"[.!?:]$", w) and len(cur) > limit * 0.45:
                cues.append(cur)
                cur = ""
    if cur:
        cues.append(cur)
    return cues


def wrap2(cue, width=42):
    """Two balanced lines."""
    if len(cue) <= width:
        return [cue]
    words = cue.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b))
        if best is None or score < best[0]:
            best = (score, a, b)
    return [best[1], best[2]]


def timed(text, start, length):
    """[(t0, t1, lines)] cues spread over the voice length in proportion to their characters."""
    cs = chunks(text)
    total = sum(len(c) for c in cs) or 1
    out, t = [], start
    for c in cs:
        d = length * len(c) / total
        out.append((t, t + d, wrap2(c)))
        t += d
    return out


def ts_ass(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def ts_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter,44,&H00FFFFFF,&H00FFFFFF,&HC0150F0B,&HC0150F0B,-1,0,0,0,100,100,0,0,3,14,0,2,120,120,46,1
Style: Node,Inter,40,&H00E8D03F,&H00FFFFFF,&H00150F0B,&H30150F0B,-1,0,0,0,100,100,0,0,3,16,0,7,36,36,30,1
Style: Info,Inter,28,&H00F2EEE8,&H00FFFFFF,&H00150F0B,&H30150F0B,0,0,0,0,100,100,0,0,3,12,0,7,36,36,30,1
Style: Badge,JetBrains Mono,44,&H0000D4FF,&H00FFFFFF,&H00150F0B,&H40150F0B,-1,0,0,0,100,100,0,0,3,14,0,9,36,36,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_text(s):
    return s.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(path, cues, length, seg, badge=None):
    ev = []
    for t0, t1, lines in cues:
        ev.append(f"Dialogue: 0,{ts_ass(t0)},{ts_ass(t1)},Sub,,0,0,0,,{ass_text(chr(10).join(lines))}")
    if seg.get("node"):
        ev.append(f"Dialogue: 1,{ts_ass(0)},{ts_ass(length)},Node,,0,0,0,,{ass_text(seg['node'])}")
        info = []
        if seg.get("role"):
            info.append(f"Rôle · {seg['role']}")
        if seg.get("test"):
            info.append(f"Test · {seg['test']}")
        if info:
            ev.append(f"Dialogue: 1,{ts_ass(0)},{ts_ass(length)},Info,,0,0,92,,{ass_text(chr(10).join(info))}")
    if badge:
        ev.append(f"Dialogue: 2,{ts_ass(0)},{ts_ass(length)},Badge,,0,0,0,,{ass_text(badge)}")
    path.write_text(ASS_HEAD + "\n".join(ev) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ cards
CARD = """<html><head><meta charset="utf-8"><style>
@font-face{{font-family:Inter;src:url('{fonts}/Inter-Medium.ttf');font-weight:500}}
@font-face{{font-family:Inter;src:url('{fonts}/Inter-Bold.ttf');font-weight:700}}
@font-face{{font-family:Inter;src:url('{fonts}/Inter-ExtraBold.ttf');font-weight:800}}
@font-face{{font-family:JBM;src:url('{fonts}/JetBrainsMono-Medium.ttf')}}
html,body{{margin:0;width:1920px;height:1080px;background:#0D1217;font-family:Inter;overflow:hidden}}
.k{{position:absolute;left:160px;top:360px;width:1600px}} .led{{width:180px;height:7px;background:#3FD0E8;border-radius:4px;box-shadow:0 0 28px rgba(63,208,232,.8)}}
h1{{font-size:{size}px;font-weight:800;color:#E8EEF2;margin:34px 0 18px;letter-spacing:-1px;line-height:1.05}} p{{font-size:34px;color:#A9B8C4;margin:0;line-height:1.4}}
.m{{font-family:JBM;font-size:24px;color:#3FD0E8;letter-spacing:2px;margin-top:26px}}
</style></head><body>{img}<div class="k"><div class="led"></div><h1>{t}</h1><p>{s}</p><p class="m">{m}</p></div></body></html>"""


def render_cards():
    from playwright.sync_api import sync_playwright
    TMP.mkdir(parents=True, exist_ok=True)
    fonts = (HERE / "fonts").as_uri()
    hero = ROOT / "02_Blender/04_Renders/stills/01_Hero_SouthEast.png"
    bgimg = (f'<img src="{hero.as_uri()}" style="position:absolute;inset:0;width:1920px;height:1080px;object-fit:cover">'
             '<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(10,14,19,.95),rgba(10,14,19,.75) 55%,rgba(10,14,19,.2))"></div>'
             if hero.exists() else "")
    vl = FACTS["tests"]["verify_lab"]
    lab = FACTS["lab"]
    pages = {
        "title": dict(size=110, img=bgimg, t="Data Center Casablanca",
                      s="Visite du laboratoire GNS3 en direct : chaque machine, son rôle, son test, son résultat",
                      m="ANSI/TIA-942 RATED-3 · LABO EN DIRECT · ENREGISTRÉ LE 23/11/2026"),
        "thumbnail_v2": dict(size=120, img=bgimg, t="DC Casablanca<br>visite en direct",
                             s=f"{lab['nodes']} nœuds GNS3 · démarrage à froid · pannes provoquées · voix off",
                             m="GNS3 · PFSENSE · ZABBIX/GRAFANA · TRUENAS"),
        "end": dict(size=96, img=bgimg, t="Tout est réel, tout est rejouable",
                    s=f"verify_lab : {vl['pass']} PASS, {vl['fail']} FAIL · configurations générées depuis l’inventaire",
                    m="SCRIPTS : 03_NETWORK/AUTOMATION · PREUVES : REPORT/EVIDENCE"),
    }
    for a, t in ACT_TITLES.items():
        pages[f"act{a}"] = dict(size=104, img="", t=escape(t.split(" · ", 1)[1]), s=escape(t.split(" · ", 1)[0]),
                                m="DC CASABLANCA · LABO GNS3 EN DIRECT")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for name, kw in pages.items():
            f = TMP / f"{name}.html"
            f.write_text(CARD.format(fonts=fonts, **kw), encoding="utf-8")
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(TMP / f"{name}.png"))
        b.close()
    shutil.copy(TMP / "thumbnail_v2.png", VID / "thumbnail_v2.png")


# ------------------------------------------------------------------------------------------------ segments
def rdir(seg):
    return RAW if seg.get("src") == "raw" else RAW2


def marks(rec, base=None):
    d = json.loads(((base or RAW2) / f"{rec}.json").read_text(encoding="utf-8"))
    off = d["t0"] - d["vstart"] if "vstart" in d and "t0" in d else 0.0   # mark times are relative to t0
    return [(m["t"] + off, m["label"]) for m in d["marks"]]


def span(seg):
    """(rec files, start, end) of the raw picture of a segment."""
    rec = seg["rec"]
    files = SPLIT.get(rec, (rec,))
    ms = marks(files[-1] if rec in SPLIT else rec, rdir(seg))
    start = next(t for t, l in ms if l == seg["mark"])
    stop_label = seg.get("until")
    end = None
    for t, l in ms:
        if t <= start:
            continue
        if (stop_label and l == stop_label) or (not stop_label and l in IDS and l != seg["mark"]):
            end = t
            break
    if end is None:
        end = dur(rdir(seg) / f"{files[0]}.webm") - 0.3
    return files, start, end


def own_span(rec, seg):
    ms = marks(rec)
    a = next(t for t, l in ms if l == seg["mark"])
    b = next((t for t, l in ms if t > a and l == seg.get("until")), dur(RAW2 / f"{rec}.webm") - 0.3)
    return a, b


def silence(seconds, out):
    ff(["-f", "lavfi", "-t", f"{seconds:.3f}", "-i", "anullsrc=r=48000:cl=stereo", "-c:a", "pcm_s16le", str(out)])


def voice_track(key, total, out):
    """Voice delayed by PAD_BEFORE, padded with silence to `total`, loudness -16 LUFS."""
    ff(["-i", str(VO / f"{key}.mp3"), "-af",
        f"adelay={int(PAD_BEFORE * 1000)}:all=1,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad=whole_dur={total:.3f}",
        "-t", f"{total:.3f}", "-ac", "2", "-c:a", "pcm_s16le", str(out)])


def build_segment(seg, cut, out):
    key = seg["id"] + ("_jury" if cut == "jury" and "jury_vo" in seg else "")
    text = texts()[key]
    vo_len = dur(VO / f"{key}.mp3")
    T = PAD_BEFORE + vo_len + PAD_AFTER
    TMP.mkdir(parents=True, exist_ok=True)
    fontdir = TMP / "fonts"
    if not fontdir.exists():
        shutil.copytree(HERE / "fonts", fontdir)
    wav = TMP / f"{key}.wav"
    badge = None
    if seg.get("card"):
        png = TMP / f"{seg['card']}.png"
        cues = timed(text, PAD_BEFORE, vo_len)
        T = max(T, 4.0)
        voice_track(key, T, wav)
        write_ass(TMP / "seg.ass", cues, T, {})
        ff(["-loop", "1", "-t", f"{T:.3f}", "-i", str(png), "-i", str(wav), "-vf",
            f"subtitles=seg.ass:fontsdir=fonts,fade=in:0:12,fade=out:st={T - 0.5:.3f}:d=0.5,format=yuv420p",
            *ENC, "-shortest", str(out)], cwd=TMP)
        return T
    if seg.get("still"):     # a real screenshot of the same live run, slow zoom (Ken Burns)
        img = ROOT / seg["still"]
        T = max(T, 5.0)
        voice_track(key, T, wav)
        write_ass(TMP / "seg.ass", timed(text, PAD_BEFORE, vo_len), T, seg)
        n = int(T * 30)
        ff(["-i", str(img), "-i", str(wav), "-vf",
            f"scale=3840:-2,zoompan=z='min(1+0.10*on/{n},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1920x1080:fps=30,"
            "subtitles=seg.ass:fontsdir=fonts,format=yuv420p", *ENC, "-t", f"{T:.3f}", str(out)], cwd=TMP)
        return T
    files, a, b = span(seg)
    L = max(0.5, b - a)
    if seg.get("speed") == "auto":
        k = max(1.0, L / (T - 0.2))
        vf_speed = f"setpts=(PTS-STARTPTS)/{k:.4f}"
        if k > 1.3:
            badge = f"×{k:.0f}" if k >= 3 else f"×{k:.1f}".replace(".", ",")
        V = L / k
    else:
        k = L / T
        lim = 2.0 if cut == "jury" else 1.5
        if k > lim:          # picture longer than the voice: speed up to the limit, the picture runs on after the voice
            k = lim
        elif k < 0.75:        # picture shorter: slow down a little, then freeze the last frame
            k = 0.75 if L / 0.75 < T else k
        vf_speed = f"setpts=(PTS-STARTPTS)/{k:.4f}"
        V = L / k
    total = max(T, V)
    if total > V + 0.05:
        vf_speed += f",tpad=stop_mode=clone:stop_duration={total - V + 0.2:.3f}"
    voice_track(key, total, wav)
    cues = timed(text, PAD_BEFORE, vo_len)
    write_ass(TMP / "seg.ass", cues, total, seg, badge)
    ins = []
    for f in files:
        ins += ["-ss", f"{a:.3f}", "-t", f"{L:.3f}", "-i", str(rdir(seg) / f"{f}.webm")]
    ins += ["-i", str(wav)]
    if len(files) == 2:
        # each half has its own length (variable-rate recordings): both are fitted to the same output length V
        a2, b2 = own_span(files[0], seg)
        ins[0:6] = ["-ss", f"{a2:.3f}", "-t", f"{b2 - a2:.3f}", "-i", str(RAW2 / f"{files[0]}.webm")]
        vf_l = vf_speed.replace(f"/{k:.4f}", f"/{(b2 - a2) / V:.4f}", 1)
        fc = (f"[0:v]fps=30,{vf_l},scale=960:1080[l];[1:v]fps=30,{vf_speed},scale=960:1080[r];"
              f"[l][r]hstack=inputs=2,subtitles=seg.ass:fontsdir=fonts,format=yuv420p[v]")
        amap = "2:a"
    else:
        fc = (f"[0:v]fps=30,{vf_speed},scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
              f"subtitles=seg.ass:fontsdir=fonts,format=yuv420p[v]")
        amap = "1:a"
    ff([*ins, "-filter_complex", fc, "-map", "[v]", "-map", amap, "-t", f"{total:.3f}", *ENC, str(out)], cwd=TMP)
    return total


def act_card(act, out):
    png = TMP / f"act{act}.png"
    ff(["-loop", "1", "-t", "2.6", "-i", str(png), "-f", "lavfi", "-t", "2.6", "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", "fade=in:0:10,fade=out:st=2.1:d=0.5,format=yuv420p", *ENC, "-shortest", str(out)])
    return 2.6


def build(cut, only=None):
    CLIPS.mkdir(parents=True, exist_ok=True)
    parts, srt, chapters, t, last_act = [], [], [], 0.0, None
    sel = [s for s in SEGS if (cut == "long" or s.get("jury")) and (s["id"] + ("_jury" if cut == "jury" and "jury_vo" in s else "")) in texts()]
    for s in sel:
        if s.get("rec") and not (rdir(s) / f"{SPLIT.get(s['rec'], (s['rec'],))[0]}.webm").exists():
            print(f"   {s['id']}: recording {s['rec']} missing, skipped", flush=True)
            continue
        if cut == "long" and s["act"] in ACT_TITLES and s["act"] != last_act:
            out = CLIPS / f"_act{s['act']}.mp4"
            if not out.exists():
                act_card(s["act"], out)
            chapters.append((t, ACT_TITLES[s["act"]]))
            parts.append(out)
            t += dur(out)
            last_act = s["act"]
        out = CLIPS / f"{s['id']}{'_jury' if cut == 'jury' else ''}.mp4"
        if only is None or s["id"] in only or not out.exists():
            print(time.strftime("%H:%M:%S"), cut, s["id"], flush=True)
            build_segment(s, cut, out)
        d = dur(out)
        key = s["id"] + ("_jury" if cut == "jury" and "jury_vo" in s else "")
        vo_len = dur(VO / f"{key}.mp3")
        for c0, c1, lines in timed(texts()[key], t + PAD_BEFORE, vo_len):
            srt.append((c0, c1, lines))
        if cut == "jury" or s.get("node"):
            chapters.append((t, s.get("node") or s["id"]))
        parts.append(out)
        t += d
    name = "DC_Casablanca_walkthrough" if cut == "long" else "DC_Casablanca_demo_5min"
    lst = TMP / f"{cut}_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    final = VID / f"{name}.mp4"
    ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])
    (VID / f"{name}.srt").write_text("".join(f"{i}\n{ts_srt(a)} --> {ts_srt(b)}\n" + "\n".join(l) + "\n\n"
                                             for i, (a, b, l) in enumerate(srt, 1)), encoding="utf-8")
    (VID / f"{name}_chapters.txt").write_text("".join(f"{int(a // 60)}:{int(a % 60):02d} {c}\n" for a, c in chapters),
                                               encoding="utf-8")
    print(f"{final.name}: {dur(final):.1f} s, {len(parts)} parts, {len(srt)} cues", flush=True)


def main(argv):
    cuts = ["long", "jury"] if not argv or argv[0] in ("both", "--only", "--cards") else [argv[0]]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    if "--cards" in argv or not (TMP / "title.png").exists():
        render_cards()
    for c in cuts:
        build(c, only)


if __name__ == "__main__":
    main(sys.argv[1:])
