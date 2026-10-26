---
name: twin-studio
description: The user's own digital twin. Makes a video of them speaking any script, using their HeyGen avatar and their cloned voice, in any format. Outputs include a designed talking clip with captions that light up word by word and a name tag (16:9, 9:16, 1:1 or 4:5, in their brand colours), a transparent presenter for an editor or another video skill, and a plain talking head. Use it for an explainer about their job or service, a course or lesson intro, a welcome or onboarding video, a product or offer explanation, a personal message to clients, an FAQ answer, a LinkedIn or YouTube talking clip, or "make my twin say X". Hebrew first-class; works in any language. First run sets up a profile (avatar, voice, name, colours) that is shared with twin-reel-studio. For a full motion-design reel with graphics, use twin-reel-studio instead.
---

# Twin Studio: your digital twin

A clip is made in four steps:
1. Your script.
2. Narration in your cloned voice (ElevenLabs).
3. Your HeyGen twin lip-synced to the narration, on a transparent background.
4. A designed frame: a background in your colours, captions word by word, your name tag, and a title.

The result is an MP4 ready to post or send.

`S` below is this skill's folder (`~/.claude/skills/twin-studio`). Run Python with `-I -X utf8`.

## What it makes

| Ask | Command | Result |
|---|---|---|
| "Make my twin say this" | `make.py --text-file script.txt --out <folder>` | A designed clip in the profile's default frame |
| An explainer about my job / service | `make.py ... --frame side --title "..."` | You on a colour panel, the title beside you, captions |
| A vertical clip for Instagram, TikTok or a WhatsApp status | `make.py ... --aspect 9:16` | 1080×1920 |
| A transparent presenter for an editor, Canva, CapCut or another video skill | `make.py ... --presenter` | `.webm` with alpha plus a ProRes 4444 `.mov` |
| Just me talking, no design | `make.py ... --frame plain` | HeyGen's own render plus captions |
| My own recording, lip-synced to my twin | `make.py --audio rec.mp3 --out ...` | Same frames, in your real voice |

**Frames:**

| Frame | Look | Notes |
|---|---|---|
| `studio` | Light | Off-white background, a big brand-colour disc behind you, a thin frame |
| `spotlight` | Dark | A dark stage with a soft light behind you and an accent line |
| `side` | Split | You on a brand-colour panel and a big title beside you. On 9:16 the title sits above you. The best frame for an explainer. |
| `image` | Your background | Your own background image, e.g. your office or a branded wall: `--bg-image` or `clip.bg_image` |
| `plain` | No design | Only captions and the name tag |

**Aspects:** `16:9` (YouTube, a website, a course), `9:16` (reels, stories, status), `1:1` and `4:5` (feed posts).

**Longer explainers** (2–5 minutes, with graphics, screenshots or slides): make the twin with `--presenter`, then build the video around it in the user's video tool. If the club's `motion-studio` skill is installed, use it, with the transparent twin as the presenter layer. Two minutes of twin costs about $15 in HeyGen credits, so plan the script first.

## 0. Install and first run (the user pasted the install prompt)

Speak the user's language (usually Hebrew), one step at a time, in plain words. Wait for them after every step that
needs their hands. The user may not be technical: never ask them to type commands, run them yourself.

**Step 1: free tools.** Install whatever is missing, without asking. All of it is free.

| Tool | Check | Windows (winget) | Mac (Homebrew) |
|---|---|---|---|
| git | `git --version` | `winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements` | `xcode-select --install` |
| Python 3.10+ | `python --version` (Mac: `python3`) | `winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements` | `brew install python@3.12` |
| ffmpeg | `ffmpeg -version` | setup.py installs it | setup.py installs it |

