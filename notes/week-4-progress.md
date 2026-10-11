# Week 4 Progress — LiteLecture (CAC 2026)

**Built:** Jun 2, 2026 (Plan B — the real encoder)
**Phase:** B (Real Encoder)
**Status:** Encoder written + tested for the offline stages. AI stages run on Chen's machine.

---

## Why this exists

The old demo (`limits-intro-30s.litelec`) was hand-typed from memory and was WRONG
(invented an (x^2-1)/(x-1) example; the real video is (x-1)/(x-1), confirmed by a
screenshot at 1:45). The player was real but playing fabricated content. This encoder
replaces fabrication with real extraction.

## What got built — `src/encoder/`

- `encode.py` (295 lines) — 4-stage pipeline:
  1. **prepare** — ffmpeg: 16 kHz mono audio + one frame every N seconds + duration
  2. **transcribe** — faster-whisper (the exact API proven in Week 1) -> real transcript,
     resegmented into short 3-8 word chunks on sentence boundaries
  3. **ocr** — Pix2Text reads on-screen math (EXPERIMENTAL on handwriting); deduped
  4. **assemble** — writes a spec-compliant `.litelec`
  - Heavy libs imported lazily, so ffmpeg + assembly work without the AI libs.
  - `--symbols FILE` overrides flaky OCR with hand-verified formulas (honest: noted in
    `modification_note`).
- `limits-symbols.sample.json` — the REAL formula from the screenshot, ready to use.
- `README.md` — beginner run instructions.

## Tested (in sandbox)
- `python -m py_compile` — syntax OK.
- **prepare** on a synthetic 30s video: audio.wav (16 kHz mono) + 6 frames at
  t=0,5,10,15,20,25 + duration 30.0s via ffprobe. Works.
- **assemble** with mock transcript + verified symbols -> validated against spec
  section 11 rules 1-7: VALID. ~0.9 KB.

## NOT tested here (sandbox limits — confirmed honestly)
- YouTube is BLOCKED in the sandbox -> yt-dlp download must run on Chen's machine.
- HuggingFace is BLOCKED -> Whisper/Pix2Text models can't download here.
- The Dropbox mount throws I/O errors reading the existing mp4s, so prepare was tested
  on a synthetic video instead. ffmpeg logic is identical.

## NEXT — Chen runs on the Windows machine
1. `.venv\Scripts\Activate.ps1`
2. `python src\encoder\encode.py "https://www.youtube.com/watch?v=riXcZT2ICjA" --title "Khan Academy - Introduction to Limits" --creator "Khan Academy" --symbols src\encoder\limits-symbols.sample.json --out web\public\demos\limits-intro.litelec`
3. In `web\src\App.jsx` set `DEMO_URL = "/demos/limits-intro.litelec"`, then `cd web && npm run dev`.
4. Compare against the YouTube video — now it's an honest comparison.

## Follow-ups
- OCR quality on handwriting is the open problem (Week 6). For now use `--symbols`.
- Decide segment/timestamps: screenshot formula appears ~1:45, not in the first 30s.
- Once a real file plays, delete the fabricated `limits-intro-30s.litelec`.

---

## BACKLOG — voice quality (not scheduled; Chen will decide when)

The TTS voice works and is in sync, but sounds choppy/robotic. Options, cheapest first:

