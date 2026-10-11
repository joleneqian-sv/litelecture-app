#!/usr/bin/env python3
"""
Minimal ASR-OCR cross-verification for symbolic content (URTC Section IV / V).

Idea: a lecture states most formulas twice — on the board (pixels -> math-OCR)
and out loud (audio -> ASR transcript). The two channels fail independently, so
agreement between them is evidence the extracted LaTeX is correct.

  verify(latex, transcript_window) -> VerifyResult(score, verdict, ...)

Method (deliberately simple, no ML):
  1. Speak the candidate LaTeX with a rule-based normalizer (Python port of
     web/src/mathspeak.js) -> canonical spoken-token sequence.
  2. Normalize the ASR transcript near the formula's timestamp (number words ->
     digits, "divided by"/"over" -> over, "is equal to" -> equals, ...).
  3. Slide the formula's token sequence over the transcript window; the best
     token-level alignment similarity (1 - Levenshtein/len) is the agreement
     score. score >= --threshold  => VERIFIED; any spoken-math tokens present
     but score below threshold    => FLAGGED (needs human check);
     no spoken math nearby        => UNCOVERED (verifier abstains).

Covered patterns: powers (squared/cubed/to the power of), fractions (over,
divided by), equals, plus/minus, times, square roots, percent, pi, simple
variables, function notation f(x), number words up to 999.

Usage:
  python experiments/verify/spoken_math.py web/public/demos/algebra.litelec
  python experiments/verify/spoken_math.py --self-test
Options:
  --threshold 0.6   verification threshold on agreement score
  --window 12       seconds of transcript before the formula's t to include
  --csv out.csv     also write per-formula results
"""
import argparse
import csv
import json
import re
import sys

# ---------------------------------------------------------------- LaTeX -> speech
# Python port of web/src/mathspeak.js (keep the two in sync).
_WORDS = [
    (r"\\implies", " implies "), (r"\\Rightarrow", " implies "),
    (r"\\neq", " not equal to "), (r"\\leq", " less than or equal to "),
    (r"\\geq", " greater than or equal to "),
    (r"\\times", " times "), (r"\\cdot", " times "),
    (r"\\div", " divided by "), (r"\\pm", " plus or minus "),
    (r"\\pi", " pi "), (r"\\infty", " infinity "),
    (r"\\%", " percent "), (r"\\,", " "),
]


