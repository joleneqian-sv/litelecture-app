#!/usr/bin/env python3
"""
ASR-guided repair of flagged OCR extractions (propose-and-verify).

After cross-verification FLAGS a formula (spoken math disagrees with the OCR
LaTeX), this module tries to FIX it:

  1. ALIGN   the spoken-token form of the OCR LaTeX against the ASR tokens
             (Levenshtein alignment with backtrace).
  2. LOCATE  each disagreement span, and find the minimal substring of the
             (normalized) OCR LaTeX that "speaks" exactly those tokens
             (brute-force over substrings — formulas are short).
  3. INVERT  the ASR tokens in that span back to LaTeX through a deterministic
             inverse lexicon (percent -> \\%, plus -> +, squared -> ^2, ...).
             Structural tokens we cannot invert (over, square root of) abort.
  4. SPLICE  the replacement in, producing a candidate LaTeX.
  5. VERIFY  accept the candidate ONLY IF its agreement with the speech is
             >= accept threshold (default 0.999) AND strictly better than the
             original. Otherwise return the original, still FLAGGED.

Because step 5 uses the same signal that caught the error, repair is safe by
construction: a bad proposal can never replace a good extraction, and an
unfixable formula stays flagged for human override.

Usage:
  python experiments/verify/repair.py            # self-test
  python experiments/verify/repair.py results.json   # repair oracle errors
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "oracle"))

from latex_norm import normalize, norm_cer
from spoken_math import latex_to_speech, normalize_spoken, agreement

# deterministic inverse of the spoken-token lexicon (flat tokens only)
_INV = {"plus": "+", "minus": "-", "times": "\\times", "equals": "=",
        "percent": "\\%", "plus_or_minus": "\\pm", "pi": "\\pi",
        "squared": "^2", "cubed": "^3", ".": "."}
_TOK = re.compile(r"^([a-zA-Z]|\d+(\.\d+)?)$")  # variables and numbers


def speech_tokens(latex):
    return normalize_spoken(latex_to_speech(latex)).split()


def invert_tokens(toks):
    """ASR tokens -> LaTeX, or None if any token is structural/unknown."""
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t == "sub" and i + 1 < len(toks) and _TOK.match(toks[i + 1]):
            out.append("_" + toks[i + 1]); i += 2
        elif t in _INV:
            out.append(_INV[t]); i += 1
        elif _TOK.match(t):
            out.append(t); i += 1
        else:
            return None  # over / square root of / unknown -> can't invert flat
    return "".join(out)


def _align(a, b):
    """Levenshtein alignment; returns list of (op, i, j) with op in M/S/D/I."""
    m, n = len(a), len(b)
    d = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): d[i][0] = i
    for j in range(n + 1): d[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    ops, i, j = [], m, n
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("M" if a[i - 1] == b[j - 1] else "S", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("D", i - 1, j)); i -= 1
        else:
            ops.append(("I", i, j - 1)); j -= 1
    return ops[::-1]


def diff_spans(a, b):
    """Contiguous disagreement regions: [(a_lo, a_hi, b_lo, b_hi), ...]."""
    spans, cur = [], None
    for op, i, j in _align(a, b):
        if op == "M":
            if cur: spans.append(cur); cur = None
            continue
        ai = (i, i + 1) if op in ("S", "D") else (i, i)
        bj = (j, j + 1) if op in ("S", "I") else (j, j)
        if cur is None:
            cur = [ai[0], ai[1], bj[0], bj[1]]
        else:
            cur[1], cur[3] = max(cur[1], ai[1]), max(cur[3], bj[1])
    if cur: spans.append(cur)
    return spans


def find_substring(latex, want_tokens):
    """Minimal contiguous substring of `latex` whose speech == want_tokens."""
    best = None
    n = len(latex)
    for lo in range(n):
        for hi in range(lo + 1, n + 1):
            sub = latex[lo:hi]
            if speech_tokens(sub) == want_tokens:
                if best is None or (hi - lo) < (best[1] - best[0]):
                    best = (lo, hi)
                break  # longer strings from this lo only add tokens
    return best


def repair(ocr_latex, spoken_text, accept=0.999):
    """-> dict(latex, status in {VERIFIED, CORRECTED, FLAGGED}, score, ...)."""
    lat = normalize(ocr_latex)
    base = agreement(lat, spoken_text)
    if base >= accept:
        return {"latex": lat, "status": "VERIFIED", "score": base}
    ocr_toks = speech_tokens(lat)
    hyp = normalize_spoken(spoken_text).split()
    # best-matching ASR window = the one agreement() scored (recompute simply):
    # slide ref-sized windows, keep the closest
    n = len(ocr_toks)
    best_w, best_key = hyp, None
    for L in (max(1, n - 1), n, n + 1, n + 2):
        for i in range(max(1, len(hyp) - L + 1)):
            w = hyp[i:i + L]
            # tie-break toward windows the size of the reference, so a
            # substitution is preferred over a deletion of equal distance
            key = (_lev_toks(ocr_toks, w), abs(L - n))
            if best_key is None or key < best_key:
                best_w, best_key = w, key
    cand = lat
    for a_lo, a_hi, b_lo, b_hi in reversed(diff_spans(ocr_toks, best_w)):
        rep = invert_tokens(best_w[b_lo:b_hi])
        if rep is None:
            continue
        if a_lo == a_hi:               # pure insertion of spoken content
            continue                    # v1: skip; no anchor substring
        pos = find_substring(cand, ocr_toks[a_lo:a_hi])
        if pos is None:
            continue
        cand = cand[:pos[0]] + rep + cand[pos[1]:]
    cand = normalize(cand)
    new = agreement(cand, spoken_text)
    if new >= accept and new > base:
        return {"latex": cand, "status": "CORRECTED", "score": new,
                "was": lat, "old_score": base}
    return {"latex": lat, "status": "FLAGGED", "score": base}


def _lev_toks(a, b):
    if a == b: return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------- oracle run
def run_oracle(res_path):
    rows = [r for r in json.load(open(res_path, encoding="utf-8"))["rows"]
            if r.get("ocr_pred") is not None]
    print(f"{len(rows)} formulas; speech simulated from ground truth "
          f"(replace with Whisper transcript for the real run)\n")
    n_ver = n_cor = n_flag = 0
    cer_before, cer_after = [], []
    for r in rows:
        spoken = latex_to_speech(normalize(r["latex"]))
        out = repair(r["ocr_pred"], spoken)
        cer_before.append(norm_cer(r["latex"], r["ocr_pred"]))
        cer_after.append(norm_cer(r["latex"], out["latex"]))
        if out["status"] == "VERIFIED": n_ver += 1
        elif out["status"] == "CORRECTED":
            n_cor += 1
            ok = "-> MATCHES TRUTH" if cer_after[-1] == 0 else "-> still wrong!"
            print(f"[CORRECTED] id={r['id']:>3} {out['old_score']:.2f} -> {out['score']:.2f} {ok}")
            print(f"   ocr : {out['was']!r}")
            print(f"   fix : {out['latex']!r}")
            print(f"   true: {normalize(r['latex'])!r}")
        else:
            n_flag += 1
            print(f"[FLAGGED  ] id={r['id']:>3} score {out['score']:.2f} "
                  f"(unfixable -> human override) ref={r['latex']!r}")
    n = len(rows)
    print(f"\nverified {n_ver}/{n}   corrected {n_cor}/{n}   "
          f"still flagged {n_flag}/{n}")
    print(f"symbolic CER: {sum(cer_before)/n*100:.2f}% before repair -> "
          f"{sum(cer_after)/n*100:.2f}% after repair "
          f"({sum(1 for c in cer_after if c == 0)}/{n} exact)")


# ---------------------------------------------------------------- self-test
def self_test():
    cases = [
        # (ocr_latex, spoken truth, expected status, expected latex)
        (r"7 5 9_{0}", "seventy five percent", "CORRECTED", r"75\%"),
        (r"2 5 \%_{0}=\frac{1} {4}", "twenty five percent equals one over four",
         "CORRECTED", normalize(r"25\%=\frac{1}{4}")),
        (r"x^{2}+3=1 2", "x squared plus three equals twelve",
         "VERIFIED", normalize(r"x^2+3=12")),
        # ASR disagrees on a token INSIDE structure -> splice fixes it
        (r"\frac{1}{3}", "one over two", "CORRECTED", normalize(r"\frac{1}{2}")),
        # replacement itself is structural (sqrt vs frac) -> cannot invert, FLAG
        (r"\frac{x}{2}", "square root of x", "FLAGGED", None),
        # OCR wrong digit, ASR states it -> fix
        (r"7+5=1 3", "seven plus five equals twelve", "CORRECTED", "7+5=12"),
    ]
    ok = True
    for ocr, spoken, want, want_latex in cases:
        out = repair(ocr, spoken)
        good = out["status"] == want and (want_latex is None or out["latex"] == want_latex)
        ok &= good
        print(f"[{'pass' if good else 'FAIL'}] {ocr!r} + {spoken!r}")
        print(f"       -> {out['status']} {out['latex']!r} (want {want} {want_latex!r})")
    print("\nself-test:", "ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_oracle(sys.argv[1])
    else:
        raise SystemExit(self_test())
