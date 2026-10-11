#!/usr/bin/env python3
"""
Oracle error-budget harness (100-formula version).

Splits total symbolic error into two independent parts using the oracle video
whose exact LaTeX is KNOWN (oracle_truth.json):

  EXTRACTION CER = how wrong the ENCODER's math-OCR is reading formulas out of
                   rendered video pixels (pixels -> LaTeX). Uses the SAME
                   Pix2Text calls as src/encoder/encode.py.
  RENDERING  CER = how wrong the RECEIVER is typesetting KNOWN LaTeX
                   (LaTeX -> display via KaTeX). Zero by construction; verified.

Reports overall AND per level (pre-algebra / algebra-1 / algebra-2).
Run on a machine with Pix2Text (the encoder machine) for the extraction number;
the rendering number needs only node + katex (in web/).
"""
import json, os, re, subprocess, sys, tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from latex_norm import norm_cer  # LaTeX-dialect-fair CER (see latex_norm.py)

HERE  = os.path.dirname(os.path.abspath(__file__))
REPO  = os.path.abspath(os.path.join(HERE, "..", ".."))
TRUTH = os.path.join(HERE, "oracle_truth.json")
VIDEO = os.path.join(HERE, "oracle.mp4")
WEB   = os.path.join(REPO, "web")

def _norm(s): return re.sub(r"\s+", "", s or "")
def levenshtein(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j]+1, cur[-1]+1, prev[j-1]+(ca != cb)))
        prev = cur
    return prev[-1]
def cer(ref, pred):
    """Raw string CER (whitespace-insensitive), clamped to [0,1]. Counts
    render-equivalent LaTeX dialect (\\left(, \\cfrac, \\operatorname{l o g},
    ^{2} vs ^2, ...) as error, so it OVERSTATES true extraction error.
    Report norm_cer as the headline number and this as the naive baseline."""
    r, p = _norm(ref), _norm(pred)
    if not r: return 0.0 if not p else 1.0
    return min(1.0, levenshtein(r, p) / len(r))

def recognize_formula(p2t, path):
    for attr in ("recognize_formula", "recognize_math"):
        fn = getattr(p2t, attr, None)
        if fn:
            try:
                out = fn(path)
                if isinstance(out, dict): out = out.get("text") or out.get("latex") or ""
                return (out or "").strip()
            except Exception: pass
    fn = getattr(p2t, "recognize", None)
    if fn:
        try:
            out = fn(path)
            text = out if isinstance(out, str) else json.dumps(out)
            m = re.findall(r"\$+([^$]+)\$+", text)
            return m[0].strip() if m else ""
        except Exception: pass
    return ""
def load_p2t():
    try: from pix2text import Pix2Text
    except Exception: return None
    print("[ocr] loading Pix2Text ...")
    try: return Pix2Text.from_config()
    except Exception: return Pix2Text()
