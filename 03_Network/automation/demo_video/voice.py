"""French voiceover for the walkthrough (PLAN_06 P2): narration.yaml -> one mp3 per segment + durations.json.

  python automation/demo_video/voice.py [--only id,id] [--force]
Voice: edge-tts fr-FR-HenriNeural, rate -5 % (online). Fallback when edge-tts fails: the offline Windows voice
"Microsoft Hortense Desktop" (System.Speech) -> wav -> mp3.
`{placeholders}` are filled from video/raw2/values.json (live results written by walkthrough.py); a segment whose
placeholders are not known yet is skipped (re-run after the recording).
The text shown in the subtitles is the `vo` text itself; PRON only changes what the voice reads.
Outputs: video/vo/<id>.mp3 and <id>_jury.mp3 (when jury_vo), video/vo/durations.json, video/vo/texts.json.
"""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VID = ROOT / "05_Report" / "presentation" / "video"
VO = VID / "vo"
VALUES = VID / "raw2" / "values.json"
VOICE, RATE = "fr-FR-HenriNeural", "-5%"

# what the voice reads instead of the written form (subtitles keep the written form)
PRON = [
    (r"\bGNS3\b", "GNS 3"), (r"\bpfSense\b", "pf Sense"), (r"\bpfsync\b", "pf sync"), (r"\beBGP\b", "e B G P"),
    (r"\blab_up\.py\b", "lab up"), (r"\blab_up\b", "lab up"), (r"\bdemo_check\b", "démo check"),
    (r"\bverify_lab\b", "vérifie lab"), (r"\blog_viewer\.py\b", "log viewer"), (r"\bADMIN-WS\b", "admin W S"),
    (r"\bCORE-A\b", "core A"), (r"\bCORE-B\b", "core B"), (r"\bEDGE-A\b", "edge A"), (r"\bLEAF-B1\b", "leaf B 1"),
    (r"\bLEAF-A1\b", "leaf A 1"), (r"\bLEAF-A2\b", "leaf A 2"), (r"\bFW-A\b", "F W A"), (r"\bFW-B\b", "F W B"),
    (r"\bISP-A\b", "I S P A"), (r"\bSRV-WEB-01\b", "le serveur web 01"), (r"\bSRV-MON-01\b", "le serveur mon 01"),
    (r"\bSRV-CMP-01\b", "C M P 01"), (r"\bSRV-CMP-02\b", "C M P 02"), (r"\bSRV-BCK-01\b", "B C K 01"),
    (r"\bSYSLOG\b", "syslog"), (r"\bGTB\b", "G T B"), (r"\bDCIM\b", "D C I M"), (r"\bNOC\b", "nok"),
    (r"\bSOC\b", "sok"), (r"\bVIP\b", "V I P"), (r"\bNAS\b", "nasse"), (r"\bPUE\b", "P U E"),
    (r"\bAS (\d)", r"A S \1"), (r"192\.0\.2\.80", "192 point 0 point 2 point 80"),
    (r"10\.90\.0\.12", "10 point 90 point 0 point 12"), (r"10\.20\.0\.10", "10 point 20 point 0 point 10"),
    (r"\b15,7 Go\b", "15,7 gigaoctets"), (r"\b3 Go\b", "3 gigaoctets"), (r"\bRated-3\b", "Rated 3"),
    (r"\bTIA-942\b", "T I A 942"), (r"\bWAN\b", "ouane"), (r"\bVLAN\b", "V LAN"), (r"\bHSRP\b", "H S R P"),
    (r"\bOSPF\b", "O S P F"), (r"\bLACP\b", "L A C P"), (r"\bSSH\b", "S S H"), (r"\bHTTP\b", "H T T P"),
    (r"\bNAT\b", "nat"), (r"\bCARP\b", "carp"), (r"\bACL\b", "A C L"),
]


def load():
    return yaml.safe_load((HERE / "narration.yaml").read_text(encoding="utf-8"))["segments"]


def values():
    return json.loads(VALUES.read_text(encoding="utf-8")) if VALUES.exists() else {}


def fill(text, vals):
    """Text with its placeholders filled, or None while a value is missing."""
    keys = re.findall(r"\{(\w+)\}", text)
    if any(k not in vals for k in keys):
        return None
    return re.sub(r"\{(\w+)\}", lambda m: str(vals[m.group(1)]), " ".join(text.split()))


def spoken(text):
    for a, b in PRON:
        text = re.sub(a, b, text)
    return text


async def _edge(text, out):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(out))


def hortense(text, out):
    wav = out.with_suffix(".wav")
    ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Hortense Desktop'); $s.Rate=0; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=text, text=True, encoding="utf-8", check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    wav.unlink()


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def main(argv):
    VO.mkdir(parents=True, exist_ok=True)
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    force = "--force" in argv
    vals = values()
    dpath, tpath = VO / "durations.json", VO / "texts.json"
    durs = json.loads(dpath.read_text(encoding="utf-8")) if dpath.exists() else {}
    texts = json.loads(tpath.read_text(encoding="utf-8")) if tpath.exists() else {}
    for s in load():
        for key, field in ((s["id"], "vo"), (s["id"] + "_jury", "jury_vo")):
            if field not in s or (only and s["id"] not in only):
                continue
            text = fill(s[field], vals)
            if text is None:
                print(f"skip {key}: placeholder not known yet", flush=True)
                continue
            out = VO / f"{key}.mp3"
            if out.exists() and texts.get(key) == text and not force:
                continue
            try:
                asyncio.run(_edge(spoken(text), out))
                engine = "edge-tts Henri"
            except Exception as e:  # noqa: BLE001  offline or service refused
                print(f"edge-tts failed for {key} ({e}); offline voice", flush=True)
                hortense(spoken(text), out)
                engine = "Hortense (offline)"
            durs[key], texts[key] = round(dur(out), 2), text
            print(f"{key:14} {durs[key]:6.2f} s  {engine}", flush=True)
    dpath.write_text(json.dumps(durs, indent=1, ensure_ascii=False), encoding="utf-8")
    tpath.write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
