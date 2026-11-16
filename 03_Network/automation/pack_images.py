"""Pack the lab images into zip archives for the GitHub repo (Git LFS), and unpack them back.

  python automation/pack_images.py            H:/DC-Casablanca-images/{cisco,iso,qemu} -> images/archives/*.zip
                                              (parts under 1.9 GB: GitHub LFS refuses files over 2 GB)
  python automation/pack_images.py --unpack [DEST]   join the parts, unzip to DEST (default H:/DC-Casablanca-images),
                                              then check every SHA-256 against images/manifest.json
The archives are Git LFS objects. On a clone without them: git lfs pull --include "03_Network/images/archives/*"
"""
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

NET = Path(__file__).resolve().parents[1]
ARCH = NET / "images" / "archives"
STORE = Path(os.environ.get("DC_IMAGES", r"H:\DC-Casablanca-images"))
PART = 1900 * 1024 * 1024
GROUPS = {"cisco": ["cisco"], "qemu": ["qemu"], "iso-pfsense": ["iso/pfSense-CE-2.7.2-RELEASE-amd64.iso"],
          "iso-truenas": ["iso/TrueNAS-SCALE-25.10.7.iso"]}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def pack():
    ARCH.mkdir(parents=True, exist_ok=True)
    index = []
    for name, items in GROUPS.items():
        z = ARCH / f"{name}.zip"
        files = []
        for it in items:
            p = STORE / it
            files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as zf:
            for f in files:
                zf.write(f, f.relative_to(STORE).as_posix())
        raw = sum(f.stat().st_size for f in files)
        parts = [z]
        if z.stat().st_size > PART:
            parts = []
            with open(z, "rb") as src:
                i = 1
                while chunk := src.read(PART):
                    q = ARCH / f"{name}.zip.{i:03d}"
                    q.write_bytes(chunk)
                    parts.append(q)
                    i += 1
            z.unlink()
        packed = sum(q.stat().st_size for q in parts)
        index.append(dict(archive=f"{name}.zip", parts=[q.name for q in parts], files=[f.relative_to(STORE).as_posix()
                     for f in files], original_bytes=raw, packed_bytes=packed,
                          sha256={q.name: sha256(q) for q in parts}))
        print(f"{name:12s} {raw / 1048576:8.1f} MB -> {packed / 1048576:8.1f} MB  ({len(parts)} part(s))")
    (ARCH / "archives.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    tot_r = sum(i["original_bytes"] for i in index)
    tot_p = sum(i["packed_bytes"] for i in index)
    print(f"total        {tot_r / 1048576:8.1f} MB -> {tot_p / 1048576:8.1f} MB ({100 * (1 - tot_p / tot_r):.1f} % saved)")


def unpack(dest):
    dest.mkdir(parents=True, exist_ok=True)
    index = json.loads((ARCH / "archives.json").read_text(encoding="utf-8"))
    man = {r["file"]: r["sha256"] for r in json.loads((NET / "images/manifest.json").read_text(encoding="utf-8"))["images"]}
    bad = 0
    for a in index:
        z = ARCH / a["archive"]
        if len(a["parts"]) > 1:
            z = dest / a["archive"]
            with open(z, "wb") as out:
                for q in a["parts"]:
                    out.write((ARCH / q).read_bytes())
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dest)
        if z.parent == dest:
            z.unlink()
        for f in a["files"]:
            ok = sha256(dest / f) == man.get(f)
            bad += not ok
            print(f"{'OK ' if ok else 'BAD'} {f}")
    print("all images restored and verified" if not bad else f"{bad} file(s) differ from the manifest")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--unpack" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--unpack"]
        sys.exit(unpack(Path(rest[0]) if rest else STORE))
    pack()
