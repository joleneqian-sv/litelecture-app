# LiteLecture — Size Breakdown (for the write-up)

Measured from the real demo files on 2026-06-15. Use these numbers in the CAC
write-up / science-fair board.

## Headline
- **Limits lecture:** 18.6 MB video → 31 KB file = **~614× smaller**
- **Percent lecture:** 4.1 MB video → 10.9 KB file = **~400× smaller**
- Both are TTS-only (no embedded audio). Honest framing: "~400–600× smaller,
  fully offline, synthetic narration."

## Where the bytes go — Limits demo (31 KB total)
| Section | Size | Share | What it is |
|---|---|---|---|
| transcript | ~22 KB | ~70% | 295 lines, ~2,056 spoken words |
| source | ~0.4 KB | ~1% | title, creator, URL, license, original size |
| accessibility | ~0.2 KB | ~1% | spoken-math descriptions |
| symbols | ~0.2 KB | ~1% | the 2 LaTeX formulas |
| scenes | ~0.1 KB | <1% | "whiteboard" |
| audio | ~0 | 0% | just {"mode":"tts_only"} — no audio data |
| format + version | few bytes | ~0% | |
| (formatting whitespace) | ~8 KB | rest | indentation from pretty-printing |

## Where the bytes go — Percent demo (10.9 KB total)
- transcript ~6.8 KB (~63%), 89 lines, 607 words
- source ~0.5 KB, symbols ~0.3 KB (3 formulas), accessibility ~0.3 KB,
  emphasis ~0.1 KB (the 9/50 circle), scenes ~0.1 KB.

## Key insight (the quotable line)
**LiteLecture's cost is essentially the words spoken — roughly 10–15 bytes per
spoken word.** The math, annotations, and accessibility features are nearly free.
A video pays for every pixel of every frame; LiteLecture only pays for meaning.

## Further compression (future / talking points)
- Minify (strip indentation): ~31 KB → ~23 KB.
- gzip on the wire (every real web server does this automatically): text compresses
  ~70% more, so the 31 KB file travels as ~7 KB.
- So a 12-minute lecture realistically moves ~7 KB over the network vs ~18.6 MB.

## In the app
An expandable "See where the bytes go" panel is in the size-comparison card,
computed live from whichever lecture is selected.
