# Week 3 Progress — LiteLecture (CAC 2026)

**Week of:** Jun 8, 2026 (built early, May 28)
**Phase:** A (Foundation)
**Status:** Player works. The plain data page is now an actual player.

---

## What got done — Week 3 milestone

The Week 2 page just dumped JSON. It now plays a lecture:

1. **KaTeX math rendering** (`src/Formula.jsx`)
   - LaTeX from the `symbols` array renders as real, typeset math.
   - Malformed LaTeX falls back to showing the raw string instead of crashing the page.

2. **Playback timeline + controls** (`src/App.jsx`)
   - A clock advances 10x/second while playing.
   - Play / Pause / Restart buttons + a drag-to-seek scrubber.
   - Transcript line (caption) and formulas (whiteboard) both sync to the current time.
   - Formulas appear during their `[t, t + duration_s]` window.

3. **Web Speech API (text-to-speech)**
   - Each transcript chunk is spoken aloud by the browser's built-in voice as the clock reaches its timestamp.
   - Pause/restart/scrub all cancel and re-sync speech so old lines don't replay.

## Verified
- `npm run build` compiles cleanly (KaTeX fonts bundled, ~124 KB gzipped JS).
- Preview server: page 200, demo file 200.

## Note on the environment
- The Dropbox-mounted folder truncated several files mid-write during this session
  (sync race between the editor and Dropbox). Files were rewritten directly to disk to fix it.
- The Linux `node_modules`/`dist` inside the Dropbox `web/` folder are gitignored and can be
  deleted on your machine; run `npm install` locally to get the Windows versions.

## Pending — pick up here
1. On your machine: `cd web && npm install` (katex was added as a new dependency).
2. Run `npm run dev` and try Play — confirm math renders, captions show, and the voice reads lines.
3. Smoke test on Chrome, plus Safari / Android Chrome if available.
4. Commit Week 3: `git add web/ notes/week-3-progress.md` then commit/push.

## Week 4 (next, Phase B) — start the real encoder
- `src/encoder/` Python CLI: yt-dlp + ffmpeg → download a Khan Academy MP4, extract audio + sample frames.

## Still carried over
- Rebuild `public/demos/limits-intro-30s.litelec` from real Whisper output (current one was approximated from memory).

---

## IMPORTANT finding (May 28) — demo is fabricated, confirmed against real video

Chen compared the player against the actual Khan Academy video (screenshot at 1:45).
The current `public/demos/limits-intro-30s.litelec` is WRONG — it was hand-typed from
memory, not extracted.

- Real video shows: f(x) = (x-1)/(x-1)  =>  f(x) = 1, x != 1 ;  f(1) = 0/0 = undefined
- Fabricated demo invented: f(x) = (x^2-1)/(x-1), f(2)=3  (a different, made-up example)

The PLAYER is real and works; the FILE it plays is fake. Real video->file extraction
(the encoder) does NOT exist yet.

## NEXT SESSION (tomorrow) — Plan B: build the real encoder (Week 4 kickoff)

Goal: generate the .litelec from the ACTUAL video, not from memory.
- Transcribe real audio with Whisper (Week 1 proved it runs on Chen's Windows machine;
  the sandbox likely can't download the models due to locked-down network — confirm and,
  if blocked, run transcription on Chen's machine).
- OCR the on-screen math (Pix2Text) -> get f(x)=(x-1)/(x-1) etc. from real frames.
- Write a correct limits-intro .litelec from real Whisper + OCR output.
- Then the player + the real file = an honest size/quality comparison.

(Deferred: Plan A quick hand-patch of the demo — Chen chose to wait and do the real thing.)
