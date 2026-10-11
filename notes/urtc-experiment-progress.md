# URTC Experiment Progress — Baseline Formula-CER (§V.B)

**Updated:** 2026-07-01

---

## 2026-07-01 — Oracle decomposition COMPLETE (headline result)

100-formula Manim oracle (`experiments/oracle/`), Pix2Text extraction + KaTeX rendering:

| level | n | ext CER (normalized) | ext CER (raw string) | exact | rendering CER |
|---|---|---|---|---|---|
| pre-algebra | 34 | 1.2% | 14.0% | 31/34 | 0.0% |
| algebra-1 | 33 | 0.0% | 20.9% | 33/33 | 0.0% |
| algebra-2 | 33 | 0.0% | 37.6% | 33/33 | 0.0% |
| **ALL** | **100** | **0.4%** | **24.1%** | **97/100** | **0.0%** |

Three findings:
1. **Rendering CER = 0** on all 100 (KaTeX renders every ground-truth formula
   deterministically). The receiver contributes zero symbolic error.
2. **Naive string CER overstates extraction error ~60x** (24.1% -> 0.4%).
   Pix2Text emits render-equivalent LaTeX dialect (`\left(`, `\cfrac`,
   `\operatorname{l o g}`, `^{2}` vs `^2`). `latex_norm.py` canonicalizes both
   sides; only real symbol differences remain. This is itself a paper point.
3. **The 3 real errors are ONE systematic failure mode**: `%` misread as
   `\%_{0}` / `9_{0}` (25\%, 18\%, 75\% formulas). Systematic -> detectable ->
   exactly what ASR cross-verification should catch ("seventy-five percent").

Rerun anytime without OCR: `python experiments/oracle/oracle_cer.py --rescore`
(reuses saved predictions; prints both raw and normalized CER).

## 2026-07-03 — L4 CODE oracle (entry-level Python + C++): extraction + syntax verification

`experiments/oracle_code/` — 60 ground-truth ENTRY-LEVEL snippets (15 each:
py-basic, py-flow, cpp-basic, cpp-flow — variables, print/cout, if, loops,
simple functions; no classes) rendered as an editor-style video, OCR'd back
with Tesseract, indentation reconstructed from word x-coordinates (TSV mode —
generic OCR drops leading whitespace, fatal for Python):

| level | n | CER (content) | same-program exact |
|---|---|---|---|
| py-basic | 15 | 0.0% | 15/15 |
| py-flow | 15 | 1.1% | 12/15 |
| cpp-basic | 15 | 0.2% | 14/15 |
| cpp-flow | 15 | 1.5% | 12/15 |
| **ALL** | **60** | **0.7%** | **53/60** |

Correctness = "same program": AST equality for Python (`x=5` ≡ `x = 5` — the
code analog of the math LaTeX normalizer), token-normalized equality for C++.
Verification = syntax check (`ast.parse` / `g++ -fsyntax-only`), the code
analog of KaTeX renderability:
- 7 wrong extractions; **syntax check catches 5 (71%)**;
- **2 SILENT errors** (compile fine, wrong program):
  - Python: `i = i + 1` → `i=i+til` (`til` is a valid identifier);
  - C++: `int x = 3 + 4 * 2` → `3+4+4*2` — compiles and computes 19 instead
    of 11. A numerically wrong lesson that no syntax checker can catch —
    exactly the case needing ASR / human override, mirroring the math
    `%`-misread finding.

Rerun: `python experiments/oracle_code/code_oracle.py --make` then `--score`
(needs tesseract + ffmpeg + pillow + g++; `--range=a-b` scores a slice).
Results in `code_oracle_results.json`.

## 2026-07-01 — ASR verification of OCR on the oracle: PERFECT DETECTION (Table 1 result)

`experiments/verify/oracle_asr_check.py` — simulate the lecturer's speech from
ground-truth LaTeX, score ASR-OCR agreement against the saved Pix2Text
predictions, check whether low agreement flags the 3 truly-wrong extractions:

