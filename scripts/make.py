"""One command: script -> your cloned voice -> your HeyGen twin -> a designed frame -> final MP4.

usage: python -I -X utf8 make.py --text-file script.txt --out D:/clips/intro
       python -I -X utf8 make.py --text "..." --out ... --frame side --aspect 9:16 --title "..."
       python -I -X utf8 make.py --audio my_recording.mp3 --out ...      your own recording instead of the cloned voice
       python -I -X utf8 make.py --text-file s.txt --out ... --presenter only the transparent twin (+ a ProRes 4444 .mov) for an editor
       --dry-run prints the plan and the estimated HeyGen cost, and spends nothing.
Frame, aspect, captions and name tag default to the profile's clip.* settings.
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fail, key, load

HERE = os.path.dirname(os.path.abspath(__file__))
PER_SEC = 0.12   # HeyGen API, USD per second of avatar video (check your plan)

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
src = p.add_mutually_exclusive_group(required=True)
src.add_argument("--text")
src.add_argument("--text-file")
src.add_argument("--audio")
p.add_argument("--out", required=True, help="the clip's folder")
p.add_argument("--name", default="clip")
p.add_argument("--frame", choices=["studio", "spotlight", "side", "image", "plain"])
p.add_argument("--aspect", choices=["16:9", "9:16", "1:1", "4:5"])
p.add_argument("--title", default="")
p.add_argument("--bg-image")
p.add_argument("--no-captions", action="store_true")
p.add_argument("--no-name-tag", action="store_true")
p.add_argument("--presenter", action="store_true", help="stop after the transparent twin (+ ProRes .mov)")
p.add_argument("--dry-run", action="store_true")
a = p.parse_args()

prof = load()
py = [sys.executable, "-I", "-X", "utf8"]


def step(cmd):
    """Run one stage; on failure pass its own message through, without a Python traceback."""
    if subprocess.run(cmd).returncode != 0:
        sys.exit(1)


def blockers():
    """Everything that would make the real run fail, checked before anything is spent."""
    out = []
    heygen_tts = not a.audio and prof["voice"]["provider"] == "heygen"
    if not key("HEYGEN_API_KEY"):
        out.append("HEYGEN_API_KEY is missing: run creator.py keys")
    if not prof["heygen"].get("look_id"):
        out.append("No avatar chosen: run creator.py looks, then creator.py set heygen.look_id=<id>")
    if not a.audio and not heygen_tts:
        if not key("ELEVEN_API_KEY"):
            out.append("ELEVEN_API_KEY is missing: run creator.py keys (or creator.py set voice.provider=heygen)")
        if not prof["voice"].get("voice_id"):
            out.append("No voice chosen: run creator.py voices, then creator.py set voice.voice_id=<id>")
    if heygen_tts and not (prof["voice"].get("voice_id") or prof["heygen"].get("voice_id")):
        out.append("No HeyGen voice chosen: run creator.py voices, then creator.py set heygen.voice_id=<id>")
    if a.audio and not os.path.exists(a.audio):
        out.append(f"The audio file {a.audio} does not exist")
    if a.text_file and not os.path.exists(a.text_file):
        out.append(f"The script file {a.text_file} does not exist")
    if (a.bg_image or frame == "image") and not os.path.exists(a.bg_image or prof["clip"].get("bg_image") or "-"):
        out.append("frame=image needs a background picture: --bg-image <file> (or creator.py set clip.bg_image=<file>)")
    return out


frame = a.frame or prof["clip"].get("frame") or "studio"
aspect = a.aspect or prof["clip"].get("aspect") or "16:9"
problems = blockers()
if problems and not a.dry_run:
    fail("Can't make the clip yet (nothing was spent):\n     - " + "\n     - ".join(problems))
if not a.dry_run:
    os.makedirs(a.out, exist_ok=True)
readable = not ((a.text_file and not os.path.exists(a.text_file)) or (a.audio and not os.path.exists(a.audio)))
script = None
if not a.audio and readable:
    text = a.text or open(a.text_file, encoding="utf-8").read()
    script = os.path.join(a.out, "script.txt")
    if not a.dry_run:
        open(script, "w", encoding="utf-8").write(text.strip() + "\n")

if a.dry_run:
    secs = 0.0
    if readable and not a.audio:
        secs = len(text.split()) / 2.4
    elif readable:
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.audio], capture_output=True, text=True).stdout or 0)
    print(json.dumps({"frame": "transparent presenter" if a.presenter else frame, "aspect": aspect,
                      "voice": "your recording" if a.audio else prof["voice"]["provider"], "estimated_seconds": round(secs),
                      "estimated_heygen_usd": round(secs * PER_SEC, 2), "out": a.out,
                      "ready": not problems, "blockers": problems}, ensure_ascii=False, indent=2))
    sys.exit(1 if problems else 0)

# 1. narration
audio = a.audio
if not audio:
    if prof["voice"]["provider"] == "heygen" and not prof["voice"].get("voice_id") and prof["heygen"].get("voice_id"):
        audio = None   # HeyGen speaks the script itself in step 2
    else:
        step(py + [os.path.join(HERE, "voice.py"), "--text-file", script, "--out", a.out])
        audio = os.path.join(a.out, "narration.wav")

# 2. the twin: transparent unless the frame is plain
alpha = a.presenter or frame != "plain"
twin_args = ["--audio", audio] if audio else ["--script-file", script]
step(py + [os.path.join(HERE, "twin.py"), *twin_args, "--out", a.out, "--name", f"{a.name}_twin"] + (["--webm"] if alpha else []))
twin = os.path.join(a.out, f"{a.name}_twin.{'webm' if alpha else 'mp4'}")

if a.presenter:
    mov = os.path.join(a.out, f"{a.name}_presenter.mov")
    step(["ffmpeg", "-y", "-loglevel", "error", "-c:v", "libvpx-vp9", "-i", twin, "-c:v", "prores_ks", "-profile:v", "4444",
                    "-pix_fmt", "yuva444p10le", "-c:a", "pcm_s16le", mov])
    print(json.dumps({"webm": twin, "prores": mov}, ensure_ascii=False))
    sys.exit()

# 3. the frame
cmd = py + [os.path.join(HERE, "frame.py"), "--twin", twin, "--out", os.path.join(a.out, f"{a.name}.mp4"), "--frame", frame, "--aspect", aspect]
if audio:
    cmd += ["--audio", audio]
if script:
    cmd += ["--script", script]
if a.title:
    cmd += ["--title", a.title]
if a.bg_image:
    cmd += ["--bg-image", a.bg_image]
if a.no_captions:
    cmd += ["--no-captions"]
if a.no_name_tag:
    cmd += ["--no-name-tag"]
step(cmd)
