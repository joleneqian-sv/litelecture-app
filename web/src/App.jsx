import { useEffect, useMemo, useRef, useState } from "react";
import Formula from "./Formula.jsx";
import Tokens from "./Tokens.jsx";
import { latexToSpeech } from "./mathspeak.js";

// Available lectures (add more demos here as they're encoded).
// Each card's cover is drawn from the lecture's own formulas (KaTeX),
// so covers cost zero image bytes and always match the content.
const DEMOS = [
  {
    label: "Limits — Introduction (Khan)",
    title: "Limits — Introduction",
    source: "Converted under Khan Academy license",
    url: "/demos/limits-intro.litelec",
    color: "#5b2a86",
    cover: ["\\lim_{x \\to 1} \\frac{x^2-1}{x-1}", "f(x)=\\frac{x^2-1}{x-1}"],
  },
  {
    label: "Pre-Algebra — Percent → Decimal & Fraction (Khan)",
    title: "Percent, Decimal & Fraction",
    source: "Converted under Khan Academy license",
    url: "/demos/algebra.litelec",
    color: "#1d3f8f",
    cover: ["18\\% = \\frac{18}{100}", "\\frac{18}{100} = 0.18"],
  },
  {
    label: "Algebra I — Solving 3x + 5 = 17 (Khan)",
    title: "Solving 3x + 5 = 17",
    source: "Converted under Khan Academy license",
    url: "/demos/demo3.litelec",
    color: "#0b5d4a",
    cover: ["3x + 5 = 17", "x = 4"],
  },
];