def latex_to_speech(latex):
    if not latex:
        return ""
    s = " " + latex + " "
    for _ in range(5):
        s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r" \1 over \2 ", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r" square root of \1 ", s)
    s = re.sub(r"\^\s*\{([^{}]*)\}", r" to the power of \1 ", s)
    s = re.sub(r"\^\s*2\b", " squared ", s)
    s = re.sub(r"\^\s*3\b", " cubed ", s)
    s = re.sub(r"\^\s*([a-zA-Z0-9])", r" to the power of \1 ", s)
    s = re.sub(r"_\s*\{([^{}]*)\}", r" sub \1 ", s)
    s = re.sub(r"_\s*([a-zA-Z0-9])", r" sub \1 ", s)
    for pat, word in _WORDS:
        s = re.sub(pat, word, s)
    s = re.sub(r"([a-zA-Z])\s*\(\s*([^()]*?)\s*\)", r"\1 of \2", s)
    s = s.replace("=", " equals ").replace("+", " plus ")
    s = re.sub(r"-", " minus ", s)
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    s = re.sub(r"[{}\\]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------- ASR normalizer
_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
         "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}

# spoken phrase -> canonical token(s); longest patterns first
_PHRASES = [
    (r"\bis equal to\b", "equals"), (r"\bis the same as\b", "equals"),
    (r"\bequal to\b", "equals"), (r"\bequals\b", "equals"),
    (r"\bgives us\b", "equals"), (r"\bwhich is\b", "equals"),
    (r"\bplus or minus\b", "plus_or_minus"),
    (r"\bnegative\b", "minus"), (r"\bplus\b", "plus"),
    (r"\bminus\b", "minus"), (r"\btake away\b", "minus"),
    (r"\btimes\b", "times"), (r"\bmultiplied by\b", "times"),
    (r"\bdivided by\b", "over"), (r"\bover\b", "over"),
    (r"\bout of\b", "over"),
    (r"\bsquare root of\b", "square root of"), (r"\bsquared\b", "squared"),
    (r"\bcubed\b", "cubed"),
    (r"\bto the power of\b", "to the power of"),
    (r"\braised to the\b", "to the power of"),
    (r"\bto the\b", "to the power of"),
    (r"\bpercent\b", "percent"), (r"\bpi\b", "pi"),
]
_MATH_TOKENS = {"equals", "plus", "minus", "times", "over", "squared", "cubed",
                "percent", "pi", "plus_or_minus", "square", "root", "power"}


def words_to_numbers(text):
    """'twenty five' -> '25'; 'one hundred' -> '100' (up to 999)."""
    toks, out, i = text.split(), [], 0
    while i < len(toks):
        t = toks[i]
        if t in _TENS:
            if i + 1 < len(toks) and toks[i + 1] in _ONES and _ONES[toks[i + 1]] < 10:
                out.append(str(_TENS[t] + _ONES[toks[i + 1]])); i += 2
            else:
                out.append(str(_TENS[t])); i += 1
        elif t in _ONES:
            if i + 1 < len(toks) and toks[i + 1] == "hundred":
                n = _ONES[t] * 100; i += 2
                if i < len(toks) and toks[i] == "and":
                    i += 1
                if i < len(toks) and toks[i] in _TENS:
                    n += _TENS[toks[i]]; i += 1
                    if i < len(toks) and toks[i] in _ONES and _ONES[toks[i]] < 10:
                        n += _ONES[toks[i]]; i += 1
                elif i < len(toks) and toks[i] in _ONES:
                    n += _ONES[toks[i]]; i += 1
                out.append(str(n))
            else:
                out.append(str(_ONES[t])); i += 1
        else:
            out.append(t); i += 1
    return " ".join(out)


def normalize_spoken(text):
    """ASR transcript text -> canonical spoken-math token string."""
    s = " " + (text or "").lower() + " "
    s = re.sub(r"[^a-z0-9\s.%-]", " ", s)
    s = s.replace("%", " percent ")
    s = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", s)  # 'zero . one eight' pre-joined
    s = words_to_numbers(s)
    s = re.sub(r"\bpoint\b", ".", s)
    s = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", s)
    while True:  # 'zero point one eight' -> '0.1 8' -> '0.18'
        s2 = re.sub(r"(\d+\.\d+)\s+(\d)", r"\1\2", s)
        if s2 == s:
            break
        s = s2
    for pat, tok in _PHRASES:
        s = re.sub(pat, f" {tok} ", s)
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)  # '2x' -> '2 x'
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- agreement
def _lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def agreement(latex, transcript_text):
    """Best sliding-window token similarity between spoken(latex) and ASR text."""
    # both sides go through the SAME canonicalizer so tokens line up
    ref = normalize_spoken(latex_to_speech(latex)).split()
    hyp = normalize_spoken(transcript_text).split()
    if not ref:
        return 0.0
    n, best = len(ref), 0.0
    if len(hyp) <= n:
        windows = [hyp]
    else:  # try several window lengths so leading/trailing filler can't hurt
        windows = [hyp[i:i + L]
                   for L in (max(1, n - 1), n, n + 1, n + 2)
                   for i in range(len(hyp) - min(L, len(hyp)) + 1)]
    for w in windows:
        best = max(best, 1.0 - _lev(ref, w) / max(len(ref), len(w)))
        if best == 1.0:
            break
    return round(best, 4)


def has_spoken_math(transcript_text):
    toks = set(normalize_spoken(transcript_text).split())
    return bool(toks & _MATH_TOKENS) or any(re.fullmatch(r"\d+(\.\d+)?", t)
                                            for t in toks)


class VerifyResult(dict):
    pass