| speech condition | correct extractions (n=97) | OCR errors (n=3) | precision | recall |
|---|---|---|---|---|
| verbatim | all score 1.000 | max 0.800 | 1.00 | 1.00 |
| paraphrased (+synonyms, +filler) | all score 1.000 | max 0.700 | 1.00 | 1.00 |

- Clean separation margin: +0.20 (verbatim), +0.30 (paraphrased). Any
  threshold in 0.8–1.0 gives perfect detection on this set.
- All 3 `%`-misread errors are caught; zero false alarms on 97 correct ones.
- CAVEAT for the paper: speech is SIMULATED (perfect ASR of a lecturer stating
  each formula). It shows the agreement algorithm works; it does not yet show
  Whisper-in-the-loop performance. Claim as: "under an oracle-ASR assumption,
  cross-verification detects all extraction errors with no false positives."
- Rerun: `python experiments/verify/oracle_asr_check.py`

## 2026-07-01 — ASR-guided REPAIR: 100/100 exact after correction

`experiments/verify/repair.py` — propose-and-verify repair of flagged formulas:
align spoken(OCR LaTeX) vs ASR tokens -> locate disagreement span -> find the
minimal LaTeX substring speaking that span -> splice in the inverse-lexicon
LaTeX of the ASR tokens -> ACCEPT ONLY IF agreement rises to ~1.0, else keep
the human-override flag. Safe by construction (a repair can never replace a
good extraction; unfixable stays flagged).

Oracle result (simulated speech): all 3 flagged `%`-misreads corrected to
EXACT ground truth; 97 verified untouched; 0 still flagged.
**Symbolic CER: 0.40% -> 0.00% after repair (100/100 exact).**
Self-test covers: % fix, wrong-digit fix, token-inside-fraction fix, and a
structural disagreement (sqrt vs frac) that correctly stays FLAGGED.
Caveat: same oracle-ASR assumption as the detection test.
Run: `python experiments/verify/repair.py` (self-test) or
`python experiments/verify/repair.py experiments/oracle/oracle_cer_results.json`

## 2026-07-01 — ASR-OCR cross-verification prototype (`experiments/verify/spoken_math.py`)

- Rule-based spoken-math normalizer + agreement scorer; self-test: ALL PASS
  (powers, fractions, equals, plus/minus, roots, percent, number words).
- On clean spoken math it verifies correct LaTeX (score 1.0) and scores a
  deliberate OCR error lower (0.83) — detects errors *comparatively*, but a
  single-char error can still clear an absolute threshold. Report as ranking
  signal / flag, not absolute guarantee.
- **Real-lecture pilot (algebra.litelec, Khan)**: coverage 3/3 formulas have
  spoken math nearby, but scores 0.33–0.43 -> all FLAGGED at threshold 0.6.
  Khan narrates *around* formulas ("18 per hundred", "18 hundredths") rather
  than stating them verbatim. Honest finding: verbatim agreement verifies
  oracle-style speech; real lectures need paraphrase-tolerant matching (future
  work / limitation for the paper).

## 2026-07-01 — Per-formula diagnostics added to baseline_cer.py

- New pristine-PNG "OCR ceiling" pass + per-formula ref/pred/CER at every
  codec/bitrate -> `per_formula.csv`; per-formula verdicts (OCR-limited vs
  compression-driven). Rerun the algebra experiment to diagnose the flat 33.3%.
  NOTE: consider scoring it with `latex_norm.norm_cer` too — the 33.3% likely
  contains the same dialect inflation found in the oracle.

## URTC 2026 logistics (checked 2026-07-01)

- IEEE Boston lists **URTC 2026: Oct 9–11, 2026, MIT** — cycle confirmed real.
- urtc.mit.edu still shows the 2025 cycle; 2026 submission details/CMT link
  "posted soon". 2025 paper deadline was Aug 3 -> plan for ~early Aug 2026.
  Check the site again mid-July.

