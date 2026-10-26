"""Stage a transparent twin render in a designed frame: background, position, captions word by word, name tag, title.

usage: python -I -X utf8 frame.py --twin twin.webm --out final.mp4                       profile defaults (clip.*)
       python -I -X utf8 frame.py --twin twin.webm --out f.mp4 --frame side --aspect 9:16 --title "3 mistakes when..."
       python -I -X utf8 frame.py --twin twin.webm --out f.mp4 --script script.txt       captions spelled as written
       --still 3.5 renders one frame (PNG) at that second instead of the video: check the layout before a long render
Frames: studio (light, a brand disc behind you) | spotlight (dark stage) | side (you on a colour panel, title beside you)
        | image (your own background, clip.bg_image or --bg-image) | plain (no design, only captions and name tag)
"""
import argparse, difflib, json, math, os, re, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SKILL, load
from PIL import Image, ImageDraw, ImageFilter, ImageOps

SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--twin", required=True, help="twin render: transparent .webm (or an .mp4 for frame=plain)")
p.add_argument("--out", required=True)
p.add_argument("--audio", help="sound track (default: the twin's own)")
p.add_argument("--frame", choices=["studio", "spotlight", "side", "image", "plain"])
p.add_argument("--aspect", choices=list(SIZES))
p.add_argument("--title", default="", help="title text (side frame: beside you; others: at the top)")
p.add_argument("--bg-image", help="background image for frame=image")
p.add_argument("--script", help="the script file: captions use its spelling, with the audio's timing")
p.add_argument("--captions", dest="captions", action="store_true", default=None)
p.add_argument("--no-captions", dest="captions", action="store_false")
p.add_argument("--name-tag", dest="name_tag", action="store_true", default=None)
p.add_argument("--no-name-tag", dest="name_tag", action="store_false")
p.add_argument("--whisper-model", default="medium")
p.add_argument("--still", type=float, help="render a single PNG frame at this second")
a = p.parse_args()

prof = load()
C = prof["clip"]
frame = a.frame or C.get("frame") or "studio"
aspect = a.aspect or C.get("aspect") or "16:9"
captions = C.get("captions", True) if a.captions is None else a.captions
name_tag = (C.get("name_tag", True) if a.name_tag is None else a.name_tag) and prof.get("name")
bg_image = a.bg_image or C.get("bg_image")
rtl = prof.get("direction", "rtl") == "rtl"
B = prof["brand"]
W, H = SIZES[aspect]
vertical = H > W
work = tempfile.mkdtemp(prefix="twinframe_")
hexrgb = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
INK, PAPER, ACC = hexrgb(B["ink"]), hexrgb(B["paper"]), hexrgb(B["accent"])
mix = lambda c1, c2, t: tuple(round(x + (y - x) * t) for x, y in zip(c1, c2))


def probe(path, entries, stream="v:0"):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries, "-of", "json", path],
                         capture_output=True, text=True).stdout
    return json.loads(out)


info = probe(a.twin, "stream=width,height,codec_name,r_frame_rate:format=duration")
SW, SH = info["streams"][0]["width"], info["streams"][0]["height"]
DUR = float(info["format"]["duration"])
num, den = info["streams"][0]["r_frame_rate"].split("/")
FPS = round(float(num) / float(den), 3) or 25
alpha = info["streams"][0]["codec_name"] in ("vp9", "vp8") and a.twin.lower().endswith(".webm")
dec = ["-c:v", "libvpx-vp9"] if info["streams"][0]["codec_name"] == "vp9" else (["-c:v", "libvpx"] if alpha else [])
if frame != "plain" and not alpha:
    sys.exit("This frame needs a transparent twin: render it with twin.py --webm (or use --frame plain).")

# --- where the person is in the render: union of the alpha bounding boxes of a few frames ---
box = [SW, SH, 0, 0]
if alpha:
    for k, t in enumerate([DUR * f for f in (0.15, 0.4, 0.65, 0.9)]):
        png = os.path.join(work, f"probe{k}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *dec, "-ss", f"{t:.2f}", "-i", a.twin, "-frames:v", "1", png], check=True)
        bb = Image.open(png).convert("RGBA").getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        if bb:
            box = [min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3])]
    if box[2] <= box[0]:
        sys.exit("The twin render looks empty (no opaque pixels).")
