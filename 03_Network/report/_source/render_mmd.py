"""Render a Mermaid source (.mmd) to PNG locally: headless Edge loads mermaid.js from the jsDelivr CDN (a library
download only - the diagram itself never leaves the PC, unlike mermaid.ink), takes a screenshot, Pillow crops it.

  python report/_source/render_mmd.py arch_topology            -> report/_source/arch_topology.png
"""
import html
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).parent
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def render(name, width=2400, height=2000, scale=1.5):
    src = (HERE / f"{name}.mmd").read_text(encoding="utf-8")
    page = (f'<!doctype html><html><head><meta charset="utf-8"><script src="{MERMAID}"></script>'
            '<style>body{margin:0;background:#fff}.mermaid{display:inline-block;padding:16px}</style></head><body>'
            f'<pre class="mermaid">{html.escape(src)}</pre>'
            '<script>mermaid.initialize({startOnLoad:true,theme:"default",themeVariables:{fontSize:"22px"},flowchart:{htmlLabels:true,useMaxWidth:false}});</script>'
            '</body></html>')
    browser = next(b for b in BROWSERS if Path(b).exists())
    with tempfile.TemporaryDirectory() as td:
        h, shot = Path(td) / "d.html", Path(td) / "d.png"
        h.write_text(page, encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
                        "--virtual-time-budget=15000", f"--screenshot={shot}", h.as_uri()],
                       check=True, capture_output=True, timeout=120)
        img = Image.open(shot).convert("RGB")
    box = ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox()
    if not box:
        raise SystemExit(f"{name}: blank render (mermaid.js not loaded?)")
    pad = 20 * scale
    img = img.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(img.width, box[2] + pad), min(img.height, box[3] + pad)))
    out = HERE / f"{name}.png"
    img.save(out, optimize=True)
    print(f"{out} {img.width}x{img.height}")


if __name__ == "__main__":
    for n in sys.argv[1:] or ["arch_topology"]:
        render(n)
