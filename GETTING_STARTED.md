# Getting Started — Week 1 (May 25-31, 2026)

A step-by-step guide to set up the LiteLecture project from zero. Budget: ~7 hours total, spread across the week.

---

## Day 1 (Monday or Tuesday) — Create the GitHub repo · 30 min

1. Go to https://github.com/new
2. Settings:
   - **Repository name:** `litelecture`
   - **Description:** "Low-bandwidth, accessible educational video player. Congressional App Challenge 2026."
   - **Visibility:** Private (will go public in October)
   - **Initialize with:**
     - ✅ README
     - ✅ `.gitignore` → choose **Node**
     - ✅ License → **MIT**
3. Click **Create repository**.
4. Clone it locally. Pick a sensible folder, e.g. `~/code/`:
   ```bash
   cd ~/code
   git clone git@github.com:YOUR_USERNAME/litelecture.git
   cd litelecture
   ```
5. Add the starter files from your LiteLecture workspace folder:
   ```bash
   mkdir -p docs public/demos
   # Copy the two files I drafted into these folders.
   ```
   - `docs/litelec-spec.md`
   - `public/demos/limits-intro-30s.litelec`
6. Extend `.gitignore`:
   ```gitignore
   # Python encoder
   __pycache__/
   *.pyc
   .venv/
   venv/

   # Whisper models (large files)
   models/
   *.bin

   # Secrets
   .env
   .env.local

   # Build outputs
   dist/
   build/
   .vercel/

   # OS junk
   .DS_Store
   Thumbs.db
   ```
7. First commit:
   ```bash
   git add .
   git commit -m "Initial commit: spec v0.1 + first demo .litelec"
   git push
   ```

**Done when:** Your repo on GitHub shows the README, LICENSE, `docs/litelec-spec.md`, and `public/demos/limits-intro-30s.litelec`.

---

## Day 2 (Wednesday) — Install Pix2Text (open-source math OCR) · 30 min