else:
    box = [0, 0, SW, SH]
bx0, btop, bx1, bbot = box
bcx = (bx0 + bx1) / 2

# --- layout: head-top line and centre line of the person, per frame and aspect ---
side_x = (0.27 if rtl else 0.73) * W              # RTL reads from the right, so the text goes right and you go left
if vertical:
    top = {"side": 0.38 * H}.get(frame, 0.32 * H)
    cx = W / 2
else:
    top = {"16:9": 140, "1:1": 190, "4:5": 280}[aspect] if frame != "side" else 0.16 * H
    cx = side_x if frame == "side" else W / 2
if frame == "plain" and not alpha:
    s = max(W / SW, H / SH)                         # cover the frame with the render itself
    ox, oy = (W - SW * s) / 2, (H - SH * s) / 2
else:
    s = (H - top) / (bbot - btop) if bbot >= SH - 4 else (H - top) / ((bbot - btop) * 1.06)
    ox, oy = cx - bcx * s, top - btop * s
TW, TH = round(SW * s / 2) * 2, round(SH * s / 2) * 2
person = (ox + bx0 * s, oy + btop * s, ox + bx1 * s, min(H, oy + bbot * s))

# --- background ---
bg = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(bg)
if frame == "studio":
    r = 0.36 * (person[3] - person[1]) + 0.18 * (person[2] - person[0])
    ccx, ccy = (person[0] + person[2]) / 2, person[1] + 0.42 * (person[3] - person[1])
    d.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], fill=ACC)
    m = round(0.022 * min(W, H))
    d.rectangle([m, m, W - m, H - m], outline=INK, width=3)
elif frame == "spotlight":
    bg = Image.new("RGB", (W, H), INK)
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    ccx, ccy = (person[0] + person[2]) / 2, person[1] + 0.35 * (person[3] - person[1])
    r = 0.62 * max(person[3] - person[1], person[2] - person[0])
    gd.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(r * 0.35))
    bg = Image.composite(Image.new("RGB", (W, H), mix(INK, mix(PAPER, ACC, 0.08), 0.22)), bg, glow)
    d = ImageDraw.Draw(bg)
    d.rectangle([0, H - round(0.012 * H), W, H], fill=ACC)
elif frame == "side":
    if vertical:
        d.rectangle([0, round(0.33 * H), W, H], fill=ACC)
    else:
        x0, x1 = (0, round(0.5 * W)) if rtl else (round(0.5 * W), W)
        d.rectangle([x0, 0, x1, H], fill=ACC)
    ks = round(0.03 * min(W, H))
    kx = (W - round(0.06 * W) - ks) if (rtl and not vertical) else round(0.06 * W)
    if vertical:
        kx = (W - ks) // 2
    ky = round((0.07 if vertical else 0.20) * H)
    d.rectangle([kx, ky, kx + ks, ky + ks], fill=INK)
elif frame == "image":
    if not bg_image:
        sys.exit("frame=image needs --bg-image or clip.bg_image in the profile.")
    bg = ImageOps.fit(Image.open(bg_image).convert("RGB"), (W, H), Image.LANCZOS)
    bg = Image.blend(bg, Image.new("RGB", (W, H), INK), 0.18)
bg.save(os.path.join(work, "bg.png"))

