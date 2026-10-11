# LiteLecture

**Low-bandwidth, accessible educational lecture player.** A Congressional App Challenge 2026 entry.

LiteLecture turns an educational video into a tiny `.litelec` text file — averaging about
50 KB per minute, often **400–600× smaller** than the source video — that a web app replays
with synced captions, live-typeset math, and spoken narration. It works fully offline, and a
built-in accessibility mode reads every equation aloud for blind and low-vision learners.

> Live demo: **https://litelecture.vercel.app**

## Why

- **Rural & tribal students** can't load Khan Academy on metered or unreliable broadband
  (FCC: ~24% of rural U.S. households lack reliable broadband; tribal areas fare worse).
- **Visually impaired students** can't hear formulas read aloud — screen readers see an
  on-screen equation as an image, not as math.
- **Offline learners** in remote schools and post-disaster classrooms need lectures that fit
  on a USB stick or travel over a messaging app.

LiteLecture addresses all three with one web app: download a lecture once (each is the size of
a text message), then study it offline on any device, with every equation spoken in plain words.

## How it works

The source video is decomposed by the **encoder** into:

- **Transcript** — timestamped speech, via [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **Symbolic content** — formulas (and code), stored as exact LaTeX strings, via open-source
  [Pix2Text](https://github.com/breezedeus/Pix2Text) OCR plus hand-verification.
- **Scenes, emphasis, and "tokens"** — compact layout hints, annotations, and instructor
  manipulatives stored as counts, not pixels.

These pack into a `.litelec` JSON file. The **player** reconstructs playback with deterministic
LaTeX rendering ([KaTeX](https://katex.org)) and the browser's built-in TTS (Web Speech API).

Symbolic content is **never generated** — it is rendered from the source string, so
`x² + y² = z²` can never silently become `x³ + y² = z²`. That guarantees educational fidelity.

## Features

- Player: playback timeline, scrubber, synced captions, sentence-grouped narration with a
  voice picker and speed control, formulas synced to the spoken line.
- Three real demo lectures (Khan Academy Limits, Pre-Algebra Percent, Algebra I) with a picker.
- **AccessLearn mode**: high-contrast theme, large text, and spoken math (a built-in
  LaTeX→speech ruleset reads any formula aloud, with no manual authoring required).
- **Offline PWA**: installable, service-worker cached — loads and plays with no network.
- Size-comparison card showing the real byte savings for each lecture, computed live.

## Measured results

| Lecture | Source video | `.litelec` | Smaller by |
|---|---|---|---|
| Khan — Intro to Limits | 18.6 MB | 31 KB | ~614× |
| Khan — Percent → Decimal/Fraction | 4.1 MB | ~11 KB | ~400× |

Both are TTS-only (no embedded audio). Honest framing: *~400–600× smaller, fully offline,
synthetic narration.* See [`notes/size-breakdown.md`](./notes/size-breakdown.md).

## Repository layout

```
litelecture/
├── docs/
│   ├── litelec-spec.md              File format specification
│   └── cac-written-submission.md    CAC written submission draft
├── web/                             React + Vite PWA player (deployed on Vercel)
│   ├── src/                         App, Formula (KaTeX), Tokens, MathSpeak
│   └── public/demos/*.litelec       Pre-encoded demo lectures
├── src/encoder/                     Python encoder: yt-dlp + ffmpeg + Whisper + Pix2Text
├── notes/                           Week-by-week progress notes
├── GETTING_STARTED.md               Setup guide
├── ATTRIBUTION.md                   Source-video and open-source credits
└── LICENSE                          MIT
```

## Running it

**Player** (from `web/`):

```bash
npm install
npm run dev        # local dev
npm run build      # production build
npm run preview    # test the offline PWA (service worker is production-only)
```

**Encoder** (from repo root, in the Python venv): see
[`src/encoder/README.md`](./src/encoder/README.md) and [`GETTING_STARTED.md`](./GETTING_STARTED.md).

## License & attribution

- **Tool code: MIT** — see [LICENSE](./LICENSE).
- **Demo content** in `web/public/demos/`: derived from Khan Academy lectures under
  **CC BY-NC-SA 3.0**. Each `.litelec` file carries its own license metadata.
- Full credits, including the open-source libraries used, are in [ATTRIBUTION.md](./ATTRIBUTION.md).

## Acknowledgements

Built for the [Congressional App Challenge](https://www.congressionalappchallenge.us) 2026.
