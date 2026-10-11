#!/usr/bin/env python3
"""
Ground-truth oracle generator (Manim-equivalent, no animation engine needed).

Manim renders math as: LaTeX string -> typeset image -> video frames. We do the
same with pdflatex + pdftoppm + Pillow + ffmpeg, so the exact symbolic content of
every frame is KNOWN. For speed, all formulas are typeset in ONE multipage LaTeX
document (one compile), then each page is auto-cropped and centered on a canvas.

Outputs (in this dir):
  oracle.mp4         rendered lecture-style video of all formulas
  oracle_truth.json  exact ground-truth LaTeX + level + topic + timestamp each
"""
import json, os, subprocess, tempfile
from formulas import FORMULAS

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1280, 720
GAP_T, HOLD_T = 0.5, 2.5   # blank gap, formula hold (seconds)

def build_pdf(work):
    body = []
    for _, _, latex in FORMULAS:
        body.append(r"\thispagestyle{empty}\null\vfill\begin{center}$\displaystyle "
                    + latex + r"$\end{center}\vfill\newpage")
    tex = ("\\documentclass[12pt]{article}\n"
           "\\usepackage[paperwidth=12in,paperheight=6.75in,margin=0.5in]{geometry}\n"
           "\\usepackage{amsmath,amssymb}\n\\pagestyle{empty}\n"
           "\\begin{document}\n" + "\n".join(body) + "\n\\end{document}\n")
    path = os.path.join(work, "all.tex")
    open(path, "w").write(tex)
    r = subprocess.run(["pdflatex","-interaction=nonstopmode","-halt-on-error","all.tex"],
                       cwd=work, capture_output=True, text=True)
    if not os.path.exists(os.path.join(work, "all.pdf")):
        print(r.stdout[-2000:]); raise SystemExit("pdflatex failed")
    return os.path.join(work, "all.pdf")

def main():
    from PIL import Image, ImageChops
    work = tempfile.mkdtemp()
    pdf = build_pdf(work)
    # render every page to PNG in one pdftoppm call
    subprocess.run(["pdftoppm","-png","-r","200",pdf,os.path.join(work,"pg")], check=True)
    pages = sorted(p for p in os.listdir(work) if p.startswith("pg") and p.endswith(".png"))
    assert len(pages) == len(FORMULAS), f"{len(pages)} pages != {len(FORMULAS)} formulas"

    frames_dir = os.path.join(work, "frames"); os.makedirs(frames_dir)
    def autocrop(im):
        bg = Image.new("RGB", im.size, (255,255,255))
        bbox = ImageChops.difference(im.convert("RGB"), bg).getbbox()
        return im.crop(bbox) if bbox else im
    for i, pg in enumerate(pages):
        im = autocrop(Image.open(os.path.join(work, pg)).convert("RGB"))
        canvas = Image.new("RGB", (W, H), (255,255,255))
        scale = min(W*0.82/im.width, H*0.5/im.height, 4.0)
        im2 = im.resize((max(1,int(im.width*scale)), max(1,int(im.height*scale))))
        canvas.paste(im2, ((W-im2.width)//2, (H-im2.height)//2))
        canvas.save(os.path.join(frames_dir, f"f{i:03d}.png"))

    blank = os.path.join(work, "blank.png")
    Image.new("RGB", (W, H), (255,255,255)).save(blank)

    concat, truth, t = [], [], 0.0
    for i, (level, topic, latex) in enumerate(FORMULAS):
        concat.append((blank, GAP_T)); t += GAP_T
        truth.append({"id": i, "level": level, "topic": topic,
                      "t": round(t + HOLD_T/2, 2), "latex": latex})
        concat.append((os.path.join(frames_dir, f"f{i:03d}.png"), HOLD_T)); t += HOLD_T
    concat.append((blank, GAP_T)); t += GAP_T

    listf = os.path.join(work, "list.txt")
    with open(listf, "w") as f:
        for png, dur in concat:
            f.write(f"file '{png}'\nduration {dur}\n")
        f.write(f"file '{concat[-1][0]}'\n")
    out_mp4 = os.path.join(HERE, "oracle.mp4")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",listf,
                    "-vf",f"fps={FPS},format=yuv420p","-c:v","libx264","-crf","18",out_mp4],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    json.dump({"fps":FPS,"width":W,"height":H,"duration_s":round(t,2),"formulas":truth},
              open(os.path.join(HERE,"oracle_truth.json"),"w",encoding="utf-8"), indent=2)
    print(f"[oracle] wrote oracle.mp4 ({round(t,1)}s) + oracle_truth.json "
          f"with {len(truth)} ground-truth formulas")

if __name__ == "__main__":
    main()
