# Week 2 Progress — LiteLecture (CAC 2026)

**Week of:** Jun 1, 2026 (started early, May 28)
**Phase:** A (Foundation)
**Status:** React + Vite scaffold + data loader done. Vercel deploy pending (needs Chen's account).

---

## What got done

### React + Vite scaffold (`web/`)
- New app under `web/` — kept separate from the Python encoder at repo root.
- Files: `package.json`, `vite.config.js`, `index.html`, `src/main.jsx`, `src/App.jsx`, `src/index.css`.
- React 18 + Vite 5, `@vitejs/plugin-react`.

### Data loader (Week 2 milestone)
- `src/App.jsx` fetches `/demos/limits-intro-30s.litelec`, parses it, and dumps the full JSON on the page.
- Also shows a small summary header (format/version, transcript chunk count, symbol count) + a metadata table (title, creator, duration, license).
- Demo file copied to `web/public/demos/` so Vite bundles it into `dist/`.

### Verified in the sandbox
- `npm install` → 62 packages, clean.
- `npm run build` → compiles, `dist/` produced (~46 KB gzipped JS).
- Preview server: `/` returns 200; `/demos/limits-intro-30s.litelec` returns 200 and parses as valid JSON (8 transcript chunks, 3 symbols).

---

## Pending — pick up here

1. **Deploy to Vercel** (needs Chen's account — can't be done from here):
   - Option A (dashboard): import the GitHub repo at vercel.com, set **Root Directory = `web`**, framework auto-detects Vite. Deploy.
   - Option B (CLI): `npm i -g vercel`, then from `web/`: `vercel` (link/login), then `vercel --prod`.
   - Confirm the live URL works (will be a `*.vercel.app` subdomain).
2. **On your own machine:** `cd web && npm install` to regenerate `node_modules` (the Linux `node_modules` built in the sandbox couldn't be deleted from the Dropbox mount — safe to delete manually; it's gitignored).
3. **Commit Week 2:** `git add web/` then commit/push.

---

## Week 3 (Jun 8-14) — next per action plan

- Integrate KaTeX; render the `symbols` array at the right timestamps.
- Basic playback timeline (clock incrementing each second).
- Web Speech API reads the `transcript` aloud at the right times.
- Smoke test on Chrome, Safari, Android Chrome.

## Still carried over from Week 1

- Rebuild `public/demos/limits-intro-30s.litelec` from real Whisper output (current one was approximated from memory, not transcribed). Do before any external use.
