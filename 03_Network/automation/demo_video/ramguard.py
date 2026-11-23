"""RAM guard for recordings (PLAN_06 D5): the host (15.7 GB) powers off when its memory saturates.

  python automation/demo_video/ramguard.py [--floor 0.45] [--log path]
Every 5 s: host free physical RAM -> log. Two samples in a row under the floor -> kill the Playwright/Edge
recording browser and any ffmpeg (the lab itself is left alone: stopping nodes is the director's job).
"""
import subprocess
import sys
import time
from pathlib import Path

FLOOR = float(sys.argv[sys.argv.index("--floor") + 1]) if "--floor" in sys.argv else 0.45
LOG = Path(sys.argv[sys.argv.index("--log") + 1]) if "--log" in sys.argv else Path(__file__).with_name("ramguard.log")


def free_gb():
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30, m.dwMemoryLoad


def main():
    low = 0
    with open(LOG, "a", encoding="utf-8") as f:
        while True:
            gb, load = free_gb()
            f.write(f"{time.strftime('%H:%M:%S')} avail={gb:.2f}GB load={load}%\n")
            f.flush()
            low = low + 1 if gb < FLOOR else 0
            if low >= 2:
                for im in ("msedge.exe", "ffmpeg.exe"):
                    subprocess.run(["taskkill", "/F", "/IM", im], capture_output=True)
                f.write(f"{time.strftime('%H:%M:%S')} GUARD: killed msedge/ffmpeg (avail {gb:.2f} GB)\n")
                f.flush()
                low = 0
            time.sleep(5)


if __name__ == "__main__":
    main()