**Why Pix2Text instead of MathPix:** As of 2026, MathPix Convert removed its free tier and requires a $19.99 setup fee. LiteLecture is 100% open-source, so we use [Pix2Text](https://github.com/breezedeus/Pix2Text) — a local, MIT-licensed library that recognizes both layout and formulas from images. No API key, no monthly cost, runs on your laptop.

1. Make sure you have Python 3.9+ installed:
   ```bash
   python --version
   ```
   If it says Python 2.x or "command not found", install Python 3.11+ from https://python.org.

2. Create a virtual environment for the encoder (one-time setup, keeps dependencies isolated):
   ```bash
   cd /path/to/litelecture
   python -m venv .venv
   # Activate it:
   # macOS/Linux:  source .venv/bin/activate
   # Windows:      .venv\Scripts\activate
   ```
   Your terminal prompt should now show `(.venv)` at the start.

3. Install Pix2Text:
   ```bash
   pip install pix2text
   ```
   First run downloads model weights (~500 MB) — takes ~5 min on broadband.

4. Smoke test on any formula image:
   ```bash
   # Save any image of a formula as test.png (a screenshot from a math lecture works)
   python -c "from pix2text import Pix2Text; p = Pix2Text(); print(p.recognize_formula('test.png'))"
   ```
   You should see a LaTeX string printed.

**Done when:** Pix2Text prints LaTeX for a test formula image.

⚠️ Don't commit `.venv/` to git — your `.gitignore` already excludes it. Don't commit model files either (they're ~500 MB).

---

## Day 3 (Thursday or Friday) — Install faster-whisper · 15 min

**Why faster-whisper instead of whisper.cpp:** faster-whisper is a Python re-implementation of OpenAI Whisper that runs 4× faster than whisper.cpp on CPU and installs cleanly via `pip` on Windows. No C++ build tools required. Same accuracy.

Make sure your virtual environment is active (you should see `(.venv)` at the start of your prompt). Then:

1. Install faster-whisper:
   ```bash
   pip install faster-whisper
   ```
   ~30 seconds.

2. Smoke test on a sample audio file. If you don't have one handy, download a sample:
   ```bash
   # Windows (PowerShell):
   Invoke-WebRequest -Uri "https://github.com/ggerganov/whisper.cpp/raw/master/samples/jfk.wav" -OutFile "jfk.wav"
   # macOS/Linux:
   curl -L -o jfk.wav https://github.com/ggerganov/whisper.cpp/raw/master/samples/jfk.wav
   ```

3. Transcribe it:
   ```bash
   python -c "from faster_whisper import WhisperModel; m = WhisperModel('base.en'); segs, _ = m.transcribe('jfk.wav'); print(' '.join(s.text for s in segs))"
   ```
   First run downloads the `base.en` model (~150 MB). After that, transcription itself takes ~3 seconds for an 11-second clip on a typical laptop. You should see something like:
   > "And so my fellow Americans, ask not what your country can do for you..."

**Done when:** the JFK transcript prints to your terminal.

### Notes on model size

| Model | Size | Speed (laptop CPU) | Quality |
|---|---|---|---|
| `tiny.en` | 39 MB | very fast | OK for testing |
| `base.en` | 74 MB | fast | good — recommended for development |
| `small.en` | 244 MB | medium | very good |
| `medium.en` | 769 MB | slow | excellent — recommended for final Demo encoding |
| `large-v3` | 1550 MB | very slow | best, but overkill for our use |

Use `base.en` for development, switch to `medium.en` when encoding the final demos in September.

---

## Day 4 (Saturday) — Smoke test the pipeline · 60 min

The point of this exercise: prove to yourself that you can transcribe a real Khan Academy clip before any code exists.

1. Install yt-dlp:
   ```bash
   pip install --user yt-dlp
   # or on macOS:
   brew install yt-dlp
   ```
2. Download just the audio of a 30-second clip:
   ```bash
   cd ~/code/whisper.cpp

   # The URL from your demo .litelec
   yt-dlp -x --audio-format wav \
     --download-sections "*0:00-0:30" \
     -o "limits-intro.%(ext)s" \
     "https://www.khanacademy.org/math/ap-calculus-ab/ab-limits-new/ab-1-2/v/introduction-to-limits-hd"
   ```
3. Run whisper:
   ```bash
   ./main -m models/ggml-large-v3.bin -f limits-intro.wav -otxt
   ```
4. Open `limits-intro.wav.txt` and compare to your hand-crafted transcript in `limits-intro-30s.litelec`.

**Done when:** Whisper's output matches the spirit of your hand-typed transcript. They won't be word-identical — paraphrasing is expected.

⚠️ If yt-dlp fails on the Khan Academy URL, fall back to a Khan Academy clip on YouTube (`youtube.com/khanacademy`). You're using it for personal R&D, not redistribution.

---

## Day 5 (Sunday) — Weekly review · 30 min

Open the action plan file:
- Did you finish Days 1-4? Y/N
- Any blockers?
- One-line note about what's next.

If you finished everything, you're on track. If you fell behind on Day 3 or 4 specifically, that's fine — install + smoke test can slide a week without breaking Phase A.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make` fails on macOS with missing tools | Run `xcode-select --install` |
| whisper.cpp is too slow | Use `medium.en` instead of `large-v3` |
| yt-dlp says "video unavailable" | Try the YouTube mirror or use a different KA clip |
| Pix2Text install fails with torch errors | `pip install torch --index-url https://download.pytorch.org/whl/cpu` first, then retry pix2text |
| Pix2Text formula recognition is slow | Normal on CPU (~2-5s per image). Acceptable for batch encoding. |
| Git push refused (SSH key not set up) | Set up an SSH key per GitHub's docs, or use HTTPS clone instead |

---

## What you'll have by end of Week 1

- A GitHub repo with spec + first demo `.litelec`
- A working local Pix2Text install (math OCR)
- A working local Whisper transcription tool
- A proven (informal) end-to-end smoke test on a real Khan Academy clip
- 100% open-source toolchain — zero recurring cost

This is the foundation for Week 2 (start scaffolding the React Player).