function fmt(t) {
  const s = Math.floor(t % 60);
  const m = Math.floor(t / 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function fmtBytes(n) {
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  if (n >= 1024) return Math.round(n / 1024) + " KB";
  return n + " B";
}

// Merge short transcript fragments into full sentences so the voice can speak
// each one with natural intonation (and the caption shows the whole sentence).
function buildSentences(chunks) {
  const out = [];
  let cur = null;
  for (const c of chunks) {
    const text = (c.text || "").trim();
    if (!text) continue;
    if (!cur) cur = { t: c.t, text };
    else cur.text += " " + text;
    // break on sentence end — or when the merged text gets long (transcripts
    // with sparse punctuation would otherwise build giant utterances, which
    // Chrome's speech engine handles badly)
    if (/[.?!]["')\]]?$/.test(text) || cur.text.length > 220) {
      out.push(cur);
      cur = null;
    }
  }
  if (cur) out.push(cur);
  return out;
}

// Local on-demand conversion server (see server.py in the repo root).
const CONVERT_SERVER = "http://localhost:8571";
const CONVERT_STAGES = [
  "queued",
  "starting",
  "downloading",
  "transcribing",
  "reading formulas",
  "assembling",
  "done",
];

function pickDefaultVoice(voices) {
  const prefer = ["natural", "aria", "jenny", "guy", "google", "zira"];
  for (const p of prefer) {
    const v = voices.find((v) => v.name.toLowerCase().includes(p));
    if (v) return v;
  }
  return voices[0];
}

export default function App() {
  const [view, setView] = useState("browse"); // "browse" | "player"
  const [demoUrl, setDemoUrl] = useState(DEMOS[0].url);

  // Keep the BROWSER's back button working: entering the player pushes a
  // history entry, and pressing Back (browser or in-app) returns to Browse
  // instead of leaving the site.
  useEffect(() => {
    if (window.location.hash === "#player") {
      // refreshed while in player view -> start at Browse with a clean URL
      window.history.replaceState({}, "", window.location.pathname);
    }
    const onPop = () =>
      setView(window.location.hash === "#player" ? "player" : "browse");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function openLecture(url) {
    setDemoUrl(url);
    setView("player");
    window.history.pushState({}, "", "#player");
  }

  function goBrowse() {
    if (window.location.hash === "#player") window.history.back();
    else setView("browse");
  }

  // ---- On-demand conversion (talks to the local server.py) ----
  const [convertUrl, setConvertUrl] = useState("");
  const [convertMediaUrl, setConvertMediaUrl] = useState("");
  const [convertTitle, setConvertTitle] = useState("");
  const [contactPage, setContactPage] = useState("");
  const [contactVideo, setContactVideo] = useState("");
  const [contactName, setContactName] = useState("");

  function sendRequest(e) {
    e.preventDefault();
    const subject = "LiteLecture — lecture request";
    const body =
      `Lecture page link: ${contactPage}\n` +
      `Video link: ${contactVideo}\n` +
      (contactName ? `Requested by: ${contactName}\n` : "");
    window.location.href =
      `mailto:jolene.qian@gmail.com?subject=${encodeURIComponent(subject)}` +
      `&body=${encodeURIComponent(body)}`;
  }
  // Publisher mode: the Convert box only appears when the local conversion
  // server is running. On the public site it stays hidden — conversion is a
  // publisher-side tool; playback needs no server.
  const [serverUp, setServerUp] = useState(false);
  const [converted, setConverted] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("litelec.converted") || "[]");
    } catch {
      return [];
    }
  });
  // published lectures = converted files shipped in /demos + listed in the
  // manifest; these appear for every visitor of the deployed site
  const [published, setPublished] = useState([]);

  useEffect(() => {
    fetch("/demos/index.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => setPublished(Array.isArray(list) ? list : []))
      .catch(() => {});
  }, []);

  // sizes[url] = { lite, orig } — fetched from each (tiny, cached) .litelec
  const [sizes, setSizes] = useState({});

  useEffect(() => {
    if (view !== "browse") return;
    const urls = [
      ...DEMOS.map((d) => d.url),
      ...published.map((d) => d.file),
      ...converted.map((d) => d.url),
    ];
    urls.forEach(async (url) => {
      if (sizes[url]) return;
      try {
        const r = await fetch(url);
        if (!r.ok) return;
        const buf = await r.arrayBuffer();
        const doc = JSON.parse(new TextDecoder().decode(buf));
        setSizes((s) => ({
          ...s,
          [url]: {
            lite: buf.byteLength,
            orig: doc.source?.original_bytes || 0,
            srcUrl: doc.source?.url || "",
            cover: (doc.symbols || [])
              .filter((s) => s.kind === "latex")
              .slice(0, 2)
              .map((s) => s.data),
          },
        }));
      } catch {
        /* size line simply not shown */
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, converted, published]);

  function sizeLine(url) {
    const z = sizes[url];
    if (!z) return null;
    let s = fmtBytes(z.lite);
    if (z.orig > 0) {
      s += ` · video ${fmtBytes(z.orig)} (${Math.round(z.orig / z.lite)}× smaller)`;
    }
    return <div className="cardsize">{s}</div>;
  }

  const COVER_PALETTE = ["#5b2a86", "#1d3f8f", "#0b5d4a", "#7a4a12", "#3d3d7a", "#8f2d56"];

  function coverArt(url, title) {
    // deterministic color from the title, so each lecture looks distinct
    let h = 0;
    for (const c of title || url) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const bg = COVER_PALETTE[h % COVER_PALETTE.length];
    const tex = sizes[url]?.cover;
    return (
      <div className="cover" style={{ background: bg }}>
        {tex && tex.length ? (
          tex.map((f, i) => (
            <div className="coverline" key={i}>
              <Formula latex={f} />
            </div>
          ))
        ) : (
          <div className="covertitle">{title}</div>
        )}
      </div>
    );
  }

  function origLink(url) {
    const src = sizes[url]?.srcUrl;
    if (!src) return null;
    return (
      <a
        className="origlink"
        href={src}
        target="_blank"
        rel="noopener noreferrer"
      >
        original video ↗
      </a>
    );
  }

  useEffect(() => {
    if (view !== "browse") return;
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 1500);
    fetch(`${CONVERT_SERVER}/status/probe`, { signal: ctl.signal })
      .then(async () => {
        setServerUp(true); // any HTTP answer = server present
        // rediscover past conversions from the server's jobs folder, so
        // cards survive restarts, port changes, and different browsers
        try {
          const r = await fetch(`${CONVERT_SERVER}/list`);
          const { jobs } = await r.json();
          setConverted((cur) => {
            const known = new Set(cur.map((x) => x.url));
            const found = (jobs || [])
              .map((j) => ({
                title: j.title,
                url: `${CONVERT_SERVER}/file/${j.id}`,
              }))
              .filter((e) => !known.has(e.url));
            if (!found.length) return cur;
            const next = [...cur, ...found];
            localStorage.setItem("litelec.converted", JSON.stringify(next));
            return next;
          });
        } catch {
          /* list is best-effort */
        }
      })
      .catch(() => setServerUp(false))
      .finally(() => clearTimeout(t));
    return () => ctl.abort();
  }, [view]);
  const [convert, setConvert] = useState(null); // {job, stage, error, title}

  useEffect(() => {
    if (!convert?.job || convert.stage === "done" || convert.stage === "error")
      return;
    const t = setInterval(async () => {
      try {
        const r = await fetch(`${CONVERT_SERVER}/status/${convert.job}`);
        const s = await r.json();
        setConvert((c) => ({ ...c, stage: s.stage, error: s.error, title: s.title }));
        if (s.stage === "done") {
          const entry = {
            title: s.title || "Converted lecture",
            url: `${CONVERT_SERVER}/file/${convert.job}`,
            license: s.license,
          };
          setConverted((list) => {
            const next = [...list.filter((x) => x.url !== entry.url), entry];
            localStorage.setItem("litelec.converted", JSON.stringify(next));
            return next;
          });
        }
      } catch {
        /* server briefly unreachable; keep polling */
      }
    }, 2000);
    return () => clearInterval(t);
  }, [convert?.job, convert?.stage]);

  function saveConverted(next) {
    setConverted(next);
    localStorage.setItem("litelec.converted", JSON.stringify(next));
  }

  async function removeConverted(url) {
    if (!window.confirm("Remove this converted lecture? This deletes its file."))
      return;
    // deletion must reach the server's jobs folder, or the card would be
    // rediscovered from disk on the next refresh
    try {
      const id = url.split("/").pop();
      const r = await fetch(`${CONVERT_SERVER}/job/${id}`, { method: "DELETE" });
      if (!r.ok && r.status !== 404) {
        const s = await r.json().catch(() => ({}));
        return window.alert(s.error || "delete failed");
      }
    } catch {
      return window.alert(
        "Couldn't reach the conversion server — start it (python server.py) " +
          "to remove converted lectures permanently."
      );
    }
    saveConverted(converted.filter((x) => x.url !== url));
  }

  function renameConverted(url) {
    const cur = converted.find((x) => x.url === url);
    const name = window.prompt("New title:", cur ? cur.title : "");
    if (!name || !name.trim()) return;
    saveConverted(
      converted.map((x) => (x.url === url ? { ...x, title: name.trim() } : x))
    );
  }

  async function renamePublished(file) {
    const cur = published.find((p) => p.file === file);
    const title = window.prompt("New title:", cur ? cur.title : "");
    if (!title || !title.trim()) return;
    const id = file.split("/").pop().replace(".litelec", "");
    try {
      const r = await fetch(`${CONVERT_SERVER}/publish_rename/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() }),
      });
      const s = await r.json();
      if (!r.ok) return window.alert(s.error || "rename failed");
      setPublished((cur) =>
        cur.map((p) => (p.file === file ? { ...p, title: s.title } : p))
      );
      window.alert("Renamed. Commit and push to update the public site.");
    } catch {
      window.alert("Couldn't reach the conversion server.");
    }
  }

  async function unpublish(file) {
    if (!window.confirm("Unpublish this lecture? It will be removed from the site after your next push."))
      return;
    const id = file.split("/").pop().replace(".litelec", "");
    try {
      const r = await fetch(`${CONVERT_SERVER}/unpublish/${id}`, {
        method: "POST",
      });
      if (!r.ok) {
        const s = await r.json().catch(() => ({}));
        return window.alert(s.error || "unpublish failed");
      }
      setPublished((cur) => cur.filter((p) => p.file !== file));
      window.alert("Unpublished. Commit and push to update the public site.");
    } catch {
      window.alert("Couldn't reach the conversion server.");
    }
  }

  async function publishConverted(url) {
    const id = url.split("/").pop();
    try {
      const r = await fetch(`${CONVERT_SERVER}/publish/${id}`, {
        method: "POST",
      });
      const s = await r.json();
      if (!r.ok) return window.alert(s.error || "publish failed");
      setPublished((cur) => [
        ...cur.filter((p) => p.file !== s.file),
        { file: s.file, title: s.title },
      ]);
      window.alert(
        `Published “${s.title}”.\n\nIt is now part of the web app. To put it ` +
          `on the public site, commit and push (Vercel redeploys automatically).`
      );
    } catch {
      window.alert("Couldn't reach the conversion server.");
    }
  }

  async function startConvert(e) {
    e.preventDefault();
    setConvert({ stage: "contacting server…", error: null });
    try {
      const r = await fetch(`${CONVERT_SERVER}/convert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: convertUrl,
          media_url: convertMediaUrl,
          title: convertTitle,
        }),
      });
      const s = await r.json();
      if (!r.ok) setConvert({ stage: "error", error: s.error });
      else setConvert({ job: s.job, stage: "queued", error: null });
    } catch {
      setConvert({
        stage: "error",
        error:
          "Couldn't reach the conversion server. Start it on this computer with: python server.py",
      });
    }
  }
  const [state, setState] = useState({ status: "loading" });
  const [lineIndex, setLineIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voiceURI, setVoiceURI] = useState("");
  const [rate, setRate] = useState(0.95);
  const [access, setAccess] = useState(false); // AccessLearn: high-contrast + large + spoken math
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  const playingRef = useRef(false);
  const genRef = useRef(0);
  const voiceRef = useRef(null);
  const rateRef = useRef(0.95);

  // Load the selected .litelec; re-runs (and resets playback) when the demo changes
  useEffect(() => {
    genRef.current++;
    playingRef.current = false;
    setPlaying(false);
    setLineIndex(-1);
    setState({ status: "loading" });
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    fetch(demoUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${demoUrl}`);
        return res.text();
      })
      .then((text) => {
        const data = JSON.parse(text);
        const bytes = new Blob([text]).size; // real on-the-wire file size
        setState({ status: "ok", data, bytes });
      })
      .catch((err) => setState({ status: "error", message: err.message }));
  }, [demoUrl]);

  // Load installed voices (arrive asynchronously in Chrome)
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const load = () => {
      const vs = window.speechSynthesis
        .getVoices()
        .filter((v) => v.lang && v.lang.toLowerCase().startsWith("en"));
      setVoices(vs);
      setVoiceURI((prev) => {
        if (prev && vs.some((v) => v.voiceURI === prev)) return prev;
        return pickDefaultVoice(vs)?.voiceURI || "";
      });
    };
    load();
    window.speechSynthesis.onvoiceschanged = load;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  useEffect(() => {
    voiceRef.current = voices.find((v) => v.voiceURI === voiceURI) || null;
  }, [voiceURI, voices]);
  useEffect(() => {
    rateRef.current = rate;
  }, [rate]);

  useEffect(
    () => () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    []
  );

  // Track network status to show an online/offline badge (works offline via SW)
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const data = state.status === "ok" ? state.data : null;
  const duration = data?.source?.duration_s ?? 30;
  const sentences = useMemo(
    () => buildSentences(data?.transcript ?? []),
    [data]
  );

  function speakLine(i) {
    if (!sentences.length || i < 0 || i >= sentences.length) {
      setPlaying(false);
      playingRef.current = false;
      return;
    }
    setLineIndex(i);
    if (!("speechSynthesis" in window)) return;
    const myGen = genRef.current;
    const u = new SpeechSynthesisUtterance(sentences[i].text);
    if (voiceRef.current) u.voice = voiceRef.current;
    u.rate = rateRef.current;
    // Chrome's speech engine can die silently mid-utterance (esp. long text
    // with network voices) and never fire ANY event. Three layers of armor:
    // advance on error, a watchdog that estimates the utterance's maximum
    // plausible duration, and a pause/resume heartbeat (known Chrome fix).
    let advanced = false;
    const advance = () => {
      if (advanced) return;
      advanced = true;
      clearTimeout(watchdog);
      clearInterval(heartbeat);
      if (genRef.current !== myGen) return;
      if (!playingRef.current) return;
      speakLine(i + 1);
    };
    const words = sentences[i].text.split(/\s+/).length;
    const maxMs = Math.min(90000, (words * 600) / rateRef.current + 6000);
    const watchdog = setTimeout(() => {
      window.speechSynthesis.cancel(); // clear the wedged utterance
      advance();
    }, maxMs);
    const heartbeat = setInterval(() => {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }
    }, 10000);
    u.onend = advance;
    u.onerror = advance;
    window.speechSynthesis.speak(u);
  }

  function play() {
    if (!("speechSynthesis" in window)) return;
    genRef.current++;
    playingRef.current = true;
    setPlaying(true);
    window.speechSynthesis.cancel();
    const start = lineIndex < 0 || lineIndex >= sentences.length ? 0 : lineIndex;
    speakLine(start);
  }
  function pause() {
    genRef.current++;
    playingRef.current = false;
    setPlaying(false);
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }
  function reset() {
    genRef.current++;
    playingRef.current = false;
    setPlaying(false);
    setLineIndex(-1);
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }
  function scrub(e) {
    const t = Number(e.target.value);
    let idx = 0;
    for (let i = 0; i < sentences.length; i++) {
      if (sentences[i].t <= t) idx = i;
      else break;
    }
    genRef.current++;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (playingRef.current) speakLine(idx);
    else setLineIndex(idx);
  }

  const statusPill = (
    <span className={"netpill " + (online ? "on" : "off")} title="Network status">
      {online ? "● Online" : "● Offline — still works"}
    </span>
  );

  const demoPicker = (
    <div className="demobar">
      <button className="backbtn" onClick={goBrowse}>
        ← Browse Lectures
      </button>
    </div>
  );

  const siteHeader = (
    <header className="sitehead">
      <img src="/icon.svg" alt="LiteLecture logo" className="sitelogo" />
      <div className="wordmark">
        <strong>LiteLecture</strong>
        <span>send meaning, not pixels</span>
      </div>
      <div className="headright">{statusPill}</div>
    </header>
  );

  if (view === "browse")
    return (
      <main className="app browse">
        {siteHeader}
        <div className="stripe" />
        <h1 className="browsetitle">Browse Lectures</h1>
        <p className="browsecount">works offline</p>
        <div className="cardgrid">
          {DEMOS.map((d) => (
            <div key={d.url} className="cardwrap">
              <button
                className="lecturecard"
                onClick={() => openLecture(d.url)}
              >
                <div className="cover" style={{ background: d.color }}>
                  {d.cover.map((f, i) => (
                    <div className="coverline" key={i}>
                      <Formula latex={f} />
                    </div>
                  ))}
                </div>
                <div className="cardtitle">{d.title}</div>
                <div className="cardmeta">{d.source}</div>
                {sizeLine(d.url)}
              </button>
              <div className="cardactions">{origLink(d.url)}</div>
            </div>
          ))}
          {published
            .filter((d) => !converted.some((c) => c.url === d.file))
            .map((d) => (
              <div key={d.file} className="cardwrap">
                <button
                  className="lecturecard"
                  onClick={() => openLecture(d.file)}
                >
                  {coverArt(d.file, d.title)}
                  <div className="cardtitle">{d.title}</div>
                  <div className="cardmeta">Converted lecture · formulas pending review</div>
                  {sizeLine(d.file)}
                </button>
                <div className="cardactions">
                  {origLink(d.file)}
                  {serverUp && (
                    <>
                      <button onClick={() => renamePublished(d.file)}>rename</button>
                      <button onClick={() => unpublish(d.file)}>unpublish</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          {converted.map((d) => (
            <div key={d.url} className="cardwrap">
              <button
                className="lecturecard"
                onClick={() => openLecture(d.url)}
              >
                {coverArt(d.url, d.title)}
                <div className="cardtitle">{d.title}</div>
                <div className="cardmeta">Converted on this computer · formulas pending review</div>
                {sizeLine(d.url)}
              </button>
              <div className="cardactions">
                {origLink(d.url)}
                <button onClick={() => renameConverted(d.url)}>rename</button>
                <button onClick={() => removeConverted(d.url)}>remove</button>
                {serverUp && (
                  <button onClick={() => publishConverted(d.url)}>publish</button>
                )}
              </div>
            </div>
          ))}
        </div>

        {serverUp && (
        <section className="convertbox">
          <h2>Convert a lecture</h2>
          <p className="converthint">
            Paste a lecture link from a licensed source (Khan Academy, MIT
            OpenCourseWare). Conversion runs on this computer — start the local
            server first with <code>python server.py</code>.
          </p>
          <form onSubmit={startConvert} className="convertform">
            <div className="convertfields">
              <input
                type="text"
                placeholder="Title (optional — shown on the lecture card)"
                value={convertTitle}
                onChange={(e) => setConvertTitle(e.target.value)}
                maxLength={120}
              />
              <input
                type="url"
                required
                placeholder="Lecture page link — https://www.khanacademy.org/…"
                value={convertUrl}
                onChange={(e) => setConvertUrl(e.target.value)}
              />
              <input
                type="url"
                placeholder="Video link from that page's player (right-click the video → Copy video URL)"
                value={convertMediaUrl}
                onChange={(e) => setConvertMediaUrl(e.target.value)}
              />
            </div>
            <button type="submit" disabled={convert && convert.stage !== "error" && convert.stage !== "done"}>
              Convert
            </button>
          </form>
          {convert && convert.stage === "error" && (
            <div className="status error">{convert.error}</div>
          )}
          {convert && convert.stage !== "error" && convert.stage !== "done" && (
            <ol className="convertsteps">
              {CONVERT_STAGES.slice(0, -1).map((s) => {
                const cur = CONVERT_STAGES.indexOf(convert.stage);
                const idx = CONVERT_STAGES.indexOf(s);
                const cls = idx < cur ? "did" : idx === cur ? "doing" : "";
                return (
                  <li key={s} className={cls}>
                    {idx < cur ? "✓ " : idx === cur ? "… " : ""}
                    {s}
                  </li>
                );
              })}
            </ol>
          )}
          {convert && convert.stage === "done" && (
            <div className="status ok">
              Done — “{convert.title}” was added above. Its formulas are
              machine-extracted and marked for review.
            </div>
          )}
        </section>
        )}

        <section className="convertbox contactbox">
          <h2>Contact us</h2>
          <p className="converthint">
            Is there a lecture you'd like to see here? Tell us and we'll
            convert it (licensed sources only). This opens your email app —
            requests go to jolene.qian@gmail.com.
          </p>
          <form onSubmit={sendRequest} className="convertform">
            <div className="convertfields">
              <input
                type="url"
                required
                placeholder="Lecture page link — e.g. https://www.khanacademy.org/…"
                value={contactPage}
                onChange={(e) => setContactPage(e.target.value)}
              />
              <input
                type="url"
                required
                placeholder="Video link from that page's player (right-click the video → Copy video URL)"
                value={contactVideo}
                onChange={(e) => setContactVideo(e.target.value)}
              />
              <input
                type="text"
                placeholder="Your name (optional)"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                maxLength={80}
              />
            </div>
            <button type="submit">Send request</button>
          </form>
          <p className="contactnote">
            Every lecture is converted and reviewed by a person, so new
            requests can take a few days to appear — thanks for your patience!
          </p>
        </section>
      </main>
    );

  if (state.status === "loading")
    return (
      <main className="app">
        <h1>LiteLecture {statusPill}</h1>
        {demoPicker}
        <div className="status loading">Loading…</div>
      </main>
    );
  if (state.status === "error")
    return (
      <main className="app">
        <h1>LiteLecture {statusPill}</h1>
        {demoPicker}
        <div className="status error">Failed to load: {state.message}</div>
      </main>
    );

  const litelecBytes = state.bytes ?? 0;
  const originalBytes = data.source?.original_bytes ?? 0;
  const ratio = originalBytes > 0 && litelecBytes > 0
    ? Math.round(originalBytes / litelecBytes)
    : 0;
  // Per-section byte breakdown (compact JSON, so shares sum to ~100%)
  const sectionSizes = Object.entries(data)
    .map(([k, v]) => ({ k, bytes: new Blob([JSON.stringify(v)]).size }))
    .sort((a, b) => b.bytes - a.bytes);
  const compactTotal =
    sectionSizes.reduce((sum, x) => sum + x.bytes, 0) || 1;
  const wordCount = (data.transcript ?? []).reduce(
    (sum, c) => sum + (c.text || "").split(/\s+/).filter(Boolean).length,
    0
  );
  const bytesPerWord = wordCount ? Math.round(litelecBytes / wordCount) : 0;
  const currentChunk = lineIndex >= 0 ? sentences[lineIndex] : null;
  const time = currentChunk ? currentChunk.t : 0;
  const segStart = currentChunk ? currentChunk.t : 0;
  const segEnd =
    lineIndex >= 0 && lineIndex + 1 < sentences.length
      ? sentences[lineIndex + 1].t
      : duration;
  const emphasis = data.emphasis ?? [];
  const mathSpeech = data.accessibility?.math_speech ?? [];
  const speechFor = (sym) => {
    const m = mathSpeech.find((m) => Math.abs(m.t - sym.t) < 0.01);
    if (m) return m.text; // hand-written description preferred
    if (sym.kind === "latex") return latexToSpeech(sym.data); // auto fallback
    if (sym.alt) return sym.alt; // manipulatives carry a plain-English alt
    return null;
  };
  let activeSymbols = currentChunk
    ? data.symbols
        .map((s, idx) => ({ s, idx }))
        .filter(({ s }) => s.t < segEnd && s.t + (s.duration_s ?? 4) > segStart)
    : [];
  // Don't leave the whiteboard blank between formulas: if nothing is in its
  // authored window but a formula has already been written, keep the most recent
  // one on screen (like a real board where writing stays up).
  if (currentChunk && activeSymbols.length === 0) {
    let recent = null;
    data.symbols.forEach((s, idx) => {
      if (s.t <= segStart) recent = { s, idx };
    });
    if (recent) activeSymbols = [recent];
  }
  const emphStyleFor = (idx) => {
    const e = emphasis.find(
      (e) =>
        e.target === idx &&
        e.t < segEnd &&
        e.t + (e.duration_s ?? 4) > segStart
    );
    return e ? e.style : null;
  };

  return (
    <main className={"app" + (access ? " access" : "")}>
      <h1>LiteLecture {statusPill}</h1>
      {demoPicker}
      <p className="subtitle">{data.source?.title}</p>

      <div className="whiteboard">
        {activeSymbols.some(
          ({ s }) => s.verify && s.verify.status === "flagged"
        ) && (
          <div className="unverified-corner">
            ⚠ machine-read, not yet verified
          </div>
        )}
        {activeSymbols.length === 0 ? (
          <span className="placeholder">
            {playing ? "…" : "Press play to begin"}
          </span>
        ) : (
          activeSymbols.map(({ s, idx }) => {
            const emph = emphStyleFor(idx);
            const spoken = speechFor(s);
            // spec v0.2: machine-extracted symbols are "flagged" until a
            // human or cross-check verifies them — show them honestly
            const unverified = s.verify && s.verify.status === "flagged";
            return (
              <div
                className={
                  "formula-row" +
                  (emph ? " emph emph-" + emph : "") +
                  (unverified ? " unverified" : "")
                }
                key={idx}
              >
                {s.kind === "tokens" ? (
                  <Tokens spec={s} />
                ) : (
                  <Formula latex={s.data} />
                )}
                {access && spoken && (
                  <p className="mathspeech" aria-live="polite">
                    {spoken}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="caption" aria-live="polite">
        {currentChunk ? currentChunk.text : " "}
      </div>

      <div className="controls">
        {playing ? (
          <button onClick={pause}>⏸ Pause</button>
        ) : (
          <button onClick={play}>▶ Play</button>
        )}
        <button onClick={reset}>↺ Restart</button>
        <button
          className={"access-toggle" + (access ? " on" : "")}
          onClick={() => setAccess((a) => !a)}
          aria-pressed={access}
        >
          ♿ AccessLearn {access ? "on" : "off"}
        </button>
        <span className="clock">
          {fmt(time)} / {fmt(duration)}
        </span>
      </div>

      <input
        className="scrubber"
        type="range"
        min="0"
        max={duration}
        step="0.1"
        value={time}
        onChange={scrub}
        aria-label="Seek through the lecture"
      />

      <div className="voicebar">
        <label>
          Voice:{" "}
          <select value={voiceURI} onChange={(e) => setVoiceURI(e.target.value)}>
            {voices.length === 0 && <option>(loading voices…)</option>}
            {voices.map((v) => (
              <option key={v.voiceURI} value={v.voiceURI}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
        <label className="speed">
          Speed {rate.toFixed(2)}×
          <input
            type="range"
            min="0.6"
            max="1.2"
            step="0.05"
            value={rate}
            onChange={(e) => setRate(Number(e.target.value))}
          />
        </label>
      </div>

      <section className="sizecard">
        <h2>Why it's so small</h2>
        {ratio > 0 ? (
          <>
            <div className="sizerow">
              <span className="sizelabel">Original video</span>
              <div className="sizebar">
                <div className="bar bar-orig" />
              </div>
              <span className="sizeval">{fmtBytes(originalBytes)}</span>
            </div>
            <div className="sizerow">
              <span className="sizelabel">LiteLecture file</span>
              <div className="sizebar">
                <div
                  className="bar bar-lite"
                  style={{ width: Math.max(0.4, (litelecBytes / originalBytes) * 100) + "%" }}
                />
              </div>
              <span className="sizeval">{fmtBytes(litelecBytes)}</span>
            </div>
            <p className="sizebig">≈ {ratio.toLocaleString()}× smaller</p>
            <p className="sizesub">
              This {Math.round(duration / 60)}-minute lecture is a{" "}
              {fmtBytes(litelecBytes)} file instead of a {fmtBytes(originalBytes)}{" "}
              video — small enough to open on the slowest connection.
            </p>
          </>
        ) : (
          <p className="sizesub">
            LiteLecture file: <strong>{fmtBytes(litelecBytes)}</strong> for a{" "}
            {Math.round(duration / 60)}-minute lecture.{" "}
            <em>(Original video size pending — run the encoder with --measure.)</em>
          </p>
        )}

        <details className="breakdown">
          <summary>See where the bytes go</summary>
          <ul>
            {sectionSizes.map(({ k, bytes }) => (
              <li key={k}>
                <span className="bk-name">{k}</span>
                <span className="bk-bar">
                  <span
                    style={{ width: (bytes / compactTotal) * 100 + "%" }}
                  />
                </span>
                <span className="bk-val">
                  {fmtBytes(bytes)} · {Math.round((bytes / compactTotal) * 100)}%
                </span>
              </li>
            ))}
          </ul>
          <p className="bk-note">
            {wordCount.toLocaleString()} spoken words → about {bytesPerWord} bytes
            per word. The math, accessibility, and metadata are nearly free —
            LiteLecture's cost is essentially the words. (Shares are of the compact
            data; the saved file adds readable spacing, and gzip on the wire shrinks
            text roughly 70% more.)
          </p>
        </details>
      </section>

      <p className="hint">
        Switch lectures with the dropdown up top. The voice reads every line in
        full; caption, clock, and formulas all follow the spoken sentence.
      </p>
    </main>
  );
}
