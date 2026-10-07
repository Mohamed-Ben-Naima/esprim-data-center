"""Contact sheet of the report PDF for quick visual QA: python preview.py <pdf> <out.png> [first] [last] [dpi]"""
import sys
import pymupdf
from PIL import Image

pdf, out = sys.argv[1], sys.argv[2]
doc = pymupdf.open(pdf)
first = int(sys.argv[3]) if len(sys.argv) > 3 else 1
last = min(int(sys.argv[4]) if len(sys.argv) > 4 else len(doc), len(doc))
dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 55
pages = []
for i in range(first - 1, last):
    pm = doc[i].get_pixmap(dpi=dpi)
    pages.append(Image.frombytes("RGB", (pm.width, pm.height), pm.samples))
cols = min(4, len(pages))
w, h = pages[0].size
rows = (len(pages) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (w + 12), rows * (h + 12)), (120, 120, 120))
for k, im in enumerate(pages):
    sheet.paste(im, ((k % cols) * (w + 12) + 6, (k // cols) * (h + 12) + 6))
sheet.save(out)
print(f"{len(doc)} pages, sheet {first}-{last} -> {out}")
