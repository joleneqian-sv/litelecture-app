#!/usr/bin/env python3
"""
LiteLecture encoder — turn a real lecture video into a .litelec file.

Pipeline (4 stages):
  1. prepare    : obtain the video (yt-dlp if a URL), extract 16 kHz mono audio
                  and sample one frame every N seconds  (uses ffmpeg)
  2. transcribe : faster-whisper -> a real, timestamped transcript
  3. ocr        : Pix2Text reads on-screen math from the frames  (EXPERIMENTAL)
  4. assemble   : write a spec-compliant .litelec JSON file

Nothing here is invented. The transcript comes from the actual audio; the math
comes from the actual frames (or from a --symbols file you verified by hand).

Heavy libraries (faster_whisper, pix2text) and yt-dlp are imported lazily, only
when their stage runs, so the ffmpeg + assembly stages work without them.

Usage examples
--------------
  # Full run from a YouTube URL (needs internet + the AI libs installed)
  python encode.py "https://www.youtube.com/watch?v=riXcZT2ICjA" \
      --title "Khan Academy - Introduction to Limits" \
      --creator "Khan Academy" \
      --license "CC BY-NC-SA 3.0" \
      --out limits-intro.litelec

  # From a local video file already on disk
  python encode.py video/Algebra.mp4 --out algebra.litelec

  # Skip flaky OCR and inject formulas you verified yourself
  python encode.py input.mp4 --stages prepare,transcribe,assemble \
      --symbols my_verified_symbols.json --out out.litelec
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def run(cmd):
    """Run a shell command, raise a clear error if it fails."""
    print(f"  $ {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + "\n" + proc.stderr + "\n")
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")
    return proc.stdout


def have(tool):
    return shutil.which(tool) is not None


# ---------------------------------------------------------------- stage 1
def stage_prepare(source, workdir, frame_interval):
    """Get video -> audio.wav + frames + duration. Returns a meta dict."""
    os.makedirs(workdir, exist_ok=True)
    is_url = source.startswith("http://") or source.startswith("https://")

    vid_title, vid_creator, vid_url = "", "", ""
    if is_url:
        if not have("yt-dlp"):
            raise RuntimeError("yt-dlp not found. Install it (pip install yt-dlp) "
                               "or pass a local video file instead of a URL.")
        vid_url = source
        try:
            print("[prepare] reading video info ...")
            info = run(["yt-dlp", "--no-playlist", "--skip-download",
                        "--remote-components", "ejs:github",
                        "--print", "%(title)s",
                        "--print", "%(uploader)s",
                        "--print", "%(webpage_url)s", source]).strip().split("\n")
            if len(info) >= 1 and info[0].strip():
                vid_title = info[0].strip()
            if len(info) >= 2 and info[1].strip():
                vid_creator = info[1].strip()
            if len(info) >= 3 and info[2].strip():
                vid_url = info[2].strip()
            print(f"[prepare] title: {vid_title}  |  uploader: {vid_creator}")
        except Exception:
            print("[prepare] (could not read metadata; continuing)")
        print("[prepare] downloading video with yt-dlp ...")
        out_tmpl = os.path.join(workdir, "source.%(ext)s")
        base = ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
                # YouTube requires solving JS challenges; allow yt-dlp to
                # fetch its solver (needs deno installed)
                "--remote-components", "ejs:github",
                "--merge-output-format", "mp4", "-o", out_tmpl]
        # YouTube sometimes refuses the default player client for videos that
        # do exist (embed-only, kids-flagged, etc.). Retry with alternates.
        attempts = [
            base + [source],
            base + ["--extractor-args", "youtube:player_client=web_embedded",
                    source],
            base + ["--extractor-args", "youtube:player_client=android", source],
        ]
        last_err = None
        for i, cmd in enumerate(attempts):
            try:
                if i:
                    print(f"[prepare] retrying with alternate player client "
                          f"({i}/{len(attempts)-1}) ...")
                run(cmd)
                last_err = None
                break
            except Exception as e:
                last_err = e
        if last_err is not None:
            raise last_err
        vids = [f for f in os.listdir(workdir) if f.startswith("source.")]
        if not vids:
            raise RuntimeError("yt-dlp did not produce a video file.")
        video_path = os.path.join(workdir, vids[0])
    else:
        if not os.path.isfile(source):
            raise RuntimeError(f"Local file not found: {source}")
        video_path = source

    original_bytes = 0
    try:
        original_bytes = os.path.getsize(video_path)
    except OSError:
        pass

    if not have("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH.")

    # audio: 16 kHz mono wav (what Whisper wants)
    print("[prepare] extracting audio (16 kHz mono) ...")
    audio_path = os.path.join(workdir, "audio.wav")
    run(["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000",
         "-vn", audio_path])

    # frames: one every `frame_interval` seconds
    print(f"[prepare] sampling frames every {frame_interval}s ...")
    frames_dir = os.path.join(workdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    run(["ffmpeg", "-y", "-i", video_path, "-vf", f"fps=1/{frame_interval}",
         "-q:v", "2", os.path.join(frames_dir, "frame_%04d.jpg")])
    frame_files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    frames = [{"path": os.path.join(frames_dir, f),
               "t": round(i * frame_interval, 2)}
              for i, f in enumerate(frame_files)]

    # duration via ffprobe (fallback: 0, filled later from transcript)
    duration = 0.0
    if have("ffprobe"):
        try:
            out = run(["ffprobe", "-v", "error", "-show_entries",
                       "format=duration", "-of",
                       "default=noprint_wrappers=1:nokey=1", video_path])
            duration = round(float(out.strip()), 2)
        except Exception:
            pass

    meta = {"audio": audio_path, "frames": frames, "duration_s": duration,
            "frame_interval": frame_interval,
            "title": vid_title, "creator": vid_creator, "url": vid_url,
            "original_bytes": original_bytes}
    with open(os.path.join(workdir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print(f"[prepare] done: {len(frames)} frames, duration {duration}s")
    return meta


# ---------------------------------------------------------------- stage 2
def stage_transcribe(workdir, model_name):
    """faster-whisper -> resegmented transcript array."""
    from faster_whisper import WhisperModel  # lazy import

    audio_path = os.path.join(workdir, "audio.wav")
    print(f"[transcribe] loading Whisper model '{model_name}' (CPU) ...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print("[transcribe] transcribing (this can take a while on CPU) ...")
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    # Collect words; regroup into short 3-8 word phrase chunks on sentence ends.
    transcript = []
    cur, cur_start = [], None
    last_end = 0.0
    for seg in segments:
        words = getattr(seg, "words", None)
        if not words:  # model without word timestamps -> use whole segment
            transcript.append({"t": round(seg.start, 2),
                               "text": seg.text.strip(), "speaker": "S1"})
            last_end = seg.end
            continue
        for w in words:
            if cur_start is None:
                cur_start = w.start
            cur.append(w.word)
            last_end = w.end
            ends_sentence = w.word.strip().endswith((".", "?", "!"))
            if len(cur) >= 8 or ends_sentence:
                transcript.append({"t": round(cur_start, 2),
                                   "text": "".join(cur).strip(), "speaker": "S1"})
                cur, cur_start = [], None
    if cur:
        transcript.append({"t": round(cur_start, 2),
                           "text": "".join(cur).strip(), "speaker": "S1"})

    with open(os.path.join(workdir, "transcript.json"), "w") as fh:
        json.dump(transcript, fh, indent=2)
    print(f"[transcribe] done: {len(transcript)} chunks, "
          f"lang={info.language} ({info.language_probability:.2f})")
    return transcript, round(last_end, 2)


# ---------------------------------------------------------------- stage 3
def _recognize_formula(p2t, path):
    """Try a few Pix2Text API shapes; return a LaTeX string or ''. """
    for attr in ("recognize_formula", "recognize_math"):
        fn = getattr(p2t, attr, None)
        if fn:
            try:
                out = fn(path)
                if isinstance(out, dict):
                    out = out.get("text") or out.get("latex") or ""
                return (out or "").strip()
            except Exception:
                pass
    # last resort: full-page recognize, pull $...$ math out of the markdown
    fn = getattr(p2t, "recognize", None)
    if fn:
        try:
            out = fn(path)
            text = out if isinstance(out, str) else json.dumps(out)
            m = re.findall(r"\$+([^$]+)\$+", text)
            return m[0].strip() if m else ""
        except Exception:
            pass
    return ""


def _recognize_frame_formulas(p2t, path):
    """Extract the FORMULAS from a mixed slide (text + math), rather than
    treating the whole frame as one formula. Uses Pix2Text's page/mixed
    recognition when available; falls back to whole-frame formula OCR for
    single-equation frames (the original behavior)."""
    fn = getattr(p2t, "recognize", None)
    if fn:
        try:
            out = fn(path)
            found = []
            if isinstance(out, list):  # list of {type, text, position} regions
                for el in out:
                    if not isinstance(el, dict):
                        continue
                    kind = str(el.get("type", "")).lower()
                    if "formula" in kind or "isolated" in kind or "embedding" in kind:
                        tex = (el.get("text") or "").strip().strip("$").strip()
                        if tex:
                            found.append(tex)
            elif isinstance(out, str):  # markdown with $...$ / $$...$$ math
                found = [m.strip() for m in re.findall(r"\$+([^$]+)\$+", out)]
            if found:
                return found
        except Exception:
            pass
    single = _recognize_formula(p2t, path)
    return [single] if single else []


OLLAMA_HOST = "http://localhost:11434"

_VLM_PROMPT = (
    "You are a math OCR engine. Look at this lecture frame and transcribe "
    "EVERY mathematical formula or equation that is visible, including "
    "handwritten ones, as LaTeX. Rules: output one formula per line; output "
    "ONLY the LaTeX, no commentary, no markdown fences, no $ signs; transcribe "
    "exactly what is written (do not solve or complete anything); if a formula "
    "is partially visible or illegible, skip it; do NOT transcribe tables, "
    "table borders, or layout (never output \\multicolumn, \\hline, or "
    "alignment characters like &); if there are no formulas, output exactly "
    "NONE."
)


def _clean_vlm_line(line):
    """Normalize one VLM output line into displayable LaTeX (or '' to drop):
    strip bullets/delimiters, drop slide prose and layout environments, and
    wrap bare word-runs in \\text{} so labels typeset upright."""
    line = line.strip().strip("`").strip("$").strip()
    line = re.sub(r"^[-*\d.)\s]+", "", line)                 # list numbering
    line = re.sub(r"^(\\(textbullet|bullet|item|cdot)\b|[•·▪‣])\s*", "", line)
    # inline/display math delimiters -> plain (KaTeX displayMode rejects them)
    line = re.sub(r"\\[()\[\]]", " ", line)
    line = re.sub(r"\\\\\s*$", "", line).strip()             # trailing row break
    line = line.lstrip("&").strip()
    if not line:
        return ""
    # text-mode layout environments are slide structure, not math
    if re.search(r"\\(begin|end)\{(itemize|enumerate|center|document|"
                 r"figure|table|tabular|frame)\}", line):
        return ""
    # a lone \begin{...} or \end{...} (opener/closer with no content) is a
    # table skeleton split across lines, not a formula
    if re.fullmatch(r"\\(begin|end)\{[a-zA-Z*]+\}(\{[^{}]*\})*", line):
        return ""
    # ORPHANED environment shells: the model split a multi-line construct, so
    # a line carries \begin{...} without its \end{...} (or vice versa) —
    # strip the shell pieces, keep any real math that remains
    if line.count("\\begin{") != line.count("\\end{"):
        line = re.sub(r"\\left\s*(\\\{|\\\.|\(|\[)?\s*"
                      r"\\begin\{[a-zA-Z*]+\}(\{[^{}]*\})?", " ", line)
        line = re.sub(r"\\begin\{[a-zA-Z*]+\}(\{[^{}]*\})?", " ", line)
        line = re.sub(r"\\end\{[a-zA-Z*]+\}\s*"
                      r"(\\right\s*(\\\}|\\\.|\)|\]|\.)?)?", " ", line)
        line = line.strip()
        if not line or re.fullmatch(r"[.\s\\]*", line):
            return ""
    # unbalanced braces render wrong — a fragment of a bigger expression
    t = re.sub(r"\\[{}]", "", line)
    if t.count("{") != t.count("}"):
        return ""
    # a line STARTING with a binary operator is a fragment of a split cell
    if re.match(r"^[/*=^_+]", line):
        return ""
    # a line with 4+ plain words is slide prose; the transcript covers prose
    bare = re.findall(r"\b[A-Za-z]{2,}\b", re.sub(r"\\[a-zA-Z]+", " ", line))
    if len(bare) >= 4:
        return ""
    # short word-runs ("First roll") -> \text{...} so they render upright
    line = re.sub(r"(?<![\\{a-zA-Z])([A-Za-z]{2,}(?:\s+[A-Za-z]{2,})*)",
                  lambda m: "\\text{" + m.group(1) + "}", line)
    return re.sub(r"\s+", " ", line).strip()


def _vlm_available(host=OLLAMA_HOST):
    try:
        import urllib.request
        urllib.request.urlopen(host + "/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _vlm_frame_formulas(path, model, host=OLLAMA_HOST):
    """Ask a local vision-language model (via Ollama) for the formulas in a
    frame. Returns a list of LaTeX strings ([] if none / on failure)."""
    import base64
    import urllib.request
    try:
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        payload = {"model": model, "prompt": _VLM_PROMPT, "images": [b64],
                   "stream": False, "options": {"temperature": 0}}
        req = urllib.request.Request(
            host + "/api/generate", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=300).read())
        text = (resp.get("response") or "").strip()
        if not text or text.strip().upper() == "NONE":
            return []
        out = []
        for line in text.splitlines():
            line = _clean_vlm_line(line)
            if line and line.upper() != "NONE":
                out.append(line)
        return out
    except Exception as e:
        print(f"[ocr] VLM call failed ({e}); skipping frame")
        return []


_KATEX_CHECK_JS = (
    "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{"
    "const katex=require('katex');const lines=JSON.parse(d);"
    "const out=lines.map(s=>{try{katex.renderToString(s,"
    "{throwOnError:true,displayMode:true});return true;}catch(e){return false;}});"
    "console.log(JSON.stringify(out));});"
)


def _drop_unrenderable(symbols):
    """Final gate: validate every LaTeX symbol with the SAME renderer the
    player uses (KaTeX via node). Anything that fails to compile (e.g. a
    double subscript from a misread) is dropped — a formula that cannot render
    helps nobody. Gracefully skips if node/katex are unavailable."""
    latex_syms = [s for s in symbols if s.get("kind") == "latex"]
    if not latex_syms:
        return symbols
    web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web")
    try:
        p = subprocess.run(
            ["node", "-e", _KATEX_CHECK_JS], cwd=web,
            input=json.dumps([s["data"] for s in latex_syms]),
            capture_output=True, text=True, timeout=60)
        ok = json.loads(p.stdout.strip())
        assert len(ok) == len(latex_syms)
    except Exception as e:
        print(f"[ocr] KaTeX validity check unavailable ({e}); keeping all")
        return symbols
    keep, dropped = [], 0
    verdicts = dict(zip((id(s) for s in latex_syms), ok))
    for s in symbols:
        if s.get("kind") == "latex" and not verdicts.get(id(s), True):
            print(f"[ocr] dropped unrenderable LaTeX: {s['data'][:50]!r}")
            dropped += 1
            continue
        keep.append(s)
    if dropped:
        print(f"[ocr] KaTeX validity gate removed {dropped} symbol(s)")
    return keep


def stage_ocr(workdir, meta, default_duration, backend="auto",
              vlm_model="qwen2.5vl:7b"):
    """Frames -> deduplicated symbols array. Backend 'vlm' uses a local
    vision-language model via Ollama (better on handwriting); 'pix2text' uses
    the classic math-OCR; 'auto' prefers the VLM when Ollama is running."""
    use_vlm = backend == "vlm" or (backend == "auto" and _vlm_available())
    if use_vlm:
        print(f"[ocr] using local VLM via Ollama: {vlm_model}")
        recognize = lambda p: _vlm_frame_formulas(p, vlm_model)
    else:
        from pix2text import Pix2Text  # lazy import
        print("[ocr] loading Pix2Text ... (handwriting OCR is experimental; "
              "for better handwriting support run Ollama with a vision model)")
        try:
            p2t = Pix2Text.from_config()
        except Exception:
            p2t = Pix2Text()
        recognize = lambda p: _recognize_frame_formulas(p2t, p)

    symbols, seen = [], set()
    for fr in meta["frames"]:
        for latex in recognize(fr["path"]):
            if _looks_like_junk(latex):
                print(f"[ocr] t={fr['t']:.0f}s: dropped unreadable OCR output "
                      f"({latex[:40]!r}…)")
                continue
            key = re.sub(r"\s+", "", latex)
            if len(key) < 3 or key in seen:  # skip trivia and repeats
                continue
            seen.add(key)
            # spec v0.2: machine-extracted symbols start FLAGGED; they may only
            # become "verified" after ASR cross-check or human approval
            symbols.append({"t": fr["t"], "kind": "latex", "data": latex,
                            "verify": {"source": "ocr", "confidence": None,
                                       "status": "flagged"}})
    symbols = _drop_unrenderable(symbols)
    # give each symbol a duration = until the next one (or to the end)
    for i, s in enumerate(symbols):
        nxt = symbols[i + 1]["t"] if i + 1 < len(symbols) else default_duration
        s["duration_s"] = round(max(0.5, nxt - s["t"]), 2)

    with open(os.path.join(workdir, "symbols.json"), "w") as fh:
        json.dump(symbols, fh, indent=2)
    print(f"[ocr] done: {len(symbols)} symbol(s) (verify these by eye!)")
    return symbols


# ---------------------------------------------------------------- stage 4
def _looks_like_junk(latex):
    """Heuristics for OCR output that is clearly not a real formula (typical
    for handwritten boards): brace soup, degenerate arrays, heavy repetition,
    or absurd length. Junk is dropped rather than shipped; borderline symbols
    still ship but stay verify.status='flagged'."""
    s = re.sub(r"\s+", "", latex)
    if len(s) > 150:
        return True
    # table-layout fragments (slide skeletons, not math)
    if re.search(r"\\multicolumn|\\hline|\\cline|\\tabular", s):
        return True
    if re.fullmatch(r"[&\\{}|\[\]\s.\-]*", s):  # only structure chars, no content
        return True
    # a top-level & is a table separator, not math (matrix/cases keep \begin{)
    if "&" in s and "\\begin{" not in s:
        return True
    if "\\begin{array}" in s and "{{}}" in s:
        return True
    # the same 10-char chunk appearing 4+ times = OCR stutter
    for i in range(0, max(1, len(s) - 10), 5):
        if s.count(s[i:i + 10]) >= 4:
            return True
    # mostly braces/backslashes, hardly any actual content
    content = len(re.findall(r"[A-Za-z0-9=+\-*/<>.,()]", s))
    if len(s) > 20 and content / len(s) < 0.35:
        return True
    return False


def stage_assemble(args, transcript, symbols, duration, original_bytes=0):
    note = ("Encoded by LiteLecture v0.2: audio transcribed with faster-whisper; "
            "math from " + ("a verified --symbols file" if args.symbols
                            else "Pix2Text OCR (experimental)") + ".")
    doc = {
        "format": "litelec",
        "version": "0.2",
        "source": {
            "title": args.title,
            "url": args.url or (args.input if args.input.startswith("http") else ""),
            "creator": args.creator,
            "duration_s": duration,
            "license": args.license,
            "license_url": args.license_url,
            "modified": True,
            "modification_note": note,
            "original_bytes": original_bytes,
        },
        "audio": {"mode": "tts_only"},
        "transcript": transcript,
        "symbols": symbols,
        "scenes": [{"t": 0, "layout": "whiteboard", "background": "white"}],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    size = os.path.getsize(args.out)
    print(f"[assemble] wrote {args.out}  ({size/1024:.1f} KB)")
    return doc


def main():
    ap = argparse.ArgumentParser(description="Encode a lecture video into .litelec")
    ap.add_argument("input", help="video URL or local file path")
    ap.add_argument("--out", default="out.litelec")
    ap.add_argument("--frame-interval", type=int, default=5)
    ap.add_argument("--model", default="base.en")
    ap.add_argument("--title", default="Untitled lecture")
    ap.add_argument("--creator", default="Unknown")
    ap.add_argument("--url", default="")
    ap.add_argument("--license", default="CC BY-NC-SA 3.0")
    ap.add_argument("--license-url",
                    default="https://creativecommons.org/licenses/by-nc-sa/3.0/")
    ap.add_argument("--stages", default="prepare,transcribe,ocr,assemble")
    ap.add_argument("--symbols", default=None,
                    help="JSON file of verified symbols (skips/overrides OCR)")
    ap.add_argument("--ocr-backend", default="auto",
                    choices=["auto", "vlm", "pix2text"],
                    help="auto = use local Ollama VLM if running, else Pix2Text")
    ap.add_argument("--vlm-model", default="qwen2.5vl:7b",
                    help="Ollama vision model tag for --ocr-backend vlm/auto")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--keep", action="store_true", help="keep intermediate files")
    ap.add_argument("--measure", action="store_true",
                    help="just download the video, print its exact byte size, and exit")
    args = ap.parse_args()

    if args.measure:
        wd = tempfile.mkdtemp(prefix="litelec_measure_")
        try:
            out_tmpl = os.path.join(wd, "source.%(ext)s")
            run(["yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
                 "--merge-output-format", "mp4", "-o", out_tmpl, args.input])
            vids = [f for f in os.listdir(wd) if f.startswith("source.")]
            if not vids:
                print("MEASURE: download produced no file")
                return
            n = os.path.getsize(os.path.join(wd, vids[0]))
            print(f"\nORIGINAL_BYTES={n}   (~{n/1024/1024:.1f} MB)")
        finally:
            shutil.rmtree(wd, ignore_errors=True)
        return

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    workdir = args.workdir or tempfile.mkdtemp(prefix="litelec_")
    print(f"workdir: {workdir}\nstages : {stages}\n")

    meta = {"frames": [], "duration_s": 0.0, "frame_interval": args.frame_interval}
    transcript, symbols, duration = [], [], 0.0

    if "prepare" in stages:
        meta = stage_prepare(args.input, workdir, args.frame_interval)
        duration = meta["duration_s"]
        if args.title == "Untitled lecture" and meta.get("title"):
            args.title = meta["title"]
        if args.creator == "Unknown" and meta.get("creator"):
            args.creator = meta["creator"]
        if not args.url and meta.get("url"):
            args.url = meta["url"]
    if "transcribe" in stages:
        transcript, last_end = stage_transcribe(workdir, args.model)
        if duration <= 0:
            duration = last_end
    if args.symbols:                       # verified file overrides OCR
        with open(args.symbols) as fh:
            symbols = json.load(fh)
        for s in symbols:                  # spec v0.2: human-supplied = verified
            s.setdefault("verify", {"source": "manual", "confidence": 1.0,
                                    "status": "verified"})
        print(f"[ocr] using {len(symbols)} verified symbol(s) from {args.symbols}")
    elif "ocr" in stages:
        symbols = stage_ocr(workdir, meta, duration or 1e9,
                            backend=args.ocr_backend, vlm_model=args.vlm_model)
    if "assemble" in stages:
        stage_assemble(args, transcript, symbols, duration,
                       meta.get("original_bytes", 0))

    if not args.keep and not args.workdir and "prepare" in stages:
        shutil.rmtree(workdir, ignore_errors=True)
    print("\nDone.")


if __name__ == "__main__":
    main()
