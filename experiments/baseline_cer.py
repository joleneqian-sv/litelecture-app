#!/usr/bin/env python3
"""
Controlled formula-fidelity experiment for the URTC paper (section V.B).

Question: how much does ordinary video compression damage a lecture's formulas?

Design (controlled, reproducible — no network needed):
  1. Render each ground-truth formula (from a .litelec's `symbols`) as a clean,
     centered "slide" image.
  2. Build those slides into a short pristine video (each slide a few seconds).
  3. Compress that video with H.265 (libx265) and AV1 (libaom-av1) at low bitrates.
  4. From each degraded slide, read the formula back with math-OCR (Pix2Text) and
     measure CER (character error rate) vs the known LaTeX.
  5. LiteLecture stores the formula as exact text -> CER = 0 by construction.

Because each frame contains ONLY the formula, OCR isn't confused by clutter and
the CER is a real 0..1 number that isolates compression's effect on legibility.

Outputs in --out: results.json, results.csv, cer_vs_bitrate.png,
per_formula.csv (per-formula diagnostics: ref vs OCR prediction at every
condition, including a pristine-PNG "OCR ceiling" pass that isolates pure
OCR error from compression error).

Runs on your machine: needs ffmpeg (libx265 + libaom-av1), Pix2Text, matplotlib.
Everything except the OCR step is codec/model-independent and tested in dev.

Usage:
  python baseline_cer.py web\\public\\demos\\algebra.litelec \
      --bitrates 25,50,100,200 --codecs libx265,libaom-av1 --out experiments\\out_algebra
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

SLIDE_SECONDS = 4          # each formula shown this long
W, H = 1280, 720           # slide resolution (a typical lecture board)

# matplotlib mathtext doesn't know a few LaTeX macros; map them to equivalents.
SANITIZE = {r"\implies": r"\Rightarrow"}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(" ".join(cmd[:4]) + " ...\n" + p.stderr[-800:] + "\n")
        raise RuntimeError("command failed: " + " ".join(cmd[:3]))
    return p.stdout


# ---------- metric ----------
def levenshtein(a, b):
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def cer(ref, hyp):
    r = "".join((ref or "").split())
    h = "".join((hyp or "").split())
    if not r:
        return 0.0
    return min(1.0, levenshtein(r, h) / len(r))  # clamp: 1.0 = "fully wrong"


# ---------- ground truth ----------
def load_truth(litelec_path):
    d = json.load(open(litelec_path, encoding="utf-8"))
    gt = [s["data"] for s in d.get("symbols", []) if s.get("kind") == "latex"]
    return {
        "title": d.get("source", {}).get("title", ""),
        "litelec_bytes": os.path.getsize(litelec_path),
        "original_bytes": d.get("source", {}).get("original_bytes", 0),
        "gt": gt,
    }


# ---------- render formulas -> pristine video ----------
def render_slides(formulas, workdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    slides = []
    for i, f in enumerate(formulas):
        tex = f
        for k, v in SANITIZE.items():
            tex = tex.replace(k, v)
        png = os.path.join(workdir, f"slide_{i:04d}.png")
        fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
        fig.patch.set_facecolor("white")
        try:
            fig.text(0.5, 0.5, f"${tex}$", ha="center", va="center", fontsize=46)
            fig.savefig(png, dpi=100)
        finally:
            plt.close(fig)
        slides.append({"png": png, "latex": f, "t_mid": i * SLIDE_SECONDS + SLIDE_SECONDS / 2})
    return slides


def build_source(workdir, out_mp4):
    # each slide_%04d.png shown SLIDE_SECONDS s; high quality (crf 18) pristine source
    run(["ffmpeg", "-y", "-framerate", f"1/{SLIDE_SECONDS}",
         "-i", os.path.join(workdir, "slide_%04d.png"),
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", "30", out_mp4])
    return os.path.getsize(out_mp4)


def encode(src, codec, br, out_path):
    common = ["ffmpeg", "-y", "-i", src, "-an",
              "-b:v", f"{br}k", "-maxrate", f"{br}k", "-bufsize", f"{br*2}k"]
    if codec == "libaom-av1":
        common += ["-c:v", "libaom-av1", "-cpu-used", "6", "-row-mt", "1"]
    elif codec == "libsvtav1":
        common += ["-c:v", "libsvtav1", "-preset", "8"]
    else:
        common += ["-c:v", codec]
    run(common + [out_path])
    return os.path.getsize(out_path)


def frame_at(video, t, out_png):
    run(["ffmpeg", "-y", "-ss", f"{t}", "-i", video, "-frames:v", "1", out_png])
    return out_png


# ---------- OCR ----------
_P2T = None


def ocr_formula(png):
    global _P2T
    if _P2T is None:
        from pix2text import Pix2Text
        try:
            _P2T = Pix2Text.from_config()
        except Exception:
            _P2T = Pix2Text()
    for attr in ("recognize_formula", "recognize_math"):
        fn = getattr(_P2T, attr, None)
        if fn:
            try:
                out = fn(png)
                if isinstance(out, dict):
                    out = out.get("text") or out.get("latex") or ""
                return (out or "").strip()
            except Exception:
                pass
    fn = getattr(_P2T, "recognize", None)
    if fn:
        import re
        try:
            out = fn(png)
            text = out if isinstance(out, str) else json.dumps(out)
            m = re.findall(r"\$+([^$]+)\$+", text)
            return m[0].strip() if m else text.strip()
        except Exception:
            pass
    return ""


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Controlled formula-CER experiment")
    ap.add_argument("litelec")
    ap.add_argument("--bitrates", default="25,50,100,200")
    ap.add_argument("--codecs", default="libx265,libaom-av1")
    ap.add_argument("--out", default="experiments/out")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    bitrates = [int(b) for b in args.bitrates.split(",") if b.strip()]
    codecs = [c.strip() for c in args.codecs.split(",") if c.strip()]
    os.makedirs(args.out, exist_ok=True)

    truth = load_truth(args.litelec)
    if not truth["gt"]:
        print("No latex symbols in the .litelec — nothing to score.")
        return
    print(f"Lecture: {truth['title']}")
    print(f"Formulas: {len(truth['gt'])}")

    workdir = tempfile.mkdtemp(prefix="cer_")
    slides = render_slides(truth["gt"], workdir)
    src = os.path.join(workdir, "pristine.mp4")
    src_bytes = build_source(workdir, src)
    print(f"Pristine source: {src_bytes/1024:.0f} KB ({len(slides)*SLIDE_SECONDS}s)")

    per_formula = []  # one row per (condition, formula): ref, OCR pred, CER

    # ---- OCR ceiling: OCR the pristine slide PNGs directly (no video, no codec).
    # Any error here is pure OCR error; compression can only add on top of it.
    print("\nOCR ceiling (pristine PNG slides, no compression):")
    ceiling = []
    for i, s in enumerate(slides):
        pred = ocr_formula(s["png"])
        c = cer(s["latex"], pred)
        ceiling.append(c)
        per_formula.append({"condition": "pristine_png", "codec": "none",
                            "bitrate_kbps": "", "formula_id": i,
                            "ref": s["latex"], "ocr_pred": pred,
                            "cer": round(c, 4)})
        flag = "" if c == 0 else "   <-- OCR misreads even pristine"
        print(f"  [{i}] CER {c*100:5.1f}%  ref={s['latex']!r}  ocr={pred!r}{flag}")
    ceil_avg = sum(ceiling) / len(ceiling) if ceiling else 0.0
    print(f"  ceiling avg CER: {ceil_avg*100:.1f}%")

    rows = [{"method": "LiteLecture (.litelec)", "codec": "deterministic",
             "bitrate_kbps": "", "bytes": truth["litelec_bytes"],
             "avg_cer": 0.0, "n": len(slides)},
            {"method": "OCR ceiling (pristine PNG)", "codec": "none",
             "bitrate_kbps": "", "bytes": src_bytes,
             "avg_cer": round(ceil_avg, 4), "n": len(ceiling)}]

    for codec in codecs:
        for br in bitrates:
            enc = os.path.join(workdir, f"{codec}_{br}.mp4")
            try:
                size = encode(src, codec, br, enc)
            except Exception as e:
                print(f"  [skip] {codec}@{br}k: {e}")
                continue
            cers = []
            for i, s in enumerate(slides):
                png = frame_at(enc, s["t_mid"], os.path.join(workdir, "f.png"))
                pred = ocr_formula(png)
                c = cer(s["latex"], pred)
                cers.append(c)
                per_formula.append({"condition": f"{codec}@{br}k", "codec": codec,
                                    "bitrate_kbps": br, "formula_id": i,
                                    "ref": s["latex"], "ocr_pred": pred,
                                    "cer": round(c, 4)})
            avg = sum(cers) / len(cers) if cers else 0.0
            rows.append({"method": f"{codec} @ {br}k", "codec": codec,
                         "bitrate_kbps": br, "bytes": size,
                         "avg_cer": round(avg, 4), "n": len(cers)})
            print(f"  {codec} @ {br}k: {size/1024:.0f} KB, avg CER {avg*100:.1f}%")

    # ---- diagnosis: which errors are compression-driven vs OCR-driven?
    print("\nPer-formula diagnosis (CER by condition):")
    for i, s in enumerate(slides):
        conds = [r for r in per_formula if r["formula_id"] == i]
        base = next(r["cer"] for r in conds if r["condition"] == "pristine_png")
        worst = max((r["cer"] for r in conds), default=0.0)
        if worst == 0:
            verdict = "clean everywhere"
        elif base > 0 and abs(worst - base) < 1e-9:
            verdict = "OCR-limited (same error pristine and compressed)"
        elif base == 0:
            verdict = "COMPRESSION-driven (clean pristine, degrades when compressed)"
        else:
            verdict = "mixed (OCR error grows under compression)"
        print(f"  [{i}] pristine {base*100:.1f}% / worst {worst*100:.1f}% -> {verdict}")

    json.dump({"truth": {k: truth[k] for k in ("title", "litelec_bytes", "original_bytes")},
               "pristine_bytes": src_bytes, "ocr_ceiling_avg_cer": round(ceil_avg, 4),
               "rows": rows, "per_formula": per_formula},
              open(os.path.join(args.out, "results.json"), "w"), indent=2)
    with open(os.path.join(args.out, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["method", "codec", "bitrate_kbps",
                                           "bytes", "avg_cer", "n"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "per_formula.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["condition", "codec", "bitrate_kbps",
                                           "formula_id", "ref", "ocr_pred", "cer"])
        w.writeheader()
        w.writerows(per_formula)
    plot(rows, codecs, bitrates, os.path.join(args.out, "cer_vs_bitrate.png"))
    print(f"\nWrote results.json, results.csv, per_formula.csv, "
          f"cer_vs_bitrate.png to {args.out}")
    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)


def plot(rows, codecs, bitrates, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    for codec in codecs:
        xs, ys = [], []
        for br in bitrates:
            for r in rows:
                if r["codec"] == codec and r["bitrate_kbps"] == br:
                    xs.append(br); ys.append(r["avg_cer"] * 100)
        if xs:
            ax.plot(xs, ys, marker="o", label=codec)
    ax.axhline(0, color="green", linewidth=2, label="LiteLecture (0%, by design)")
    ax.set_xlabel("Bitrate (kbps)")
    ax.set_ylabel("Formula Character Error Rate (%)")
    ax.set_title("Formula fidelity vs. compression bitrate")
    ax.legend(); ax.grid(True, alpha=0.3); fig.tight_layout()
    fig.savefig(out_png, dpi=150)


if __name__ == "__main__":
    main()
