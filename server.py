#!/usr/bin/env python3
"""
LiteLecture on-demand conversion server (demo-grade, run on your own machine).

Wraps the existing encoder (src/encoder/encode.py) behind a tiny HTTP API the
web app talks to:

  POST /convert   {"url": "..."}      -> {"job": "<id>"} or {"error": "..."}
  GET  /status/<id>                    -> {"stage": "...", "error": ...}
  GET  /file/<id>                      -> the finished .litelec (JSON)

Design choices (deliberate, demo-grade):
  * LICENSE WHITELIST: only domains whose content licenses permit conversion
    (Khan Academy, MIT OpenCourseWare — CC BY-NC-SA). Anything else is refused
    with a clear message. This mirrors the project's license policy.
  * ONE JOB AT A TIME: encoding is heavy (Whisper + OCR); a simple queue
    protects the machine.
  * NO NEW DEPENDENCIES: Python standard library only. The encoder itself uses
    the repo venv (run this server with that venv's python).
  * Fresh conversions are machine-extracted only: their symbols carry
    verify.status = "flagged" (spec v0.2) until a human checks them.

Run:  python server.py          (from the repo root, inside the venv)
Then open the web app and use the Convert page. Server listens on :8571.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(HERE, "jobs")
ENCODER = os.path.join(HERE, "src", "encoder", "encode.py")
PORT = 8571

# Domains whose standard content license permits non-commercial conversion
# with attribution (CC BY-NC-SA). Everything else is refused.
LICENSE_WHITELIST = {
    "khanacademy.org": "CC BY-NC-SA 3.0 (Khan Academy)",
    "ocw.mit.edu": "CC BY-NC-SA 4.0 (MIT OpenCourseWare)",
}

JOBS = {}          # id -> {"stage", "url", "error", "path", "title"}
QUEUE = []         # job ids waiting
LOCK = threading.Lock()

STAGE_PATTERNS = [
    (re.compile(r"\[prepare"), "downloading"),
    (re.compile(r"\[transcribe"), "transcribing"),
    (re.compile(r"\[ocr"), "reading formulas"),
    (re.compile(r"\[assemble"), "assembling"),
]


def whitelist_check(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    for dom, license_name in LICENSE_WHITELIST.items():
        if host == dom or host.endswith("." + dom):
            return license_name
    return None


def _fetch(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def resolve_khan(url):
    """Khan lecture pages embed a YouTube video, but the pages are rendered by
    JavaScript and yt-dlp's Khan extractor is unreliable. Resolve the video id
    ourselves: (1) Khan's public video API by slug, (2) any id visible in the
    page HTML. The license whitelist was already checked on the original URL."""
    host = (urlparse(url).hostname or "").lower()
    if not (host == "khanacademy.org" or host.endswith(".khanacademy.org")):
        return url
    # (1) /v/<slug> -> Khan's video API
    m = re.search(r"/v/([^/?#]+)", url)
    if m:
        try:
            api = f"https://www.khanacademy.org/api/v1/videos/{m.group(1)}"
            data = json.loads(_fetch(api))
            yid = data.get("youtube_id") or data.get("translated_youtube_id")
            if yid and re.fullmatch(r"[A-Za-z0-9_-]{11}", yid):
                resolved = f"https://www.youtube.com/watch?v={yid}"
                print(f"[resolve] Khan API -> {resolved}")
                return resolved
            print("[resolve] Khan API had no youtube_id")
        except Exception as e:
            print(f"[resolve] Khan API failed ({e})")
    # (2) fall back to scanning the page HTML for an id
    try:
        html = _fetch(url)
        m = re.search(r'"(?:youtubeId|youtube_id)"\s*:\s*"([A-Za-z0-9_-]{11})"', html)
        if m:
            resolved = f"https://www.youtube.com/watch?v={m.group(1)}"
            print(f"[resolve] Khan page -> {resolved}")
            return resolved
        print("[resolve] no video id in Khan page; trying URL as-is")
    except Exception as e:
        print(f"[resolve] page fetch failed ({e}); trying URL as-is")
    return url


def worker():
    while True:
        with LOCK:
            job_id = QUEUE.pop(0) if QUEUE else None
        if job_id is None:
            time.sleep(0.5)
            continue
        job = JOBS[job_id]
        out = os.path.join(JOBS_DIR, job_id + ".litelec")
        job["stage"] = "starting"
        job["url"] = resolve_khan(job["url"])
        tail = []  # last lines of encoder output, for real error messages
        try:
            # ensure the encoder's subprocesses (yt-dlp etc.) use the SAME
            # venv this server runs in, even when the venv isn't activated
            env = os.environ.copy()
            env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
            cmd = [sys.executable, "-u", ENCODER, job["url"], "--out", out]
            if job.get("user_title"):
                cmd += ["--title", job["user_title"]]
            proc = subprocess.Popen(
                cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    print(f"[job {job_id}] {line}")   # echo to server console
                    tail.append(line)
                    if len(tail) > 20:
                        tail.pop(0)
                for pat, stage in STAGE_PATTERNS:
                    if pat.search(line):
                        job["stage"] = stage
            proc.wait()
            if proc.returncode != 0 or not os.path.exists(out):
                job["stage"] = "error"
                # surface the most informative lines: real ERROR lines first
                errs = [l for l in tail if "ERROR" in l.upper()]
                detail = " | ".join((errs or tail)[-4:]) or "no output from encoder"
                job["error"] = f"encoder failed: {detail[:400]}"
                continue
            try:
                doc = json.load(open(out, encoding="utf-8"))
                job["title"] = job.get("user_title") or \
                    doc.get("source", {}).get("title", "Converted lecture")
            except Exception:
                job["title"] = job.get("user_title") or "Converted lecture"
            job["path"] = out
            job["stage"] = "done"
        except Exception as e:
            job["stage"] = "error"
            job["error"] = str(e)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    def do_POST(self):
        if self.path.startswith("/publish/"):
            # copy a finished conversion into the web app's demos folder and
            # register it in the manifest; a git push then deploys it publicly
            import shutil
            job_id = self.path.split("/", 2)[2]
            if not re.fullmatch(r"[0-9a-f]{6,32}", job_id):
                return self._send(400, {"error": "bad job id"})
            src = os.path.join(JOBS_DIR, job_id + ".litelec")
            if not os.path.exists(src):
                return self._send(404, {"error": "no such conversion"})
            demos = os.path.join(HERE, "web", "public", "demos")
            os.makedirs(demos, exist_ok=True)
            shutil.copy2(src, os.path.join(demos, job_id + ".litelec"))
            try:
                doc = json.load(open(src, encoding="utf-8"))
                title = doc.get("source", {}).get("title") or "Converted lecture"
            except Exception:
                title = "Converted lecture"
            manifest_path = os.path.join(demos, "index.json")
            try:
                manifest = json.load(open(manifest_path, encoding="utf-8"))
            except Exception:
                manifest = []
            entry = {"file": f"/demos/{job_id}.litelec", "title": title}
            manifest = [m for m in manifest if m.get("file") != entry["file"]]
            manifest.append(entry)
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=1, ensure_ascii=False)
            print(f"[publish] {title!r} -> web/public/demos/{job_id}.litelec")
            return self._send(200, {"ok": True, "file": entry["file"],
                                    "title": title})
        if self.path.startswith("/publish_rename/"):
            job_id = self.path.split("/", 2)[2]
            if not re.fullmatch(r"[0-9a-f]{6,32}", job_id):
                return self._send(400, {"error": "bad id"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                title = (json.loads(self.rfile.read(n) or b"{}").get("title") or "").strip()[:120]
            except Exception:
                title = ""
            if not title:
                return self._send(400, {"error": "empty title"})
            demos = os.path.join(HERE, "web", "public", "demos")
            fpath = os.path.join(demos, job_id + ".litelec")
            mpath = os.path.join(demos, "index.json")
            if not os.path.exists(fpath):
                return self._send(404, {"error": "not published"})
            try:  # keep the file's own metadata in sync with the card title
                doc = json.load(open(fpath, encoding="utf-8"))
                doc.setdefault("source", {})["title"] = title
                with open(fpath, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, indent=2, ensure_ascii=False)
            except Exception:
                pass
            try:
                manifest = json.load(open(mpath, encoding="utf-8"))
            except Exception:
                manifest = []
            for m in manifest:
                if m.get("file") == f"/demos/{job_id}.litelec":
                    m["title"] = title
            with open(mpath, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=1, ensure_ascii=False)
            print(f"[publish] renamed {job_id} -> {title!r}")
            return self._send(200, {"ok": True, "title": title})
        if self.path.startswith("/unpublish/"):
            job_id = self.path.split("/", 2)[2]
            if not re.fullmatch(r"[0-9a-f]{6,32}", job_id):
                return self._send(400, {"error": "bad id"})
            demos = os.path.join(HERE, "web", "public", "demos")
            fpath = os.path.join(demos, job_id + ".litelec")
            mpath = os.path.join(demos, "index.json")
            if os.path.exists(fpath):
                os.remove(fpath)
            try:
                manifest = json.load(open(mpath, encoding="utf-8"))
            except Exception:
                manifest = []
            manifest = [m for m in manifest
                        if m.get("file") != f"/demos/{job_id}.litelec"]
            with open(mpath, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=1, ensure_ascii=False)
            print(f"[publish] unpublished {job_id}")
            return self._send(200, {"ok": True})
        if self.path != "/convert":
            return self._send(404, {"error": "unknown endpoint"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            url = (data.get("url") or "").strip()
            media_url = (data.get("media_url") or "").strip()
            user_title = (data.get("title") or "").strip()[:120]
        except Exception:
            return self._send(400, {"error": "bad request"})
        if not url.startswith(("http://", "https://")):
            return self._send(400, {"error": "That doesn't look like a URL."})
        license_name = whitelist_check(url)
        if license_name is None:
            allowed = ", ".join(sorted(LICENSE_WHITELIST))
            return self._send(403, {"error":
                f"That site isn't on the license whitelist yet. LiteLecture only "
                f"converts sources whose license allows it (currently: {allowed})."})
        # optional: direct video link for the SAME lecture (from the licensed
        # page's own embedded player) — used when the page can't be resolved
        if media_url:
            mh = (urlparse(media_url).hostname or "").lower()
            if mh not in ("www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com"):
                return self._send(400, {"error":
                    "The video link must be a YouTube URL copied from the "
                    "licensed page's own player."})
        job_id = uuid.uuid4().hex[:10]
        JOBS[job_id] = {"stage": "queued", "url": media_url or url, "error": None,
                        "path": None, "title": None, "user_title": user_title,
                        "license": license_name}
        with LOCK:
            QUEUE.append(job_id)
        return self._send(200, {"job": job_id, "license": license_name})

    def do_DELETE(self):
        if self.path.startswith("/job/"):
            job_id = self.path.split("/", 2)[2]
            if not re.fullmatch(r"[0-9a-f]{6,32}", job_id):
                return self._send(400, {"error": "bad job id"})
            path = os.path.join(JOBS_DIR, job_id + ".litelec")
            JOBS.pop(job_id, None)
            if os.path.exists(path):
                os.remove(path)
                print(f"[delete] removed jobs/{job_id}.litelec")
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "no such conversion"})
        return self._send(404, {"error": "unknown endpoint"})

    def do_GET(self):
        if self.path.startswith("/status/"):
            job = JOBS.get(self.path.split("/", 2)[2])
            if not job:
                return self._send(404, {"error": "unknown job"})
            return self._send(200, {"stage": job["stage"], "error": job["error"],
                                    "title": job["title"], "license": job["license"]})
        if self.path.startswith("/file/"):
            job_id = self.path.split("/", 2)[2]
            job = JOBS.get(job_id)
            path = job.get("path") if job else None
            if not path:  # not in memory (e.g., server restarted) -> disk
                if re.fullmatch(r"[0-9a-f]{6,32}", job_id):
                    cand = os.path.join(JOBS_DIR, job_id + ".litelec")
                    if os.path.exists(cand):
                        path = cand
            if not path:
                return self._send(404, {"error": "not ready"})
            return self._send(200, open(path, "rb").read())
        if self.path == "/list":
            out = []
            for name in sorted(os.listdir(JOBS_DIR)):
                if not name.endswith(".litelec"):
                    continue
                jid = name[:-len(".litelec")]
                try:
                    doc = json.load(open(os.path.join(JOBS_DIR, name),
                                         encoding="utf-8"))
                    title = doc.get("source", {}).get("title") or "Converted lecture"
                except Exception:
                    title = "Converted lecture"
                out.append({"id": jid, "title": title})
            return self._send(200, {"jobs": out})
        return self._send(404, {"error": "unknown endpoint"})

    def log_message(self, fmt, *args):  # quieter console
        pass


if __name__ == "__main__":
    os.makedirs(JOBS_DIR, exist_ok=True)
    # startup self-check: the encoder needs these on PATH / in the venv
    import shutil as _sh
    for tool, hint in [("yt-dlp", "pip install yt-dlp"),
                       ("ffmpeg", "install ffmpeg and add it to PATH")]:
        if not _sh.which(tool):
            print(f"WARNING: '{tool}' not found — conversions will fail. Fix: {hint}")
    threading.Thread(target=worker, daemon=True).start()
    print(f"LiteLecture convert server on http://localhost:{PORT}")
    print(f"Whitelist: {', '.join(sorted(LICENSE_WHITELIST))}")
    print("Keep this window open; the web app's Convert page talks to it.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