1. **Free, offline (recommended for LiteLecture's mission):**
   - Speak FULL SENTENCES, not the 3-8 word caption fragments. The choppiness is
     mostly because each fragment is a separate utterance with no carried intonation.
     Fix: merge transcript chunks into sentences for the voice; keep short chunks for
     captions. (Biggest win for least effort.)
   - Pick a nicer installed Windows voice (e.g. Microsoft "Aria"/"Guy") via
     speechSynthesis.getVoices(); add a voice picker + rate/pitch controls.
2. **Better offline engine:** Piper TTS (open-source, local, neural, much warmer).
   Fits the offline/rural goal. More integration work.
3. **Cloud neural (ElevenLabs/Google/Polly):** most human, but costs money + needs
   internet -> undercuts the "offline, no servers" story. Probably avoid.
4. **Different path entirely:** embed real Opus ~8 kbps audio (already in the spec) to
   get Khan's actual voice. Tiny-ish file, not TTS.

Recommendation: do #1 (sentences + better installed voice) when ready. Free, offline,
removes most of the robotic feel.

---

## 20-Day Sprint — Day 1 DONE (Jun 2)

Switched to the 20-day sprint plan (`LiteLecture-20day-sprint.md` at LEO-LLM root).
Target finish ~June 22. Scope = product + materials; ~3-4 hrs/day; formal user
testing cut to one light session.

### Completed today
- **Committed Week 3-4 work to GitHub** (commit 218963f): player + encoder + 2 demo
  files + notes. 18 files, 4406 insertions. Push succeeded to
  github.com/joleneqian-sv/litelecture (main).
- **Voice quality pass (player):** transcript fragments now merged into full
  SENTENCES for speech (removed choppiness); added a voice picker + speed slider;
  formulas re-synced to overlap the spoken sentence's time range.
- **DEPLOYED TO VERCEL — LiteLecture is LIVE.** First deploy failed (Root Directory
  was repo root); fixed by setting Root Directory = `web`, redeployed, success.
  Auto-deploys on every `git push` from now on.

### Live URL
- TODO: paste the litelecture-*.vercel.app URL here next session (Chen to grab it
  from the Vercel dashboard).

### Pickup next session — Sprint Day 2
- Encode demo #2: a Khan Academy ALGEBRA video with the encoder
  (`python src\encoder\encode.py "<url>" --title ... --creator "Khan Academy"
   --symbols <verified.json> --out web\public\demos\<name>.litelec`).
- Hand-verify its formulas (OCR still experimental).
- Add a demo-picker later (Sprint Day 5) once there are 2-3 demos.

### Still-open housekeeping (quick, do anytime)
- `.venv` is tracked in git -> remove with `git rm -r --cached .venv` then commit
  (it's already in .gitignore). 2-min cleanup.
- Old fabricated `limits-intro-30s.litelec` still in the repo -> delete once the
  real demo is the only one referenced.

---

## 20-Day Sprint — Day 2 DONE + extras (Jun 2)

### Second real demo
- Encoded Khan "Write 18% as a decimal and a fraction in simplest form"
  (Pre-Algebra), ~3.5 min, 89 real transcript chunks -> `web/public/demos/algebra.litelec`.
- Encoder upgraded: auto-fetches real title/uploader/url from yt-dlp; `--no-playlist`
  so a playlist URL only grabs the one video.
- Formulas added from the spoken transcript (grounded, not OCR): 18% = 18/100 (0:12),
  18/100 = 0.18 (1:09), 18/100 = 9/50 (1:35).

### Player: demo picker (pulled forward from Sprint Day 5)
- "Lecture:" dropdown switches between Limits and Pre-Algebra; reloads + resets
  playback cleanly on change.

### NEW feature: emphasis / annotations
- Added an `emphasis` track to the `.litelec` spec (docs/litelec-spec.md §9.5):
  { t, target (symbol index), style: circle|box|underline|highlight, duration_s }.
- Player renders a clean animated annotation (4 styles); stores intent, not the
  hand-drawn pixels -> tiny + screen-reader announceable (good AccessLearn + write-up point).
- Percent demo: circles the final 9/50 answer at ~1:59 (when he says "nine fifties").
- Auto-detecting real circles from video = future encoder work (CV).

### Build status
- `npm run build` clean, no warnings. (Had to fully rewrite index.css once — Dropbox
  sync truncated an appended file mid-rule; watch for this.)

### NOT yet committed
- Uncommitted: web/ (player + algebra demo + emphasis), src/encoder/ (auto-title),
  docs/litelec-spec.md (emphasis spec). Commit covers those 3 paths; Vercel auto-deploys on push.

### Pickup next — Sprint Day 3
- Encode demo #3 (e.g., an MIT OCW segment, or another Khan topic). Same flow:
  run encoder -> verify formulas -> add to DEMOS list in App.jsx.
- Optional: add emphasis to the limits demo too (underline f(1)=0/0 "undefined").

### Still-open housekeeping
- Grab the live vercel.app URL -> save here.
- `.venv` git untrack: `git rm -r --cached .venv` then commit.
- Delete fabricated `limits-intro-30s.litelec` once unused.

---

## 20-Day Sprint — Day 6 DONE (size comparison), pulled forward (Jun 2)

### Size-comparison card (the visual money shot)
- Player shows "Why it's so small": red bar (original video) vs green sliver
  (.litelec) + big "≈ Nx smaller", recomputed per lecture.
- Player measures the real .litelec byte size live (Blob size of the fetched text).
- Encoder now records `source.original_bytes` (exact downloaded MP4 size) for every
  new demo; added a `--measure` mode (download, print exact size, exit — no transcribe).

### Real measured numbers (honest)
- Limits: 18.6 MB video -> 31 KB file = ~614x smaller.
- Percent: 4.1 MB video -> 10.5 KB file = ~400x smaller.
- NOTE: these are TTS-only files (no audio). Earlier "thousands x" guess was wrong;
  these Khan videos are low-bitrate. Honest framing: "~400-600x smaller, fully offline,
  synthetic narration." Embedding Opus audio later would lower the ratio.

### Build status: clean, no warnings.

### Pickup next — Sprint options
- Day 3: third demo (encode another video). OR
- Day 7: accessibility mode (font size / high contrast / spoken math). OR
- the .venv git untrack housekeeping.

### Still-open housekeeping
- Grab live vercel.app URL -> save here.
- `.venv` untrack: `git rm -r --cached .venv` then commit.
- Delete fabricated `limits-intro-30s.litelec` once unused.

---

## 20-Day Sprint — Day 10 DONE (offline / PWA) (Jun 15)

Made LiteLecture an installable, offline-capable Progressive Web App.
- `web/public/manifest.webmanifest` (name, icon, theme, standalone), `web/public/icon.svg`.
- `web/public/sw.js` service worker: precaches the shell + both demo files, cache-first
  at runtime (anything loaded online is saved for offline).
- `index.html`: manifest + theme-color + icon links. `main.jsx`: registers the SW
  ONLY in production (import.meta.env.PROD) so dev hot-reload stays clean.
- Player shows an online/offline badge next to the title (● Online / ● Offline — still works).

### How to test offline (IMPORTANT — not in `npm run dev`)
The service worker is production-only. Test via the LIVE Vercel site (after pushing),
or locally with `npm run build` then `npm run preview`:
  1. Load the site once (online) so the SW caches everything.
  2. Chrome DevTools (F12) → Network tab → set "Offline" (or turn off wifi).
  3. Reload — the app + both lectures still play. Badge flips to "Offline — still works".
  4. Chrome address bar shows an Install icon -> installs as a standalone app.

### Why it matters (write-up)
Proves the core mission: a rural/low-bandwidth learner loads once (or gets the file
any way) and then studies with NO connection. Combined with ~7 KB gzipped files,
LiteLecture works where streaming video can't.

### NOT yet committed
- web/ (PWA files, online badge). Commit covers web/. Vercel auto-deploys on push.

---

## Sprint extra — MathSpeak auto-fallback (Week 9 item, Jun 15)

- `web/src/mathspeak.js`: heuristic LaTeX -> spoken English (frac, powers, sqrt,
  subscripts, =, +, -, implies, neq, times, div, percent, f(x)->"f of x", etc.).
- Player `speechFor()` now: hand-written math_speech if present, ELSE auto-generate
  from the LaTeX. So every formula in any future demo is spoken in AccessLearn mode
  with zero manual authoring. Matches spec §9 ("falls back to a built-in MathSpeak ruleset").
- Tested on all demo formulas + sqrt/powers/neq/implies — sensible output.
- Current 2 demos keep their polished hand-written descriptions; auto is the net beneath.

### Uncommitted now: web/ (PWA from Day 10 + mathspeak). Commit covers web/ + notes/.

---

## SESSION SUMMARY — Jun 15 (end of session)

### Sprint status (20-day plan): well ahead. Build side largely DONE.
Committed + pushed (live on Vercel via auto-deploy):
- Player: KaTeX math, sentence-grouped TTS w/ voice picker + speed, formula sync.
- Lecture picker (2 real demos: Limits, Percent).
- Emphasis/annotations (circle on 9/50).
- Size-comparison card + expandable byte breakdown.
- AccessLearn mode (high-contrast, large text, spoken math) + auto MathSpeak fallback.
- Offline PWA (manifest, service worker, installable) + online/offline badge.
- Encoder: yt-dlp+ffmpeg+Whisper pipeline, auto-title, --measure, records original_bytes.

Latest commit: 209c58f.

### What's LEFT (mostly submission materials, not code)
1. **Written submission** (250-500 words) — I can draft from everything built. HIGH value.
2. **Demo video** (~4 min) — needs Chen + parent (consent for minor). Record ~late.
3. **Repo polish** — LICENSE (MIT), ATTRIBUTION.md, real README; then make repo PUBLIC.
4. **Third demo** (optional) — more dataset breadth.
5. **Housekeeping** — `.venv` untrack (`git rm -r --cached .venv`); delete old
   fabricated `limits-intro-30s.litelec`; grab + save the live vercel.app URL.

### Recommended next step
Have Claude draft the **written submission** next session (fast, high-leverage),
then do repo polish (LICENSE/README/ATTRIBUTION + make public). Save video for last.

---

## Third demo IN PROGRESS — pick up next time (Jun 15)

- Encoded `web/public/demos/demo3.litelec` — Khan "Solving a more complicated equation"
  (Algebra I, linear equations), 520s, 261 chunks, original 8.5 MB.
- Added 5 formulas from the spoken transcript: 3x+5=17 (0:15) -> 3x=12 (3:25) ->
  x=4 (4:47); then 7x=-8 (7:35) -> x=-8/7 (8:13). Circle emphasis on x=4 and x=-8/7.
- Uses AUTO MathSpeak (no hand-written math_speech) — first demo to showcase that.
- Added to the DEMOS dropdown in App.jsx ("Algebra I — Solving 3x + 5 = 17 (Khan)").
- Build passes clean.

### NOT committed yet. To finish next time:
1. (optional) refresh localhost, pick the Algebra I lecture, verify the 5 formulas line
   up with the narration; screenshot the board if you want exact-match fidelity and I'll
   adjust timings/layout.
2. Commit: `git add web/ notes/` -> commit -> push. (covers demo3 + dropdown + this note)
3. Vercel auto-deploys; 3 lectures then live.

---

## URTC pivot (Jun 27)

Started the MIT URTC paper track (see URTC-plan.md, supervisor-plan.md,
URTC_paper/draft-v1.md at LEO-LLM root). Supervisor found.
- Built `experiments/baseline_cer.py` — the paper's core formula-CER experiment.
- First real result: flat 33% CER across bitrates (static slides compress too well +
  constant OCR error). Full details + the A/B/C design decision in
  `notes/urtc-experiment-progress.md`.

### UNCOMMITTED (web demo work + experiment): pick up next time
- web/: demo3 (Algebra I) + dropdown entry, whiteboard "keep last formula" fix,
  Tokens manipulatives renderer (3x boxes + dots), demo3 tokens/emphasis.
- experiments/: baseline_cer.py, README.md, SAMPLE_cer_vs_bitrate.png.
- Plus all earlier uncommitted player work since last push (209c58f) if any.
- Commit covers web/, experiments/, notes/. Vercel auto-deploys web/.
