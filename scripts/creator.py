"""Set up and inspect the creator profile.

usage: python -I -X utf8 creator.py doctor            check tools, Python packages and API keys (setup.py runs it too)
       python -I -X utf8 creator.py init              create the profile with defaults (once)
       python -I -X utf8 creator.py keys              open the key file (~/.twin-studio/.env) in a text editor
       python -I -X utf8 creator.py check             test every key against its service, show the HeyGen balance
       python -I -X utf8 creator.py looks             list your own HeyGen avatar looks
       python -I -X utf8 creator.py voices            list your cloned voices (ElevenLabs + HeyGen)
       python -I -X utf8 creator.py set k=v [k=v...]  set fields, dotted for nested: heygen.look_id=abc clip.frame=side brand.accent=#FF5500
       python -I -X utf8 creator.py show              print the profile
"""
import importlib.util, json, os, platform, subprocess, sys, urllib.error, urllib.request
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import DEFAULT, ENV_FILE, HEX, KEYS, PROFILE, SKILL, api_fail, fail, key, load, run, save, which

sys.stdout.reconfigure(encoding="utf-8")
# One file for both skills: twin-reel-studio (it has looks/) also needs Node, the image packages and Gemini.
REEL = (SKILL / "looks").is_dir()
NEEDS = ["HEYGEN_API_KEY", "ELEVEN_API_KEY"] + (["GEMINI_API_KEY"] if REEL else [])
PACKAGES = ["faster_whisper", "PIL"] + (["mediapipe", "rembg", "cv2", "numpy"] if REEL else [])
CHOICES = {"clip.frame": ["studio", "spotlight", "side", "image", "plain"], "clip.aspect": ["16:9", "9:16", "1:1", "4:5"],
           "voice.provider": ["elevenlabs", "heygen"], "heygen.engine": ["avatar_v", "avatar_iv"], "direction": ["rtl", "ltr"]}


def get(service, url, headers):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        api_fail(service, e.code, e.read().decode(errors="replace"))
    except urllib.error.URLError as e:
        fail(f"{service}: no connection ({e.reason})", "check the internet connection and try again")


def node_major():
    import re
    m = re.findall(r"v(\d+)", run(["node", "-v"]))
    return int(m[0]) if m else 0


def doctor():
    ok = lambda b: "OK  " if b else "MISS"
    print("Tools")
    for t in ["ffmpeg", "ffprobe"] + (["node", "npx"] if REEL else []):
        print(f"  {ok(which(t))} {t}")
    if REEL:
        print(f"  {ok(node_major() >= 22)} node {run(['node', '-v']) or '-'} (HyperFrames needs 22 or newer)")
    print("Python packages")
    for m in PACKAGES:
        print(f"  {ok(importlib.util.find_spec(m))} {m}")
    print(f"API keys (environment variables or {ENV_FILE})")
    print(f"  {ok(key('HEYGEN_API_KEY'))} HEYGEN_API_KEY  - the talking twin (required)")
    print(f"  {ok(key('ELEVEN_API_KEY'))} ELEVEN_API_KEY  - narration in your cloned voice (recommended)")
    if REEL:
        print(f"  {ok(key('GEMINI_API_KEY'))} GEMINI_API_KEY  - images in the look's style (required)")
        print("Optional video-clip tools")
        for t in ["dreamina-canvas", "kling"]:
            print(f"  {ok(which(t))} {t}")
    print(f"Profile: {PROFILE} {'(exists)' if PROFILE.exists() else '(not created yet: run init)'}")