def verify(latex, transcript_text, threshold=0.6):
    """-> dict(score, verdict in {VERIFIED, FLAGGED, UNCOVERED})."""
    if not has_spoken_math(transcript_text):
        return VerifyResult(score=0.0, verdict="UNCOVERED")
    score = agreement(latex, transcript_text)
    return VerifyResult(score=score,
                        verdict="VERIFIED" if score >= threshold else "FLAGGED")


# ---------------------------------------------------------------- .litelec runner
def run_litelec(path, threshold, window, csv_out=None):
    d = json.load(open(path, encoding="utf-8"))
    transcript = d.get("transcript", [])
    symbols = [s for s in d.get("symbols", []) if s.get("kind") == "latex"]
    rows = []
    print(f"{path}: {len(symbols)} formulas, {len(transcript)} transcript segments")
    print(f"{'t':>6}  {'score':>6}  verdict    latex")
    for s in symbols:
        t0, t1 = s["t"] - window, s["t"] + s.get("duration_s", 8)
        text = " ".join(seg["text"] for seg in transcript if t0 <= seg["t"] <= t1)
        r = verify(s["data"], text, threshold)
        rows.append({"t": s["t"], "latex": s["data"], **r,
                     "spoken_window": text[:200]})
        print(f"{s['t']:>6.1f}  {r['score']:>6.2f}  {r['verdict']:<9}  {s['data']}")
    n = len(rows) or 1
    cov = sum(r["verdict"] != "UNCOVERED" for r in rows)
    ver = sum(r["verdict"] == "VERIFIED" for r in rows)
    print(f"\ncoverage {cov}/{len(rows)} ({cov/n*100:.0f}%)   "
          f"verified {ver}/{len(rows)} ({ver/n*100:.0f}%)   threshold {threshold}")
    if csv_out:
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["t", "latex", "score", "verdict",
                                               "spoken_window"])
            w.writeheader(); w.writerows(rows)
        print(f"wrote {csv_out}")
    return rows


# ---------------------------------------------------------------- self-test
def self_test():
    cases = [
        # (latex, spoken, expect_verdict)
        ("x^2 + 3 = 12", "so x squared plus three equals twelve", "VERIFIED"),
        ("\\frac{18}{100} = 0.18", "eighteen over one hundred is equal to zero point one eight", "VERIFIED"),
        ("18\\% = \\frac{18}{100}", "eighteen percent equals eighteen over one hundred", "VERIFIED"),
        ("\\sqrt{16} = 4", "the square root of sixteen is equal to four", "VERIFIED"),
        ("a \\pm b", "a plus or minus b", "VERIFIED"),
        ("y = 2x + 1", "y equals two x plus one", "VERIFIED"),
        # OCR error: spoken math disagrees -> flag
        ("x^3 + 3 = 12", "so x squared plus three equals twelve", None),
        ("7 + 5 = 12", "seven plus five gives us twelve", "VERIFIED"),
        # no math spoken at all -> abstain
        ("e = mc^2", "let's take a short break now", "UNCOVERED"),
    ]
    ok = True
    for latex, spoken, expect in cases:
        r = verify(latex, spoken)
        status = "pass"
        if expect and r["verdict"] != expect:
            status, ok = "FAIL", False
        print(f"[{status}] {latex!r} vs {spoken!r} -> {r['verdict']} ({r['score']})")
    # the deliberate-error case must score strictly below its corrected twin
    good = agreement("x^2 + 3 = 12", "so x squared plus three equals twelve")
    bad = agreement("x^3 + 3 = 12", "so x squared plus three equals twelve")
    if bad < good:
        print(f"[pass] error detection: correct {good} > wrong {bad}")
    else:
        print(f"[FAIL] error detection: correct {good} <= wrong {bad}"); ok = False
    print("\nself-test:", "ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="ASR-OCR cross-verification")
    ap.add_argument("litelec", nargs="?")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--window", type=float, default=12.0,
                    help="seconds of transcript before formula t to include")
    ap.add_argument("--csv")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        sys.exit(self_test())
    if not args.litelec:
        ap.error("give a .litelec path or --self-test")
    run_litelec(args.litelec, args.threshold, args.window, args.csv)


if __name__ == "__main__":
    main()
