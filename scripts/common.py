"""Shared helpers: the creator profile, API keys, tool paths and friendly errors.
The same file ships in twin-studio and twin-reel-studio: both skills read one profile, so a member sets up once."""
import json, os, pathlib, re, shutil, subprocess, sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
# TWIN_HOME moves the whole setup (profile + .env) and ignores keys stored elsewhere on the machine: a clean test.
_home = os.environ.get("TWIN_HOME")
HOME = pathlib.Path(_home) if _home else pathlib.Path.home() / ".twin-studio"
ENV_FILE = HOME / ".env"
_env = os.environ.get("TWIN_PROFILE") or os.environ.get("TWIN_REEL_PROFILE")
_new = HOME / "profile.json"
_old = pathlib.Path.home() / ".twin-reel-studio" / "profile.json"   # the first location, still read if it is the only one
PROFILE = pathlib.Path(_env) if _env else (_old if not _home and _old.exists() and not _new.exists() else _new)

KEYS = {
    "HEYGEN_API_KEY": "HeyGen: app.heygen.com > Settings > API (the talking twin)",
    "ELEVEN_API_KEY": "ElevenLabs: elevenlabs.io > Developers > API Keys (your cloned voice)",
    "GEMINI_API_KEY": "Gemini: aistudio.google.com/apikey (images)",
}

DEFAULT = {
    "name": "",                 # the creator's name, as it may appear on screen
    "role": "",                 # a short line under the name, e.g. "Mortgage advisor" (name tag in clips)
    "handle": "",               # @handle for the end card, optional
    "language": "he",           # narration + captions language (ISO code)
    "direction": "rtl",         # rtl for Hebrew/Arabic, ltr otherwise
    "projects_root": "",        # where new reel folders and clips go
    "heygen": {"look_id": "", "voice_id": "", "engine": "avatar_v"},
    "voice": {"provider": "elevenlabs", "voice_id": "", "model": "eleven_v4", "tempo": 1.1},
    "brand": {"ink": "#111111", "paper": "#F5F3EE", "accent": "#E63B2E"},
    "clip": {                   # twin-studio: defaults for talking clips
        "frame": "studio",      # plain | studio | spotlight | side | image
        "aspect": "16:9",       # 16:9 | 9:16 | 1:1 | 4:5
        "captions": True,       # burned-in captions, a few words at a time
        "name_tag": True,       # name + role lower third for the first seconds
        "bg_image": "",         # a background image for frame=image (an office, a branded wall)
        "tempo": 1.2,           # talking clips run a touch faster than reels: 1.1 sounded slow
    },
    "look": "signal",           # twin-reel-studio: the reel's design language: signal | panels | feed
    "style_prompt": "",         # twin-reel-studio: your own image style prompt instead of the look's style.txt
    "header": "",               # twin-reel-studio: small Swiss header line, e.g. "AI FIELD NOTES"
    "cta": "",                  # the closing call to action; empty = end on the punchline
    "clips": {"tool": "none", "project_id": ""},   # image-to-video tool: dreamina | kling | fal | higgsfield | none
    "rules": [],                # the creator's own rules, read before every script
}


def fail(msg, fix=""):
    """Stop with a plain message (no traceback). Claude reads it and explains it to the user."""
    sys.exit(f"[!!] {msg}" + (f"\n     fix: {fix}" if fix else ""))


def load(required=True):
    if not PROFILE.exists():
        if required:
            fail(f"No profile yet at {PROFILE}", f"run: python -I -X utf8 {SKILL / 'scripts' / 'setup.py'}")
        return json.loads(json.dumps(DEFAULT))
    try:
        p = json.loads(PROFILE.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(f"The profile {PROFILE} is not valid JSON ({e})", "fix the file by hand, or delete it and run setup.py again")
    merged = json.loads(json.dumps(DEFAULT))
    for k, v in p.items():
        merged[k] = {**merged[k], **v} if isinstance(v, dict) and isinstance(merged.get(k), dict) else v
    return merged


def save(p):
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def env_file():
    """KEY=value lines from ~/.twin-studio/.env (blank and # lines ignored)."""
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def key(name):
    """An API key from the environment, then ~/.twin-studio/.env, then (Windows) the User environment,
    then the HeyGen CLI's credentials file. Under TWIN_HOME only the first two count."""
    v = os.environ.get(name, "").strip() or env_file().get(name, "")
    if v or _home:
        return v
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = str(winreg.QueryValueEx(k, name)[0]).strip()
        except OSError:
            pass
    if not v and name == "HEYGEN_API_KEY":
        f = pathlib.Path.home() / ".heygen" / "credentials"
        if f.exists():
            try:
                v = json.loads(f.read_text(encoding="utf-8-sig")).get("api_key", "").strip()
            except ValueError:
                pass
    return v


def api_fail(service, code, body=""):
    """Turn an HTTP error from HeyGen / ElevenLabs / Gemini into a plain message with the fix."""
    var = {"HeyGen": "HEYGEN_API_KEY", "ElevenLabs": "ELEVEN_API_KEY", "Gemini": "GEMINI_API_KEY"}.get(service, "")
    low = (body or "").lower()
    bad_key = "invalid_api_key" in low or "authentication" in low or "api key not valid" in low or "api_key_invalid" in low
    if (code in (401, 403) or bad_key) and not ("quota" in low or "balance" in low or "credit" in low):
        fail(f"{service} rejected the key {var} ({code})",
             f"copy the key again from {KEYS.get(var, service)}, paste it into {ENV_FILE}, then run: creator.py check")
    if code == 402 or "insufficient" in low or "balance" in low or "quota" in low or "credit" in low:
        fail(f"{service}: not enough credit ({code})",
             "HeyGen: app.heygen.com > Settings > API > Add funds (the API wallet, separate from the plan)" if service == "HeyGen"
             else f"top up your {service} account, then try again")
    if code == 404:
        fail(f"{service}: not found ({code}): {body[:200]}", "check the avatar look / voice id in the profile (creator.py looks / voices)")
    if code == 429:
        fail(f"{service}: too many requests right now ({code})", "wait a minute and run the same command again")
    fail(f"{service} error {code}: {body[:300]}")


def tool_paths():
    """Make freshly installed tools usable in this same session: winget / Homebrew / nvm put them where the
    current PATH may not look yet."""
    extra = []
    if os.name == "nt":
        la = pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
        extra += [la / "Microsoft" / "WinGet" / "Links", pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs"]
        pk = la / "Microsoft" / "WinGet" / "Packages"
        if pk.exists():
            extra += sorted(pk.glob("Gyan.FFmpeg*/*/bin"))
    else:
        extra += [pathlib.Path("/opt/homebrew/bin"), pathlib.Path("/usr/local/bin"), pathlib.Path("/opt/homebrew/opt/node@22/bin")]
    cur = os.environ.get("PATH", "").split(os.pathsep)
    add = [str(p) for p in extra if p.exists() and str(p) not in cur]
    if add:
        os.environ["PATH"] = os.pathsep.join(add + cur)


tool_paths()

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def which(t):
    return shutil.which(t)


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""