def keys():
    """Create the key file with empty lines for each key, then open it for the user to paste into and save.
    The keys never pass through the chat."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    have = ENV_FILE.read_text(encoding="utf-8-sig") if ENV_FILE.exists() else ""
    lines = [] if have else ["# Paste each key after the = sign, save the file (Ctrl+S / Cmd+S) and close it.", ""]
    for k in NEEDS:
        if f"{k}=" not in have:
            lines += [f"# {KEYS[k]}", f"{k}="]
    if lines:
        ENV_FILE.write_text(have + ("\n" if have and not have.endswith("\n") else "") + "\n".join(lines) + "\n", encoding="utf-8")
    sysname = platform.system()
    try:
        if sysname == "Windows":
            subprocess.Popen(["notepad.exe", str(ENV_FILE)])
        elif sysname == "Darwin":
            subprocess.Popen(["open", "-e", str(ENV_FILE)])
        else:
            subprocess.Popen(["xdg-open", str(ENV_FILE)])
        print(f"Opened {ENV_FILE} in a text editor. Paste the keys after the = signs, save, close, then run: creator.py check")
    except OSError:
        print(f"Open this file in any text editor, paste the keys after the = signs and save: {ENV_FILE}")


def check():
    """Call each service once (read-only, free) to prove the key works. Prints no key. Reports every key, even after a bad one."""
    bad = 0
    for test in (check_heygen, check_eleven, check_gemini):
        try:
            bad += test()
        except SystemExit as e:
            print("  " + str(e.code).replace("\n", "\n  "))
            bad += 1
    return bad


def check_heygen():
    hk = key("HEYGEN_API_KEY")
    if not hk:
        print(f"  [!!] HEYGEN_API_KEY is missing (required)\n       fix: run creator.py keys and paste it ({KEYS['HEYGEN_API_KEY']})")
        return 1
    d = get("HeyGen", "https://api.heygen.com/v3/users/me", {"x-api-key": hk}).get("data", {})
    bal = (d.get("wallet") or {}).get("remaining_balance")
    print(f"  [OK] HeyGen key works. API wallet: ${bal if bal is not None else '?'}")
    if bal is not None and bal < 2:   # a warning, not a blocker: the free selftest still runs, make.py --dry-run shows the price
        print("  [--] The HeyGen API wallet is almost empty: a 30-second clip costs about $4.\n"
              "       before the first real clip: app.heygen.com > Settings > API > Add funds ($10-15 is plenty to start)")
    return 0


def check_eleven():
    ek = key("ELEVEN_API_KEY")
    if not ek:
        print("  [--] ELEVEN_API_KEY not set: narration falls back to HeyGen's voice (works, sounds less natural)")
        return 0
    s = get("ElevenLabs", "https://api.elevenlabs.io/v1/user", {"xi-api-key": ek}).get("subscription") or {}
    if s.get("can_use_instant_voice_cloning") is False:
        print(f"  [!!] ElevenLabs key works, but the {s.get('tier', '?')} plan can't clone a voice\n"
              "       fix: Starter or higher (elevenlabs.io > Subscription), or use HeyGen's voice: creator.py set voice.provider=heygen")
        return 1
    print(f"  [OK] ElevenLabs key works. Plan: {s.get('tier', '?')}")
    return 0


def check_gemini():
    if not REEL:
        return 0
    gk = key("GEMINI_API_KEY")
    if not gk:
        print(f"  [!!] GEMINI_API_KEY is missing (required for reels)\n       fix: run creator.py keys and paste it ({KEYS['GEMINI_API_KEY']})")
        return 1
    get("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=1&key={gk}", {})
    print("  [OK] Gemini key works")
    return 0


def looks():
    k = key("HEYGEN_API_KEY") or fail("HEYGEN_API_KEY is not set", "run: creator.py keys")
    rows, token = [], ""
    while True:
        j = get("HeyGen", "https://api.heygen.com/v3/avatars/looks?ownership=private&limit=50" + (f"&token={token}" if token else ""), {"x-api-key": k})
        rows += j.get("data", [])
        token = j.get("next_token") if j.get("has_more") else ""
        if not token or len(rows) >= 500:
            break
    if not rows:
        print("No avatars of your own yet. Create your digital twin in HeyGen first (Avatars > Create avatar), "
              "wait until it shows Ready, then run this again.")
    for a in rows:
        print(f"{a['id']}  {a.get('avatar_type', ''):13} {a.get('preferred_orientation', ''):9} {a.get('name', '')}")


def voices():
    ek, hk = key("ELEVEN_API_KEY"), key("HEYGEN_API_KEY")
    if not ek and not hk:
        fail("No voice keys set (ELEVEN_API_KEY or HEYGEN_API_KEY)", "run: creator.py keys")
    if ek:
        j = get("ElevenLabs", "https://api.elevenlabs.io/v1/voices", {"xi-api-key": ek})
        order = {"cloned": 0, "professional": 1, "generated": 2}   # the creator's own clone first
        mine = sorted((v for v in j.get("voices", []) if v.get("category") in order), key=lambda v: order[v["category"]])
        print("ElevenLabs (voice.provider=elevenlabs):")
        for v in mine:
            print(f"  {v['voice_id']}  {v.get('category', ''):12} {v.get('name', '')}")
        if not mine:
            print("  no cloned voices. Make one in ElevenLabs: Voices > Add voice > Instant voice clone (1-2 minutes of clean speech).")
    if hk:
        j = get("HeyGen", "https://api.heygen.com/v3/voices?type=private&limit=50", {"x-api-key": hk})
        print("HeyGen (voice.provider=heygen, lower quality):")
        for v in j.get("data", []):
            print(f"  {v['voice_id']}  {v.get('language', ''):10} {v.get('name', '')}")
        if not j.get("data"):
            print("  no voices of your own yet (HeyGen makes one when you create the digital twin).")


def set_fields(pairs):
    if not pairs:
        fail("Nothing to set", "example: creator.py set name=\"Dana Levi\" brand.accent=#FF5500")
    p = load()
    for pair in pairs:
        if "=" not in pair:
            fail(f"'{pair}' has no value", f"write it as {pair}=<value>")
        k, v = pair.split("=", 1)
        if not k:
            fail(f"'{pair}' has no field name", "write it as field=<value>, e.g. name=\"Dana Levi\"")
        if k.startswith("brand.") and not HEX.match(v):
            fail(f"{k}={v} is not a colour", "use a 6-digit hex colour, e.g. #E63B2E")
        if k in CHOICES and v not in CHOICES[k]:
            fail(f"{k}={v} is not an option", "one of: " + ", ".join(CHOICES[k]))
        val = v
        if v[:1] in ("[", "{") or v in ("true", "false") or __import__("re").fullmatch(r"-?\d+(\.\d+)?", v):
            try:
                val = json.loads(v)
            except ValueError:   # not valid JSON: keep it as text
                pass
        node, parts = p, k.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = val
    save(p)
    print(json.dumps(p, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "doctor":
        doctor()
    elif cmd == "init":
        if PROFILE.exists():
            print(f"{PROFILE} already exists: keeping it")
        else:
            save(DEFAULT)
            print("created", PROFILE)
    elif cmd == "keys":
        keys()
    elif cmd == "check":
        sys.exit(1 if check() else 0)
    elif cmd == "looks":
        looks()
    elif cmd == "voices":
        voices()
    elif cmd == "set":
        set_fields(sys.argv[2:])
    elif cmd == "show":
        if not PROFILE.exists():
            fail(f"No profile yet at {PROFILE}", "run setup.py (or creator.py init)")
        print(json.dumps(load(), ensure_ascii=False, indent=2))
    else:
        fail(f"Unknown command '{cmd}'", "one of: doctor, init, keys, check, looks, voices, set, show")
