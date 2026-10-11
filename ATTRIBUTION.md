# Attribution & Credits

LiteLecture's own code is released under the MIT License (see [LICENSE](./LICENSE)). The demo
lectures and the open-source tools it relies on belong to their respective creators and are
credited below.

## Demo lecture content

The pre-encoded `.litelec` files in `web/public/demos/` are **derivatives of Khan Academy
videos**, used under the **Creative Commons Attribution-NonCommercial-ShareAlike 3.0** license
(CC BY-NC-SA 3.0). Each file carries its own `source` and `license` metadata. LiteLecture stores
only the transcript and verified formulas — not the original video or audio.

| Demo | Source lecture | Creator | License | Source URL |
|---|---|---|---|---|
| `limits-intro.litelec` | Introduction to Limits | Khan Academy | CC BY-NC-SA 3.0 | https://www.youtube.com/watch?v=riXcZT2ICjA |
| `algebra.litelec` | Converting Percent to Decimal and Fraction (Pre-Algebra) | Khan Academy | CC BY-NC-SA 3.0 | https://www.youtube.com/watch?v=-gB1y-PMWfs |
| `demo3.litelec` | Solving a More Complicated Equation (Algebra I) | Khan Academy | CC BY-NC-SA 3.0 | https://www.youtube.com/watch?v=XoEn1LfVoTo |

Khan Academy content is © Khan Academy and licensed CC BY-NC-SA 3.0. LiteLecture is a
non-commercial educational research project. In keeping with ShareAlike, these derived
`.litelec` files are offered under the same CC BY-NC-SA 3.0 license. LiteLecture is not
affiliated with or endorsed by Khan Academy.

## Open-source tools

### Encoder (Python)

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech transcription (MIT)
- [Pix2Text](https://github.com/breezedeus/Pix2Text) — math/text OCR (MIT)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video acquisition (Unlicense)
- [FFmpeg](https://ffmpeg.org) — audio/frame extraction (LGPL/GPL)
- OpenAI [Whisper](https://github.com/openai/whisper) model weights (MIT)

### Player (web)

- [React](https://react.dev) (MIT) and [Vite](https://vitejs.dev) (MIT)
- [KaTeX](https://katex.org) — LaTeX math rendering (MIT)
- Web Speech API — browser-native text-to-speech (no dependency)

## Hosting

- Deployed on [Vercel](https://vercel.com) (free tier).

## License layering (project policy)

- **Tool / app code** → MIT
- **Derived demo content** → CC BY-NC-SA 3.0 (inherited from the source videos)
- **`.litelec` file-format specification** → intended for the public domain (CC0)

---

*If you believe any attribution here is incomplete or incorrect, please open an issue on the
repository so it can be fixed.*