def frame_at(t, out_png):
    subprocess.run(["ffmpeg","-y","-ss",str(t),"-i",VIDEO,"-frames:v","1",out_png],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

KATEX_JS = r"""
const katex = require('katex');
try { katex.renderToString(process.env.LATEX, {throwOnError:true, displayMode:true});
      console.log('OK'); }
catch (e) { console.log('FAIL:' + e.message.replace(/\n/g,' ')); }
"""
def katex_renders(latex):
    try:
        env = dict(os.environ, LATEX=latex)   # pass via env: leading '-' is safe
        r = subprocess.run(["node","-e",KATEX_JS], cwd=WEB, env=env,
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip().startswith("OK"), r.stdout.strip()
    except Exception as e:
        return False, f"node-error:{e}"

def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    rescore = "--rescore" in sys.argv  # recompute from saved ocr_pred, no OCR run
    truth = json.load(open(TRUTH, encoding="utf-8"))["formulas"]
    saved = {}
    if rescore:
        prev = json.load(open(os.path.join(HERE, "oracle_cer_results.json"),
                              encoding="utf-8"))
        saved = {r["id"]: r for r in prev["rows"]}
        print("[rescore] reusing saved OCR predictions; no Pix2Text needed")
    p2t = None if rescore else load_p2t()
    tmp = tempfile.mkdtemp()
    rows = []
    fails = []
    for f in truth:
        ref = f["latex"]
        if rescore:
            pred = saved.get(f["id"], {}).get("ocr_pred")
        elif p2t is not None and os.path.exists(VIDEO):
            png = os.path.join(tmp, f"f{f['id']}.png"); frame_at(f["t"], png)
            pred = recognize_formula(p2t, png)
        else:
            pred = None
        if pred is not None:
            ext_raw, ext = cer(ref, pred), norm_cer(ref, pred)
        else:
            ext_raw, ext = None, None
        if rescore and f["id"] in saved:
            ok = saved[f["id"]]["renders"]  # KaTeX result doesn't change
        else:
            ok, detail = katex_renders(ref)
            if not ok: fails.append((f["id"], ref, detail))
        rows.append({**f, "ocr_pred": pred,
                     "extraction_cer": ext, "extraction_cer_raw": ext_raw,
                     "renders": ok, "rendering_cer": 0.0 if ok else 1.0})

    # ---------- overall ----------
    ext_all = [r["extraction_cer"] for r in rows if r["extraction_cer"] is not None]
    raw_all = [r["extraction_cer_raw"] for r in rows if r["extraction_cer_raw"] is not None]
    rnd_all = [r["rendering_cer"] for r in rows]
    print("\n=== ORACLE ERROR-BUDGET DECOMPOSITION (100 formulas) ===")
    print("ext_CER   = extraction error on NORMALIZED LaTeX (headline; dialect-fair)")
    print("raw_CER   = naive string CER (counts \\left( vs ( etc. as error)")
    print("exact     = formulas extracted symbol-perfectly (norm CER = 0)\n")
    print(f"{'level':<12} {'n':>3} {'ext_CER':>9} {'raw_CER':>9} {'exact':>7} {'rnd_CER':>9}")
    print("-"*55)
    by = defaultdict(list)
    for r in rows: by[r["level"]].append(r)
    for level in ("pre-algebra","algebra-1","algebra-2"):
        g = by[level]
        e = [r["extraction_cer"] for r in g if r["extraction_cer"] is not None]
        w = [r["extraction_cer_raw"] for r in g if r["extraction_cer_raw"] is not None]
        rr = [r["rendering_cer"] for r in g]
        es = f"{mean(e)*100:7.1f}%" if e else "   n/a  "
        ws = f"{mean(w)*100:7.1f}%" if w else "   n/a  "
        ex = f"{sum(1 for c in e if c == 0):>3}/{len(g)}" if e else "  n/a"
        print(f"{level:<12} {len(g):>3} {es:>9} {ws:>9} {ex:>7} {mean(rr)*100:7.1f}%")
    print("-"*55)
    es = f"{mean(ext_all)*100:7.1f}%" if ext_all else "   n/a  "
    ws = f"{mean(raw_all)*100:7.1f}%" if raw_all else "   n/a  "
    ex = f"{sum(1 for c in ext_all if c == 0):>3}/{len(rows)}" if ext_all else "  n/a"
    print(f"{'ALL':<12} {len(rows):>3} {es:>9} {ws:>9} {ex:>7} {mean(rnd_all)*100:7.1f}%")

    print(f"\nRendering: {sum(r['renders'] for r in rows)}/{len(rows)} formulas "
          f"render deterministically through KaTeX (rendering CER = "
          f"{mean(rnd_all)*100:.1f}%).")
    if fails:
        print("KaTeX could not render:")
        for i, ref, d in fails: print(f"  [{i}] {ref}  -> {d}")
    if not ext_all:
        print("Extraction: Pix2Text not available here -> run this on the encoder "
              "machine to fill the extraction column.")

    # remaining REAL extraction errors (norm CER > 0)
    real = [r for r in rows if r["extraction_cer"]]
    if real:
        print(f"\nRemaining REAL extraction errors ({len(real)} formulas, norm CER > 0):")
        for r in sorted(real, key=lambda r: -r["extraction_cer"]):
            print(f"  [{r['id']:>3}] CER {r['extraction_cer']*100:5.1f}%  "
                  f"ref={r['latex']!r}  ocr={r['ocr_pred']!r}")

    out = os.path.join(HERE, "oracle_cer_results.json")
    json.dump({"rows": rows,
               "mean_extraction_cer": mean(ext_all),
               "mean_extraction_cer_raw": mean(raw_all),
               "exact_extractions": sum(1 for c in ext_all if c == 0),
               "mean_rendering_cer": mean(rnd_all),
               "per_level": {lv: {
                   "n": len(by[lv]),
                   "extraction_cer": mean([r["extraction_cer"] for r in by[lv]
                                           if r["extraction_cer"] is not None]),
                   "extraction_cer_raw": mean([r["extraction_cer_raw"] for r in by[lv]
                                               if r["extraction_cer_raw"] is not None]),
                   "rendering_cer": mean([r["rendering_cer"] for r in by[lv]]),
               } for lv in by}}, open(out,"w"), indent=2)
    print(f"\n[oracle] wrote {out}")

if __name__ == "__main__":
    main()