---
**Goal:** the paper's core evidence — does ordinary video compression damage a
lecture's formulas, vs `.litelec` (exact by construction)?

---

## What's built
- `experiments/baseline_cer.py` — runs on Chen's machine. Two designs tried (below).
- `experiments/README.md` — usage + honesty notes.
- `experiments/SAMPLE_cer_vs_bitrate.png` — illustrative (mock) figure.
- Per-lecture output goes to `experiments/out_<name>/` (results.json, results.csv,
  cer_vs_bitrate.png).
- Metric: CER (character error rate), whitespace-insensitive, clamped to 100%.
- Dependencies confirmed installed in venv: matplotlib, pix2text (+torch, etc.),
  ffmpeg has libx265 + libaom-av1.

## Design v1 (DISCARDED) — OCR whole real frames
- Downloaded the real Khan video, compressed at 50/100/200k, OCR'd the FULL frame,
  compared to one short formula.
- Result: CER 1197–2012% (nonsense >100%). Cause: OCR read the entire whiteboard
  (all writing + captions), not the target formula. Confounded; not a real metric.

## Design v2 (CURRENT) — controlled rendered slides
- Render each formula as a clean centered slide -> short pristine video -> compress
  at low bitrates -> OCR each degraded slide -> CER. `.litelec` = 0 by construction.
- No network needed; fully reproducible.

### First real result (algebra.litelec, 3 formulas), 2026-06-27
| condition | size | avg CER |
|---|---|---|
| LiteLecture (.litelec) | 10.5 KB | 0% (by construction) |
| libx265 @ 25k | 42 KB | 33.3% |
| libx265 @ 50k | 54 KB | 33.3% |
| libx265 @ 100k | 65 KB | 33.3% |
| libx265 @ 200k | 70 KB | 33.3% |
| libaom-av1 @ 25k | 15 KB | 33.3% |
| libaom-av1 @ 50k | 18 KB | 33.3% |
| libaom-av1 @ 100k | 23 KB | 33.3% |
| libaom-av1 @ 200k | 25 KB | 33.3% |
(Pristine source: 29 KB, 12 s.)

### Interpretation (IMPORTANT)
- **Flat 33.3% at every bitrate** => two findings:
  1. Static formula slides compress so well that even 25 kbps doesn't degrade them
     (the predicted "static compresses too well" caveat — confirmed). So compression
     is NOT the variable being stressed here.
  2. 33.3% is a CONSTANT OCR error: with 3 formulas, almost certainly ONE formula is
     misread even on a pristine image; the other two read perfectly. Bitrate-independent.
- Honest current takeaway: recovering a formula from PIXELS via OCR is imperfect even
  at best quality, while `.litelec` is exact (0%) because it stores symbols, not pixels.
  Real + defensible, but NOT the intended "low bitrate garbles formulas" curve.

## Open decision (bring to supervisor) — how to get the real degradation curve
- **A — Real video cropped to the formula region.** Real lectures have motion/handwriting
  that DOES eat the bitrate budget and blur formulas at low bitrate. Crop each frame to
  the formula's bbox so OCR reads only the formula. Needs a bbox per formula. Most likely
  to produce the intended curve.
- **B — Reframe** around the v2 finding (pixels->OCR is lossy & never 0; symbols exact).
- **C — Stress the codec harder** (tiny resolution / extreme low bitrate / add motion). More artificial.

## Next concrete step (pending)
- Add PER-FORMULA diagnostics to the harness (dump reference vs OCR prediction for each
  formula, incl. an uncompressed "pristine OCR ceiling" pass) so we can SEE which formula
  the OCR misreads and what it returns. Then one quick re-run -> precise diagnosis.
- Then pick A/B/C with the supervisor.

## Status vs URTC plan
- §V.A compression ratios: DONE (real, in size-breakdown.md): ~614x / ~400x.
- §V.B formula-CER curve: experiment harness DONE; needs design choice (A/B/C) to yield
  the headline figure. This is the W1–W2 "命门" item.
