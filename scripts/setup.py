"""One-time setup. Installs and fixes what it can, then reports. Safe to run again. Spends nothing.

  python -I -X utf8 setup.py              everything
  python -I -X utf8 setup.py --no-model   skip the model downloads (they happen on first use instead)

Does: Python packages, ffmpeg (winget on Windows, Homebrew on Mac), Node 22+ for twin-reel-studio, the models
(Whisper for captions, about 1.5 GB; the cut-out model for reels, about 180 MB), the profile, and a live check of the
API keys. Ends with READY or NOT READY. The same file ships in twin-studio and twin-reel-studio.
"""
import importlib, importlib.util, platform, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common
from common import DEFAULT, ENV_FILE, PROFILE, SKILL, load, save, tool_paths
from creator import REEL, check, node_major

problems = []
MODULES = [("faster_whisper", "faster-whisper"), ("PIL", "pillow")] + (
    [("mediapipe", "mediapipe"), ("rembg", "rembg[cpu]"), ("cv2", "opencv-python"), ("numpy", "numpy")] if REEL else [])


def ok(flag, label, fix=""):
    print(f"  [{'OK' if flag else '!!'}] {label}" + ("" if flag or not fix else f"\n       fix: {fix}"), flush=True)
    if not flag:
        problems.append(label)
    return flag


def pip(*args):
    base = [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *args]
    r = subprocess.run(base, capture_output=True, text=True)
    if r.returncode and "externally-managed" in (r.stderr + r.stdout):   # Homebrew / system Python on Mac and Linux
        r = subprocess.run(base + ["--user", "--break-system-packages"], capture_output=True, text=True)
    if r.returncode:
        print((r.stderr or r.stdout)[-800:])
    return r.returncode == 0


def install(name, win_id, brew):
    system = platform.system()
    if system == "Windows" and shutil.which("winget"):
        print(f"     installing {name} with winget (free, a minute or two)...", flush=True)
        subprocess.run(["winget", "install", "--id", win_id, "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"])
    elif system == "Darwin" and shutil.which("brew"):
        print(f"     installing {name} with Homebrew...", flush=True)
        subprocess.run(["brew", "install", brew])
    elif system == "Linux" and shutil.which("apt-get"):
        subprocess.run(["sudo", "apt-get", "install", "-y", brew])
    tool_paths()


def ffmpeg_ok():
    ff = shutil.which("ffmpeg")
    if not ff:
        return False, ""
    enc = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    fil = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    missing = [n for n, s in (("libvpx-vp9", enc), ("prores_ks", enc), ("ass", fil)) if f" {n} " not in s]
    return True, ", ".join(missing)


def main():
    skip_model = "--no-model" in sys.argv
    n = 6 if REEL else 5
    print(f"1/{n} Python...", flush=True)
    if not ok(sys.version_info >= (3, 10), f"Python {platform.python_version()}",
              "install Python 3.12: Windows `winget install Python.Python.3.12` · Mac `brew install python@3.12`"):
        return finish()

    print(f"2/{n} Python packages (a few minutes the first time)...", flush=True)
    pip("-r", str(SKILL / "requirements.txt"))
    importlib.invalidate_caches()
    for mod, pkg in MODULES:
        found = importlib.util.find_spec(mod) is not None
        if found and mod == "mediapipe":   # installed is not enough: it must load on this Python
            found = subprocess.run([sys.executable, "-c", "import mediapipe"], capture_output=True).returncode == 0
        ok(found, f"package {pkg}", f"{sys.executable} -m pip install {pkg}" +
           (" (if it still fails, mediapipe has no build for this Python yet: install Python 3.12)" if mod == "mediapipe" else ""))

    print(f"3/{n} ffmpeg...", flush=True)
    have, missing = ffmpeg_ok()
    if not have:
        install("ffmpeg", "Gyan.FFmpeg", "ffmpeg")
        have, missing = ffmpeg_ok()
    ok(have, f"ffmpeg ({shutil.which('ffmpeg') or 'not found'})",
       "Windows: winget install Gyan.FFmpeg · Mac: brew install ffmpeg (Homebrew from https://brew.sh) · then close and reopen Claude Code")
    if have:
        ok(not missing, "ffmpeg has the parts this skill needs" + (f" (missing: {missing})" if missing else ""),
           "install a full build: Windows `winget install Gyan.FFmpeg` · Mac `brew install ffmpeg`")

    if REEL:
        print(f"4/{n} Node 22+ (HyperFrames renders the reel)...", flush=True)
        if node_major() < 22:
            install("Node.js", "OpenJS.NodeJS.LTS", "node")
        ok(node_major() >= 22 and shutil.which("npx") is not None, f"Node {common.run(['node', '-v']) or 'not found'}",
           "Windows: winget install OpenJS.NodeJS.LTS · Mac: brew install node · then close and reopen Claude Code")
        ok((SKILL / "template" / "track" / "hand_landmarker.task").exists(), "hand-tracking model", "re-clone the skill: the file is in the repo")

    print(f"{n - 1}/{n} Models" + (" (skipped)" if skip_model else " (one time: Whisper about 1.5 GB" + (", cut-out about 180 MB)..." if REEL else ")...")), flush=True)
    if not skip_model:
        free_gb = shutil.disk_usage(Path.home()).free / 1e9
        if free_gb < 4:
            print(f"  [--] Only {free_gb:.0f} GB free on the home drive; the models need about 2 GB")
        if importlib.util.find_spec("faster_whisper"):
            try:
                from faster_whisper import WhisperModel
                WhisperModel("medium", compute_type="int8")
                ok(True, "Whisper model (medium) for captions")
            except Exception as e:   # network, disk: report and go on
                ok(False, f"Whisper model download ({str(e)[:120]})", "check the internet connection and disk space, then run setup.py again")
        if REEL and importlib.util.find_spec("rembg"):
            r = subprocess.run([sys.executable, "-c", "from rembg import new_session; new_session('isnet-general-use')"], capture_output=True, text=True)
            ok(r.returncode == 0, "cut-out model (rembg isnet)", (r.stderr or "")[-200:] or "run setup.py again")

    print(f"{n}/{n} Profile and keys...\n", flush=True)
    if not PROFILE.exists():
        save(DEFAULT)
        print(f"  [OK] created the profile {PROFILE}")
    else:
        print(f"  [OK] profile {PROFILE}")
    if check():
        problems.append("keys")
    p = load()
    ok(bool(p["heygen"].get("look_id")), "avatar chosen (heygen.look_id)", "creator.py looks, then creator.py set heygen.look_id=<id>")
    if p["voice"]["provider"] == "elevenlabs" and common.key("ELEVEN_API_KEY"):
        ok(bool(p["voice"].get("voice_id")), "voice chosen (voice.voice_id)", "creator.py voices, then creator.py set voice.voice_id=<id>")
    else:
        ok(bool(p["voice"].get("voice_id") or p["heygen"].get("voice_id")), "voice chosen (HeyGen voice)",
           "creator.py voices, then creator.py set voice.provider=heygen heygen.voice_id=<id>")
    ok(bool(p.get("name")), "name on screen", 'creator.py set name="..."' + (' role="..."' if not REEL else ""))
    finish()


def finish():
    if problems:
        print(f"\nNOT READY: fix the [!!] lines above, then run setup.py again.\nKeys go in {ENV_FILE} (creator.py keys opens it).")
        sys.exit(1)
    print("\nREADY. Free test with no cost: python -I -X utf8 " + str(HERE / "selftest.py"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
