#!/usr/bin/env python3
"""
ASR-OCR cross-verification test on the 100-formula oracle (URTC Table 1).

Question: given the lecturer SAYS each formula and the encoder OCRs it from
pixels, does ASR-OCR agreement detect the formulas the OCR got wrong?

Setup: the oracle gives labels — norm CER > 0 marks the truly-wrong
extractions. We simulate the lecturer's speech from ground-truth LaTeX
(latex_to_speech), then score agreement(ocr_pred, speech). A real run replaces
the simulated speech with a Whisper transcript; everything downstream is
identical.

Two speech conditions:
  verbatim    - lecturer reads the formula exactly ("three over four equals
                seventy-five percent")
  paraphrased - synonym swaps + filler, as lecturers actually talk ("so three
                divided by four is equal to seventy-five percent, right")

Detection rule: flag when agreement < threshold. With correct OCR the speech
matches the spoken form of the prediction, so scores concentrate at 1.0;
genuine OCR errors break the match.

Usage:
  python experiments/verify/oracle_asr_check.py [results.json] [--threshold 0.9]
Defaults to experiments/oracle/oracle_cer_results.json.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "oracle"))

from latex_norm import norm_cer, normalize
from spoken_math import latex_to_speech, agreement

# lecturer-style paraphrase: synonym swaps the normalizer must undo, plus filler
_PARA = [
    (r"\bequals\b", "is equal to"),
    (r"\btimes\b", "multiplied by"),
    (r"\bover\b", "divided by"),
    (r"\bsquared\b", "squared"),  # kept; anchors the pattern list
]


def paraphrase(speech, i):
    s = speech
    # alternate which synonyms fire so the set is varied, not uniform
    for k, (pat, rep) in enumerate(_PARA):
        if (i + k) % 2 == 0:
            s = re.sub(pat, rep, s)
    return f"so we have {s} , right"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    res_path = args[0] if args else os.path.join(HERE, "..", "oracle",
                                                 "oracle_cer_results.json")
    thr = 0.9
    for a in sys.argv[1:]:
        if a.startswith("--threshold"):
            thr = float(a.split("=", 1)[1]) if "=" in a else thr
    rows = [r for r in json.load(open(res_path, encoding="utf-8"))["rows"]
            if r.get("ocr_pred") is not None]
    print(f"{len(rows)} formulas with OCR predictions; "
          f"flag when agreement < {thr}\n")

    for cond in ("verbatim", "paraphrased"):
        stats = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        err_scores, ok_scores = [], []
        details = []
        for i, r in enumerate(rows):
            # speak the NORMALIZED truth so both sides share one LaTeX dialect;
            # a real ASR transcript replaces this line without other changes
            truth_speech = latex_to_speech(normalize(r["latex"]))
            spoken = truth_speech if cond == "verbatim" else paraphrase(truth_speech, i)
            score = agreement(normalize(r["ocr_pred"]), spoken)
            is_err = norm_cer(r["latex"], r["ocr_pred"]) > 0
            flagged = score < thr
            (err_scores if is_err else ok_scores).append(score)
            key = ("tp" if flagged else "fn") if is_err else ("fp" if flagged else "tn")
            stats[key] += 1
            if is_err or flagged:
                details.append((r["id"], score, is_err, flagged, r["latex"],
                                r["ocr_pred"]))
        n_err, n_ok = len(err_scores), len(ok_scores)
        prec = stats["tp"] / (stats["tp"] + stats["fp"]) if stats["tp"] + stats["fp"] else float("nan")
        rec = stats["tp"] / (stats["tp"] + stats["fn"]) if n_err else float("nan")
        print(f"=== {cond.upper()} speech ===")
        print(f"  correct extractions (n={n_ok}): "
              f"min {min(ok_scores):.3f}  mean {sum(ok_scores)/n_ok:.3f}")
        print(f"  OCR errors          (n={n_err}): "
              f"max {max(err_scores):.3f}  mean {sum(err_scores)/n_err:.3f}")
        print(f"  detection @ {thr}: precision {prec:.2f}  recall {rec:.2f}  "
              f"(TP {stats['tp']}  FP {stats['fp']}  FN {stats['fn']}  TN {stats['tn']})")
        margin = min(ok_scores) - max(err_scores)
        print(f"  separation margin (min correct - max error): {margin:+.3f}"
              + ("  <- clean separation" if margin > 0 else "  <- classes overlap"))
        for fid, score, is_err, flagged, ref, pred in details:
            tag = {(True, True): "TP hit ", (True, False): "FN MISS",
                   (False, True): "FP     "}[(is_err, flagged)]
            print(f"    [{tag}] id={fid:>3} score={score:.3f} ref={ref!r}")
            print(f"              ocr={pred!r}")
        print()


if __name__ == "__main__":
    main()