# --- words with timings ---
words = []
if captions:
    from faster_whisper import WhisperModel
    script = open(a.script, encoding="utf-8").read() if a.script else ""
    m = WhisperModel(a.whisper_model, compute_type="int8")
    segs, _ = m.transcribe(a.audio or a.twin, language=prof["language"], word_timestamps=True,
                           initial_prompt=script[:400] or None, vad_filter=True)
    heard = [[w.word.strip(), w.start, w.end] for sg in segs for w in sg.words if w.word.strip()]
    if script:   # keep the script's spelling, take the timing from what was heard
        norm = lambda w: re.sub(r"[^\w]", "", w).lower()
        toks = script.split()
        sm = difflib.SequenceMatcher(None, [norm(t) for t in toks], [norm(h[0]) for h in heard], autojunk=False)
        times = [None] * len(toks)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op in ("equal", "replace") and i2 - i1 == j2 - j1:
                for k in range(i2 - i1):
                    times[i1 + k] = heard[j1 + k][1:]
            elif op in ("replace", "delete") and j2 > j1:     # spread the heard span over the script words
                t0, t1 = heard[j1][1], heard[j2 - 1][2]
                n = i2 - i1
                for k in range(n):
                    times[i1 + k] = [t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n]
        for i, t in enumerate(times):                         # words nothing was heard for: squeeze them between neighbours
            if t is None:
                prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0)
                nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.3)
                times[i] = [prev, max(prev + 0.05, (prev + nxt) / 2)]
        words = [[t, s0, s1] for t, (s0, s1) in zip(toks, times)]
    else:
        words = heard

# --- ASS: captions, name tag, title ---
def ass_col(rgb, alpha=0):
    return f"&H{alpha:02X}{rgb[2]:02X}{rgb[1]:02X}{rgb[0]:02X}"


def ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


u = min(W, H) / 1080
cap_size = round((96 if vertical else 76) * u)
WHITE = (255, 255, 255)
half_l, half_r = (round(0.5 * W) + 60, 110) if rtl else (110, round(0.5 * W) + 60)
styles = [
    # name, font, size, primary, outline(box), align, marginL, marginR, marginV, bold, borderstyle, outline width
    ("Cap", "Rubik ExtraBold", cap_size, WHITE, INK, 2, 80, 80, round((0.17 * H) if vertical else 64 * u), 3, round(14 * u)),
    ("Name", "Rubik ExtraBold", round(62 * u), WHITE, ACC, 2, 80, 80, 0, 3, round(10 * u)),
    ("Role", "Rubik Medium", round(42 * u), INK, PAPER, 2, 80, 80, 0, 3, round(8 * u)),
    ("Title", "Rubik ExtraBold", round((124 if vertical else 116) * u) if frame == "side" else round((80 if vertical else 64) * u),
     INK if frame in ("studio", "side", "plain") and not (frame == "plain" and not alpha) else WHITE, INK, 8, 90, 90, round(0.09 * H), 1, 0),
]
if frame == "side" and not vertical:
    styles[0] = ("Cap",) + styles[0][1:5] + (2, half_l, half_r, 150, 3, round(14 * u))
    styles[3] = ("Title",) + styles[3][1:5] + (9 if rtl else 7, half_l, half_r, round(0.26 * H), 1, 0)
if frame == "side" and vertical:
    styles[3] = ("Title",) + styles[3][1:5] + (8, 90, 90, round(0.11 * H), 1, 0)
    styles[0] = ("Cap",) + styles[0][1:8] + (round(0.12 * H), 3, round(14 * u))
lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
         "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
         "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
for n, f, sz, pc, oc, al, ml, mr, mv, bs, ow in styles:
    lines.append(f"Style: {n},{f},{sz},{ass_col(pc)},{ass_col(pc)},{ass_col(oc)},{ass_col(oc)},0,0,0,0,100,100,0,0,{bs},{ow},0,{al},{ml},{mr},{mv},-1")
lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]

if words:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= 4 or len(" ".join(x[0] for x in cur + [w])) > (22 if vertical else 30) or w[1] - cur[-1][2] > 0.6):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.?!:;]$", w[0]) or (re.search(r",$", w[0]) and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    for ci, ch in enumerate(chunks):
        end = min(ch[-1][2] + 0.3, chunks[ci + 1][0][1] if ci + 1 < len(chunks) else DUR)
        for wi, w in enumerate(ch):
            t0 = ch[0][1] if wi == 0 else w[1]
            t1 = ch[wi + 1][1] if wi + 1 < len(ch) else end
            txt = " ".join((f"{{\\c{ass_col(ACC)}}}{x[0]}{{\\c{ass_col(WHITE)}}}" if k == wi else x[0]) for k, x in enumerate(ch))
            lines.append(f"Dialogue: 1,{ts(t0)},{ts(t1)},Cap,,0,0,0,,{txt}")

