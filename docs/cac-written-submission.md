# LiteLecture — Congressional App Challenge 2026 Written Submission

*Draft v2 · ~465 words (CAC limit is typically 250–500). Personal hook now written in your own words.*

---

In rural America, about 24% of households still lack reliable broadband, and on tribal
lands the gap is worse. A single 12-minute lecture video runs roughly 18 MB — effectively
unwatchable on a capped data plan or a slow connection. And students who are blind can't use
educational videos at all: a screen reader can't read an equation that exists only as pixels
on a screen. One problem locks kids out by bandwidth; the other locks them out by sight.

The day before a big test, I was stuck in a car far from home with almost no signal, trying
to pull up the one lecture I needed to review. It just wouldn't load. The information I needed
was sitting right there on the internet, and a couple of missing bars of signal put it
completely out of reach. That was the moment I understood how fragile "just watch the video"
really is — and I started building LiteLecture so that needing a lesson never again means
needing a fast connection.

LiteLecture solves both with one app, by sending a lecture's *meaning* instead of its pixels.
An encoder extracts what actually teaches — the spoken transcript, every equation as real
LaTeX symbols, and the structure of what the instructor draws — and packs it into a tiny
`.litelec` file averaging about 50 KB per minute, often 400–600× smaller than the video.
A web app then replays that file: captions sync to the moment each line is spoken, equations
are typeset live, and the browser narrates the lesson aloud. Because each lecture is the size
of a text message, a student can download a whole week of lessons once — at school, a library,
or over a shared phone — then study entirely offline afterward, on any device, with no
connection at all. An "AccessLearn" mode speaks every formula in plain words, adjusts font
size and contrast, and works with screen readers — so the same design that beats the bandwidth
gap also makes math audible for blind learners.

Under the hood, the encoder uses OpenAI's Whisper to transcribe speech and optical character
recognition to pull equations off the screen, writing a structured file checked against an
open spec. The player is a React Progressive Web App: KaTeX renders the math, the Web Speech
API narrates, and a service worker caches everything so it runs with the network switched off.
Storing formulas as symbols rather than images keeps them exact and machine-readable —
something no video, at any bitrate, can offer. Measured result: an 18.6 MB Khan Academy
lecture becomes a 31 KB file that plays fully offline.

Next is a teacher tool — paste a lesson link, get a tiny file for your class. The hard part of
opening it to any video isn't the code; it's guaranteeing the math is correct and the source is
licensed. That's exactly what I'd build next.

---

## Notes for you (not part of the submission)

- **Word count:** ~465 words — under the typical 500 limit, but not by much. If your form has
  a tighter cap, the "Under the hood" paragraph is the safest to trim.
- **Every number here is real and measured** (18.6 MB → 31 KB, ~400–600×, offline) — taken
  from your own `size-breakdown.md`. Don't let anyone round these *up* into "thousands of times";
  the honest framing is your strength.
- **Your hook is in your own words** — read it aloud once and tweak anything that doesn't sound
  like you. It's the most memorable part of the submission, so it should feel true, not polished.
- **One thing to verify before submitting:** confirm the live Vercel URL works and all three
  demos play — the writeup implies a working app a judge can open.
