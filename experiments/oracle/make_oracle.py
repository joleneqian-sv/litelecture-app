"""
Manim oracle generator (URTC error-budget decomposition).

Renders a set of KNOWN formulas into a real math video and writes their exact
LaTeX + on-screen timing to oracle_truth.json. Because we start from the LaTeX,
the ground truth is exact and automatic -- no hand-labeling, no guessing. This is
what lets us cleanly separate EXTRACTION error (OCR reading the video) from
RENDERING error (receiver typesetting known LaTeX).

Requires: manim (Community edition) + a LaTeX install (TinyTeX/MiKTeX/TeX Live) + ffmpeg.

Run (from the repo root, venv active):
    pip install manim
    manim -qm --format mp4 experiments/oracle/make_oracle.py Oracle
Manim writes the MP4 under media/videos/make_oracle/720p30/Oracle.mp4, and this
script writes oracle_truth.json next to itself. Point the CER harness at both.
"""

import json
import os
from manim import Scene, MathTex, Write, FadeOut, config

# Formulas span easy -> hard, so extraction CER can be reported by complexity.
FORMULAS = [
    r"x = 4",
    r"3x + 5 = 17",
    r"a^2 + b^2 = c^2",
    r"\frac{9}{50}",
    r"f(x) = \frac{x^2 - 1}{x - 1}",
    r"\sqrt{x^2 + 1}",
    r"18\% = \frac{18}{100} = 0.18",
    r"\lim_{x \to 1} \frac{x^2 - 1}{x - 1} = 2",
    r"\int_0^1 x^2 \, dx = \frac{1}{3}",
    r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}",
]

WRITE_T = 1.0     # seconds to animate the formula in
HOLD_T = 3.0      # seconds fully on screen
FADE_T = 0.5      # seconds to fade out


class Oracle(Scene):
    def construct(self):
        truth = []
        t = 0.0
        for latex in FORMULAS:
            m = MathTex(latex).scale(1.6)
            self.play(Write(m), run_time=WRITE_T)
            # fully on screen during [t+WRITE_T, t+WRITE_T+HOLD_T]; sample the middle
            truth.append({"t": round(t + WRITE_T + HOLD_T / 2, 2), "latex": latex})
            self.wait(HOLD_T)
            self.play(FadeOut(m), run_time=FADE_T)
            t += WRITE_T + HOLD_T + FADE_T

        out = os.path.join(os.path.dirname(__file__), "oracle_truth.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"fps": config.frame_rate, "formulas": truth}, f, indent=2)
        print(f"[oracle] wrote {out} with {len(truth)} ground-truth formulas")
