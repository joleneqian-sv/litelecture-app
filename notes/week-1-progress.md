# Week 1 Progress — LiteLecture (CAC 2026)

**Week of:** May 25, 2026
**Phase:** A (Foundation)
**Status:** Days 1–4 complete; Day 5 (weekly review) pending

---

## What got done this week

### Day 1 — GitHub repo
- Created `joleneqian-sv/litelecture` on GitHub
- Cloned to local: `litelecture`
- Resolved Windows Credential Manager + PAT auth issues
- Moved spec doc and starter files into repo

### Day 2 — Pix2Text (OCR for math)
- Replaced original MathPix plan with open-source Pix2Text
- Installed successfully in venv
- Verified: `Pix2Text loaded successfully`

### Day 3 — faster-whisper (transcription)
- Installed faster-whisper in venv
- Hit CUDA error (`cublas64_12.dll not found`) — fixed by switching to `device='cpu', compute_type='int8'`
- Verified: model loads and runs on CPU

### Day 4 — End-to-end smoke test ✅
- Installed yt-dlp via pip
- Installed ffmpeg 8.1.1 via winget (Gyan.FFmpeg) + manual PATH fix
- Downloaded 30s of audio from Khan Academy "Intro to Limits" (YouTube mirror: riXcZT2ICjA)
- Ran `transcribe_smoketest.py` — produced clean timestamped transcript
- Whisper recognized math vocabulary correctly: "limit," "calculus," "function," "f of x," "x minus 1"
- Language detection: en, probability 1.00

**Pipeline proven end-to-end:**
```
YouTube URL → yt-dlp → limits-intro.wav → faster-whisper → transcript
```

---

## Key findings from Day 4

1. **Whisper's segmentation is coarser than ideal.** Produced 5 chunks of 4–9 seconds each. Hand-typed demo had 8 chunks of 2–3 seconds. Encoder will need a post-processing resegmentation step.

2. **Verbatim ≠ semantic transcript.** Whisper transcribes what was said; LiteLecture's value is what was meant. Decision for Phase B: start with verbatim (path b), defer LLM-cleaning to Phase C (path a).

3. **The hand-typed demo (`limits-intro-30s.litelec`) was not authored by Chen.** It was generated from training-data recollection of the KA video by Claude, not transcribed. The file's `modification_note` says "paraphrased," but it was more like "approximated from memory." This demo should be rebuilt from real Whisper output before any external use (CAC submission, science fairs).

---

## Environment state (as of May 25, 2026)

- Python 3.12.8
- venv at `.venv\` (activate with `.venv\Scripts\Activate.ps1`)
- Installed in venv: pix2text, faster-whisper, yt-dlp
- System-level: ffmpeg 8.1.1 on PATH (via winget)
- PowerShell ExecutionPolicy: RemoteSigned (CurrentUser)
- Default Whisper model: `base.en` (~74 MB, cached locally)

---

## Files added this session

- `transcribe_smoketest.py` — quick 5-line script to test Whisper on any .wav
- `limits-intro.wav` — 30s audio extract from KA Intro to Limits
- `notes/week-1-progress.md` — this file

## Files updated this session

- `requirements.txt` — pix2text, faster-whisper, yt-dlp
- `GETTING_STARTED.md` — Pix2Text + faster-whisper paths (Days 2/3)
- `README.md` — open-source toolchain narrative

---

## Pending — pick up here tomorrow (Day 5, Sunday wrap-up)

1. **Commit and push the updated files.** Status check:
   ```powershell
   cd litelecture
   git status
   ```
   Then:
   ```powershell
   git add requirements.txt GETTING_STARTED.md README.md notes/week-1-progress.md transcribe_smoketest.py
   git commit -m "Week 1: open-source toolchain installed, smoke test passing"
   git push
   ```
   (Decide whether to commit `limits-intro.wav` — probably skip, it's a derivative of a CC BY-NC-SA work; better to keep it out of the repo or add `*.wav` to `.gitignore`.)

2. **Add `.gitignore` entries** for derived files:
   ```
   *.wav
   .venv/
   __pycache__/
   *.pyc
   models/  # in case Whisper model cache lands here
   ```

3. **Write 3–5 line reflection** at the bottom of this file: what worked, what surprised you, what to watch for in Week 2.

---

## Pending — bigger tasks for Week 2+

- Rebuild `public/demos/limits-intro-30s.litelec` from real Whisper output (replace the synthetic version)
- Phase B kickoff: build the actual encoder script (yt-dlp + Whisper + Pix2Text → .litelec writer)
- Decide on chunk resegmentation strategy (split Whisper segments on sentence boundaries)

---

## Action plan reference

See `LiteLecture-action-plan.md` for the full 22-week schedule. We're on track:
- Week 1 of 22 (May 25 → May 31)
- Kill-switch check: Aug 23
- Demo video record: Sep 28
- CAC submission deadline: Oct 30
