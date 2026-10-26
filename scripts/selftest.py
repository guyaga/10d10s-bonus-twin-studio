"""Free self-test: no HeyGen, no keys, nothing spent.

  python -I -X utf8 selftest.py [--out folder]

Draws a stand-in presenter (a silhouette in your brand colours), turns it into a transparent 4-second clip, and runs
the real frame.py on it: a 16:9 studio clip and a 9:16 side still with a title. If both come out, everything after
HeyGen works on this machine. Default output: ./twin-selftest
"""
import argparse, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import fail, load, which

sys.stdout.reconfigure(encoding="utf-8")
p = argparse.ArgumentParser()
p.add_argument("--out", default=os.path.join(os.getcwd(), "twin-selftest"))
a = p.parse_args()
which("ffmpeg") or fail("ffmpeg is not installed", "run setup.py")
prof = load()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)

from PIL import Image, ImageDraw
W, H = 1920, 1080
ink = prof["brand"]["ink"]
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
cx = W // 2
d.ellipse([cx - 150, 180, cx + 150, 520], fill=ink)                     # head
d.rounded_rectangle([cx - 380, 560, cx + 380, H + 200], 220, fill=ink)  # shoulders and body
sil = out / "stand_in.png"
img.save(sil)

twin = out / "stand_in.webm"
r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "25", "-i", str(sil),
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "4", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                    "-b:v", "1M", "-c:a", "libopus", "-shortest", str(twin)], capture_output=True, text=True)
if r.returncode:
    fail(f"ffmpeg could not make a transparent clip: {r.stderr[-300:]}", "run setup.py (it installs a full ffmpeg)")

py = [sys.executable, "-I", "-X", "utf8", str(HERE / "frame.py"), "--twin", str(twin), "--no-captions"]
clip = out / "selftest_studio_16x9.mp4"
still = out / "selftest_side_9x16.png"
for cmd in (py + ["--out", str(clip), "--frame", "studio", "--aspect", "16:9"],
            py + ["--out", str(still), "--frame", "side", "--aspect", "9:16", "--title", "Self-test", "--still", "2"]):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")   # quiet: no ffmpeg progress
    if r.returncode:
        fail(f"frame.py failed on the stand-in clip:\n{(r.stderr or r.stdout)[-800:]}")
for f in (clip, still):
    ok = f.exists() and f.stat().st_size > 1000
    print(f"  [{'OK' if ok else '!!'}] {f}")
    if not ok:
        fail("the self-test output is missing")
print("\nSELFTEST OK: the design, the name tag and the video export work. Only the HeyGen render is left,"
      " and that is the first real clip (make.py --dry-run shows its price first).")
