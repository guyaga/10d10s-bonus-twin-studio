"""Render the creator's HeyGen twin lip-synced to a narration file (or speaking a script), straight from the HeyGen v3 API.

usage: python -I twin.py --audio audio/narration.mp3 --webm --out twin       transparent twin for a reel
       python -I twin.py --script "..." --aspect 9:16 --out D:/clips          plain talking clip
       add --dry-run to print the request and spend nothing
Look and voice come from the profile (heygen.look_id / heygen.voice_id); --look / --voice override.
Billing: HeyGen API credits (about $0.12 per second of video at the time of writing).
"""
import argparse, json, mimetypes, os, sys, time, urllib.error, urllib.request, uuid
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import api_fail, fail, key, load

API = "https://api.heygen.com"


def call(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method, headers={"x-api-key": KEY, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        api_fail("HeyGen", e.code, e.read().decode(errors="replace"))
    except urllib.error.URLError as e:
        fail(f"No connection to HeyGen ({e.reason})", "check the internet connection and try again")


def upload(path):
    b = uuid.uuid4().hex
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    head = f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
    body = head + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    return call("POST", "/v3/assets", raw=body, ctype=f"multipart/form-data; boundary={b}")["data"]["asset_id"]


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
src = p.add_mutually_exclusive_group(required=True)
src.add_argument("--script", help="text for the twin to say (HeyGen TTS)")
src.add_argument("--script-file", help="UTF-8 text file with the script")
src.add_argument("--audio", help="local mp3/wav (or https URL) to lip-sync: the recommended path")
p.add_argument("--look", help="HeyGen look id (default: profile heygen.look_id)")
p.add_argument("--voice", help="HeyGen voice id for --script (default: profile heygen.voice_id)")
p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "4:5", "5:4", "1:1", "auto"])
p.add_argument("--res", default="1080p", choices=["720p", "1080p", "4k"])
p.add_argument("--engine", help="avatar_v (default, natural) or avatar_iv")
p.add_argument("--webm", action="store_true", help="transparent WebM (alpha) for compositing")
p.add_argument("--bg-color", help="solid background hex, e.g. #000000")
p.add_argument("--speed", type=float, help="TTS speed 0.5-1.5 (--script only)")
p.add_argument("--out", default=os.getcwd())
p.add_argument("--name", help="output file base name")
p.add_argument("--dry-run", action="store_true")
p.add_argument("--no-wait", action="store_true")
a = p.parse_args()

prof = load()
look = a.look or prof["heygen"]["look_id"] or fail("No avatar chosen", "run creator.py looks, then creator.py set heygen.look_id=<id>")
body = {"type": "avatar", "avatar_id": look, "aspect_ratio": a.aspect, "resolution": a.res,
        "engine": {"type": a.engine or prof["heygen"].get("engine") or "avatar_v"},
        "title": f"Twin clip {datetime.now():%Y-%m-%d %H:%M}"}
KEY = key("HEYGEN_API_KEY")
if not KEY and not a.dry_run:
    fail("HEYGEN_API_KEY is not set", "run creator.py keys")
if a.audio:
    if a.audio.startswith("http"):
        body["audio_url"] = a.audio
    else:
        body["audio_asset_id"] = f"<upload of {a.audio}>" if a.dry_run else upload(a.audio)
else:
    body["script"] = a.script or open(a.script_file, encoding="utf-8").read().strip()
    # always explicit: a look's own default voice is usually a stock voice, not the creator's clone
    body["voice_id"] = a.voice or prof["heygen"]["voice_id"] or fail("No HeyGen voice chosen", "run creator.py voices, then creator.py set heygen.voice_id=<id> (or narrate with ElevenLabs)")
    if a.speed:
        body["voice_settings"] = {"speed": a.speed}
if a.webm:
    body["output_format"] = "webm"
    body["remove_background"] = True
if a.bg_color:
    body["background"] = {"type": "color", "value": a.bg_color}

if a.dry_run:
    print(json.dumps(body, ensure_ascii=False, indent=2))
    sys.exit()
vid = call("POST", "/v3/videos", body)["data"]["video_id"]
print(f"submitted video_id={vid}", flush=True)
if a.no_wait:
    sys.exit()
start = time.time()
while True:
    d = call("GET", f"/v3/videos/{vid}")["data"]
    if d.get("status") == "completed":
        break
    if d.get("status") == "failed":
        fail(f"HeyGen could not render the video: {d.get('failure_code')} {d.get('failure_message')}", "if it says the avatar or consent is not ready, finish it in HeyGen and try again. Failed renders are usually not charged.")
    if time.time() - start > 40 * 60:
        fail(f"Still rendering after 40 minutes (video_id={vid})", "it may still finish: look for it in HeyGen > Projects, nothing needs to be paid twice")
    print(f"  {d.get('status')} ({int(time.time() - start)}s)", flush=True)
    time.sleep(15)

os.makedirs(a.out, exist_ok=True)
out = os.path.join(a.out, f"{a.name or f'twin_{datetime.now():%Y%m%d_%H%M%S}'}.{'webm' if a.webm else 'mp4'}")
urllib.request.urlretrieve(d["video_url"], out)
print(json.dumps({"video_id": vid, "file": out, "duration": d.get("duration")}, ensure_ascii=False))