- On a Mac without Homebrew, install it first (https://brew.sh), and tell the user the Mac may ask for their password.
- After a winget install, the new tool is often not on PATH in this session. Call it by its full path, e.g.
  `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`, or ask the user to restart Claude Code and paste the prompt again.
- On Windows, if `python` opens the Microsoft Store or prints nothing, that is the Store stub: use the full path above.

**Step 2: the skill.** Clone the repo into `~/.claude/skills/twin-studio`, or `git pull` there if it already exists.

**Step 3: setup.** `python -I -X utf8 S/scripts/setup.py`. It installs the Python packages and ffmpeg, downloads the
Whisper model for captions (about 1.5 GB, once), creates the profile, tests the keys and ends with READY or NOT READY.
It is safe to run again. Fix every `[!!]` line it prints, then run it again.

**Step 4: keys.** Keys live in `~/.twin-studio/.env` (or in environment variables).
- Run `creator.py keys`. It opens that file in Notepad / TextEdit with an empty line per key. The user pastes the keys
  there and saves. This way a key never passes through the chat.
- Then run `creator.py check`. It tests each key against its service (free) and shows the HeyGen API wallet.
- If the user pastes a key into the chat anyway, write it into the `.env` file for them, and tell them in one line that
  next time the file is the safer place.
- Never print a key back.

| Key | Needed | Where |
|---|---|---|
| `HEYGEN_API_KEY` | Required | HeyGen → Settings → API. The API wallet is separate from the HeyGen plan: Add funds ($10–15 to start). |
| `ELEVEN_API_KEY` | Recommended | ElevenLabs → Developers → API Keys. Cloning a voice needs Starter or higher. Without it, the HeyGen voice is used. |

**Step 5: the twin and the voice.**
- `creator.py looks` lists the user's own avatars. Offer them in one AskUserQuestion (names, not IDs) and save the choice.
  - Empty list: the user creates the twin in HeyGen first (Avatars → Create avatar). A twin from a video needs a short
    consent recording: they read a code to the camera, in good light, face to the camera. A photo avatar needs no consent.
    It takes a few minutes to be ready. Then run `looks` again.
  - Prefer a landscape look framed from the chest up.
- `creator.py voices` lists their cloned voices (ElevenLabs first). Same: offer them, save the choice.
  - No ElevenLabs clone: Voices → Add voice → Instant voice clone, 1–2 minutes of clean speech. Or use the HeyGen voice
    that came with the twin: `voice.provider=heygen` + `heygen.voice_id`.

**Step 6: the rest** in one AskUserQuestion round:
- The name shown on screen, and a short role line, e.g. "Mortgage advisor".
- The language.
- Brand colours: `ink` (dark), `paper` (light) and `accent`, as 6-digit hex. If they have none, offer black, off-white and red.
- The default frame and aspect.
- Captions on or off.
- Where clips go (a folder they can find, e.g. `Documents/twin-clips`).

Save everything with one `creator.py set` call (it rejects a bad colour or option and says why):
```bash
python -I -X utf8 S/scripts/creator.py set name="דנה כהן" role="יועצת משכנתאות" language=he direction=rtl \
  heygen.look_id=<id> voice.provider=elevenlabs voice.voice_id=<id> \
  brand.ink=#1B1B1B brand.paper=#FAF7F2 brand.accent=#2F6BFF \
  clip.frame=side clip.aspect=16:9 clip.captions=true projects_root=D:/clips
```
- Use `direction=ltr` for any language that isn't written right to left.
- The user's own rules ("always address both genders", "never say cheap") go in `rules` as a JSON list. Read them before you write any script.

**Step 7: prove it.** Run `setup.py` once more until it says READY, then `scripts/selftest.py --out <projects_root>/selftest`.
It builds a 4-second clip with a stand-in figure in the user's colours and name tag, with no HeyGen cost. Show the user
the files. Then offer the first real clip (section 1), price first.

The profile (`~/.twin-studio/profile.json`) is shared with `twin-reel-studio`. If it already exists, keep it and fill in
only what's missing. Don't ask these questions again later: a change is one `creator.py set` call.

**Errors** come out as one `[!!]` line plus a `fix:` line. Explain them in plain words and do the fix yourself when you can.

## 1. Making a clip

1. **The script.**
   - If the user gives one, keep their words. Fix only obvious typos, and show any change.
   - If they give a topic, write it for them, in their language and their voice.
   - Write it to be heard, not read: short sentences, one idea each.
   - Separate paragraphs with a blank line. Each paragraph is voiced on its own, and the gap between paragraphs is a natural pause.
   - Write English terms in Latin letters. Spell a risky word the way it should sound.
   - **Clear for a stranger:** say what a thing is before talking about it.
   - **Length:** about 2.4 spoken words per second. 30–60 s suits a social clip; 60–120 s suits an explainer.
2. **Price check first.**
   - Run `make.py ... --dry-run`. It prints the estimated length and HeyGen cost (about $0.12 per second, billed to the user's HeyGen API credits), plus `ready` and any `blockers` (a missing key, avatar or voice). Fix the blockers first: a real run refuses to start while any remain, so nothing is spent on a run that would fail.
   - Show it with the script, and wait for the OK before the first render of a new script.
3. **Run it.**
   - Example: `python -I -X utf8 S/scripts/make.py --text-file script.txt --out <projects_root>/<clip-name> [--frame ...] [--aspect ...] [--title "..."]`.
   - The HeyGen render takes about 1–3 minutes for every 10 seconds of video. Run long ones in the background.
4. **Check before you hand it over.**
   - Look at 2–3 frames: `frame.py --twin <folder>/clip_twin.webm --out check.png --still 3 ...`. The same flags give a different layout without a new HeyGen render.
   - Check the captions against the script.
5. **Report:** the file path, the length, and what it cost.

**Re-styling is free.** The twin render (`clip_twin.webm`) and `narration.wav` stay in the folder. A new frame, aspect, title or caption setting is one `frame.py` call and costs no new HeyGen render:

```bash
python -I -X utf8 S/scripts/frame.py --twin <f>/clip_twin.webm --audio <f>/narration.wav --script <f>/script.txt \
  --out <f>/clip_square.mp4 --frame spotlight --aspect 1:1
```

**Changing one sentence:** re-voice only that paragraph, render only its segment with `twin.py --audio`, and join it at the paragraph pause. A full re-render costs the full price again.

## 2. The scripts

| Script | What it does |
|---|---|
| `scripts/setup.py` | One-time install and check: packages, ffmpeg, the Whisper model, the profile, the keys. READY / NOT READY. |
| `scripts/selftest.py` | A free end-to-end test with a stand-in figure: no HeyGen, no keys |
| `scripts/creator.py` | The profile and keys: `doctor`, `init`, `keys`, `check`, `looks`, `voices`, `set`, `show` |
| `scripts/make.py` | The whole chain in one command: voice → twin → frame |
| `scripts/voice.py` | Narration in the cloned voice, one call per paragraph: sped up ×1.2 (`clip.tempo`), silences trimmed, joined into one file |
| `scripts/twin.py` | The HeyGen v3 API: lip-syncs your twin to an audio file (`--audio`) or has it speak a script (`--script`). Takes `--webm` (transparent), `--aspect`, `--dry-run`. |
| `scripts/frame.py` | Builds the frame. It finds where you are in the render, places and scales you, draws the background in your brand colours, and adds a soft shadow, captions (`faster-whisper` timing with the script's spelling), the name tag and the title. `--still <sec>` renders a single preview frame. |
| `fonts/` | Rubik (Medium and ExtraBold, OFL licence). It covers Hebrew and Latin. |

## 3. Rules

- Render the avatar with `avatar_v`, the default. `avatar_iv` tends to grin with a wall of teeth.
- Always pass the voice explicitly. A HeyGen look's own default voice is a stock voice, not the user's.
- Never spend HeyGen credits without the user's OK on the script and the price.
- Save clips under `projects_root`. Keep each clip in its own folder.
- The user's twin, voice and keys are personal. Never upload them anywhere except HeyGen and ElevenLabs.