if name_tag:
    if vertical:
        nx, ny, an = W / 2, ((0.29 if frame == "side" else 0.24) * H if a.title else 0.17 * H), 2
    elif frame == "side":
        nx, ny, an = (person[0] + person[2]) / 2, H - 150 * u, 2
    else:
        nx, ny, an = (W - 110 * u, H - 210 * u, 3) if rtl else (110 * u, H - 210 * u, 1)
    fade = "\\fad(300,300)"
    lines.append(f"Dialogue: 2,{ts(0.5)},{ts(min(5, DUR))},Name,,0,0,0,,{{\\an{an}\\pos({nx:.0f},{ny:.0f}){fade}}}{prof['name']}")
    if prof.get("role"):
        lines.append(f"Dialogue: 2,{ts(0.5)},{ts(min(5, DUR))},Role,,0,0,0,,{{\\an{an + 6}\\pos({nx:.0f},{ny + 16 * u:.0f}){fade}}}{prof['role']}")
if a.title:
    lines.append(f"Dialogue: 0,{ts(0)},{ts(DUR)},Title,,0,0,0,,{a.title}")
if rtl:   # a right-to-left mark first, so a line that starts with a digit or a Latin word still reads right to left
    lines = [l.replace(",,0,0,0,,", ",,0,0,0,," + chr(0x200F), 1) if l.startswith("Dialogue:") else l for l in lines]
ass = os.path.join(work, "over.ass")
open(ass, "w", encoding="utf-8").write("\n".join(lines) + "\n")
fonts = os.path.join(work, "fonts")
shutil.copytree(SKILL / "fonts", fonts)

# --- compose ---
shadow = frame in ("studio", "side", "image")
if alpha:
    tw = f"[1:v]scale={TW}:{TH}:flags=lanczos,format=rgba"
    if shadow:
        tw += f",split[tw][ts];[ts]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.32,boxblur={max(4, round(16 * u))}[sh];" \
              f"[0:v][sh]overlay={ox + 10 * u:.0f}:{oy + 12 * u:.0f}:shortest=1[b1];[b1][tw]overlay={ox:.0f}:{oy:.0f}"
    else:
        tw += f"[tw];[0:v][tw]overlay={ox:.0f}:{oy:.0f}:shortest=1"
    fc = tw + ":format=auto,ass=over.ass:fontsdir=fonts,format=yuv420p[v]"
else:
    fc = f"[1:v]scale={TW}:{TH},crop={W}:{H}:{-ox:.0f}:{-oy:.0f}[tw];[0:v][tw]overlay=0:0:shortest=1,ass=over.ass:fontsdir=fonts,format=yuv420p[v]"
inputs = ["-loop", "1", "-framerate", str(FPS), "-i", "bg.png", *dec, "-i", os.path.abspath(a.twin)]
if a.audio:
    inputs += ["-i", os.path.abspath(a.audio)]
amap = ["-map", "2:a" if a.audio else "1:a?"]
out = os.path.abspath(a.out)
os.makedirs(os.path.dirname(out), exist_ok=True)
if a.still is not None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", "bg.png", *dec, "-ss", str(a.still),
           "-i", os.path.abspath(a.twin),
           # skip the first frames: the overlay emits them before the twin's first frame arrives (background only)
           "-filter_complex", fc.replace("ass=over.ass", f"setpts=PTS+{a.still}/TB,ass=over.ass").replace("format=yuv420p[v]", "format=yuv420p,select=gte(n\\,2)[v]"),
           "-map", "[v]", "-frames:v", "1", out if out.endswith(".png") else out.rsplit(".", 1)[0] + ".png"]
else:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stats", *inputs, "-filter_complex", fc, "-map", "[v]", *amap,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
           "-t", f"{DUR:.3f}", "-movflags", "+faststart", out]
subprocess.run(cmd, cwd=work, check=True)
shutil.rmtree(work, ignore_errors=True)
print(json.dumps({"file": cmd[-1], "frame": frame, "aspect": aspect, "seconds": round(DUR, 1), "captions": len(words)}, ensure_ascii=False))
