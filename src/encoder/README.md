# LiteLecture Encoder

Turns a real lecture video into a `.litelec` file. Nothing is invented:
the transcript comes from the actual audio (Whisper), and the on-screen math
comes from the actual frames (Pix2Text OCR) or from a formula file you verify
by hand.

## What runs where

| Stage | What it does | Where it must run |
|---|---|---|
| prepare | ffmpeg: extract audio + sample frames | anywhere (tested) |
| transcribe | faster-whisper: real transcript | your machine (needs the model) |
| ocr | Pix2Text: read on-screen math (experimental) | your machine (needs the model) |
| assemble | write the `.litelec` JSON | anywhere (tested) |

The download + AI stages need internet and the AI models, so run this on your
Windows machine — where Week 1 already installed everything (faster-whisper,
pix2text, yt-dlp, ffmpeg).

## One-time check

Open PowerShell in this repo and activate the virtual env from Week 1:

    .venv\Scripts\Activate.ps1

(You should see `(.venv)` at the start of the prompt.)

## Run it on the real limits video

    python src\encoder\encode.py "https://www.youtube.com/watch?v=riXcZT2ICjA" ^
      --title "Khan Academy - Introduction to Limits" ^
      --creator "Khan Academy" ^
      --license "CC BY-NC-SA 3.0" ^
      --out web\public\demos\limits-intro.litelec

That downloads the video, transcribes the real audio, attempts to read the math,
and writes the file straight into the player's demo folder.

### Trustworthy formula (recommended for now)

OCR on handwritten math is hit-or-miss. To guarantee the formula is correct,
use the verified file (it contains the real `f(x) = (x-1)/(x-1)` from the video):

    python src\encoder\encode.py "https://www.youtube.com/watch?v=riXcZT2ICjA" ^
      --title "Khan Academy - Introduction to Limits" ^
      --creator "Khan Academy" ^
      --symbols src\encoder\limits-symbols.sample.json ^
      --out web\public\demos\limits-intro.litelec

The transcript is still 100% real; only the formula comes from the verified file
(the `.litelec` records this honestly in `modification_note`).

## See it in the player

In `web\src\App.jsx`, change the demo path to the new file:

    const DEMO_URL = "/demos/limits-intro.litelec";

Then `cd web` and `npm run dev`. Now the player shows the REAL transcript.

## Useful options

    --frame-interval 5     seconds between sampled frames (default 5)
    --model base.en        Whisper model (small.en / medium.en = better, slower)
    --stages prepare,transcribe,assemble   run a subset (e.g. skip flaky OCR)
    --keep                 keep the intermediate audio/frames for inspection
    --workdir DIR          put intermediate files in DIR

## Note

`limits-intro-30s.litelec` (the old demo) was hand-typed from memory and is
WRONG — it shows a made-up `(x^2-1)/(x-1)` example. Replace it with real encoder
output using the commands above.
