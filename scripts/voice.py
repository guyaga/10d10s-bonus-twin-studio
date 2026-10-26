"""Narrate a script in the creator's cloned voice (profile voice.*), one call per paragraph, sped up and stitched.

usage: python -I voice.py --text-file script.txt --out D:/clips/intro       -> narration.wav
       python -I voice.py --text "..." --out ...
Paragraphs are split on blank lines. ElevenLabs (voice.provider=elevenlabs) sounds far better than HeyGen TTS.
"""
import argparse, json, os, subprocess, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import api_fail, fail, key, load

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
src = p.add_mutually_exclusive_group(required=True)
src.add_argument("--text")
src.add_argument("--text-file")
p.add_argument("--out", required=True, help="folder for narration.wav")
p.add_argument("--tempo", type=float, help="speed-up, default profile clip.tempo (1.2)")
a = p.parse_args()

prof = load()
V, lang = prof["voice"], prof["language"]
text = a.text or open(a.text_file, encoding="utf-8").read()
paras = [x.strip() for x in text.replace("\r", "").split("\n\n") if x.strip()]
if not paras:
    fail("The script is empty", "write what the twin should say, then run again")
tempo = a.tempo or prof["clip"].get("tempo") or 1.2
os.makedirs(a.out, exist_ok=True)
tmp = os.path.join(a.out, "voice_parts")
os.makedirs(tmp, exist_ok=True)


def post(url, headers, body):
    for attempt in range(6):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                time.sleep(4)
                continue
            api_fail("HeyGen" if "heygen" in url else "ElevenLabs", e.code, e.read().decode(errors="replace"))
        except urllib.error.URLError as e:
            fail(f"No connection to {url.split('/')[2]} ({e.reason})", "check the internet connection and try again")


parts = []
for i, t in enumerate(paras, 1):
    raw = os.path.join(tmp, f"raw{i}.mp3")
    if V.get("provider") == "heygen":
        j = json.loads(post("https://api.heygen.com/v3/voices/speech", {"x-api-key": key("HEYGEN_API_KEY")},
                            {"text": t, "voice_id": V.get("voice_id") or prof["heygen"]["voice_id"], "language": lang}))
        urllib.request.urlretrieve(j["data"]["audio_url"], raw)
    else:
        k = key("ELEVEN_API_KEY") or fail("ELEVEN_API_KEY is not set", "run creator.py keys (or creator.py set voice.provider=heygen)")
        vid = V.get("voice_id") or fail("No voice chosen", "run creator.py voices, then creator.py set voice.voice_id=<id>")
        open(raw, "wb").write(post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_192", {"xi-api-key": k},
                                   {"text": t, "model_id": V.get("model") or "eleven_v4", "language_code": lang,
                                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.85}}))
    wav = os.path.join(tmp, f"p{i}.wav")
    # speed up, trim the silence the TTS leaves at both ends
    trim = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", f"{trim},atempo={tempo}", "-ar", "44100", "-ac", "2", wav], check=True)
    parts.append(wav)
    print(f"paragraph {i}/{len(paras)} ok", flush=True)

# 0.15 s lead, 0.3 s between paragraphs, 0.4 s tail
n = len(parts)
fc = ";".join(f"[{i}:a]adelay={150 if i == 0 else 300}|{150 if i == 0 else 300}{',apad=pad_dur=0.4' if i == n - 1 else ''}[s{i}]" for i in range(n))
fc += ";" + "".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
out = os.path.join(a.out, "narration.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *sum((["-i", f] for f in parts), []), "-filter_complex", fc, "-map", "[out]", out], check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
print(json.dumps({"file": out, "seconds": round(dur, 1)}))
