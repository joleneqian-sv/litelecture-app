# Baseline formula-fidelity experiment (URTC §V.B)

The paper's core evidence: how much does ordinary video compression damage a
lecture's formulas, vs LiteLecture which keeps them exact?

## Design (controlled, reproducible — no network needed)
1. Render each ground-truth formula (from a `.litelec`'s `symbols`) as a clean,
   centered slide image.
2. Build the slides into a short pristine video (each slide a few seconds).
3. Compress that with H.265 (`libx265`) and AV1 (`libaom-av1`) at low bitrates.
4. Read each formula back from the degraded slide with math-OCR (Pix2Text) and
   compute **CER** (character error rate) vs the known LaTeX.
5. `.litelec` stores the formula as exact text -> **CER = 0** by construction.

Each frame contains ONLY the formula, so OCR isn't confused by clutter and the CER
is a real 0–100% number that isolates compression's effect on legibility.

(Earlier design OCR'd whole YouTube frames; that gave nonsense CER >100% because the
OCR read the entire board, not the target formula. This controlled version fixes it.)

## Run it (on your machine, in the repo venv)
    python experiments\baseline_cer.py web\public\demos\algebra.litelec --out experiments\out_algebra

Defaults: bitrates 25,50,100,200 kbps; codecs libx265,libaom-av1. Repeat for the
other two demos (limits-intro.litelec, demo3.litelec). Outputs: results.json,
results.csv, cer_vs_bitrate.png.

## Honesty notes
- Slides are static, and static video compresses well, so video may stay legible
  even at low bitrate. If so, that's a real finding — push bitrates lower (e.g.,
  `--bitrates 10,15,25,50`) to locate where legibility breaks, and discuss the
  static-vs-motion caveat with the mentor.
- CER is whitespace-insensitive and clamped to 100% (fully wrong).
- `\implies` is auto-mapped to `\Rightarrow` for the math renderer.

## Tested in development
Rendering, pristine-video build, H.265/AV1 encode, and frame extraction all verified
in the sandbox. Only the Pix2Text OCR step requires the local model.
