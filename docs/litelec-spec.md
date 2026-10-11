# `.litelec` File Format Specification — v0.2

**Status:** Draft
**Last updated:** 2026-07-03
**Author:** Chen
**License:** CC0 / public domain

**Changelog**
- v0.2 (2026-07-03): added optional `symbols[].verify` object (extraction provenance,
  confidence, and verification status). Additive and backward-compatible: v0.1 files
  remain valid.
- v0.1 (2026-05-25): initial draft.

---

## 1. Purpose

A `.litelec` file is a compact, JSON-based representation of an educational video lecture. It captures the lecture's *semantic content* (spoken words, formulas, code, scene layout, accessibility metadata) instead of its pixels, allowing playback through a LiteLecture Player at ~50 KB/minute instead of ~6 MB/minute (typical 1080p H.265).

The format is designed around three rules:

1. **Symbolic content is bit-exact.** Formulas, code, and any character-sensitive content are stored as source strings (LaTeX, raw code) and rendered deterministically at the receiver. No generative model ever touches them.
2. **Semantic content is approximate.** Scene descriptions, speaker pose, and background are stored as compact descriptors. The receiver may render them however it likes.
3. **Audio is optional.** A file with no audio is fully playable via receiver-side TTS reading the transcript.

---

## 2. File extension and MIME type

| Property | Value |
|---|---|
| Extension | `.litelec` |
| MIME type | `application/json` (no custom subtype for v0.1) |
| Encoding | UTF-8 |
| Content | A single JSON object conforming to the schema below |

A `.litelec` file is valid JSON. It may be minified or pretty-printed; whitespace is not significant.

---

## 3. Top-level schema

```jsonc
{
  "format": "litelec",          // REQUIRED — must be the string "litelec"
  "version": "0.1",             // REQUIRED — semver of this spec
  "source": { ... },            // REQUIRED — provenance
  "audio":  { ... } | null,     // OPTIONAL — original audio, or null for TTS-only
  "transcript":   [ ... ],      // REQUIRED — spoken words with timestamps
  "symbols":      [ ... ],      // REQUIRED — LaTeX/code, bit-exact
  "scenes":       [ ... ],      // REQUIRED — visual layout descriptors
  "accessibility": { ... }      // OPTIONAL — math-speech and alt-text
}
```

All times in this file are **seconds from the start of the lecture**, expressed as JSON numbers (floats allowed, e.g. `12.5`).

---

## 4. `source`

```jsonc
{
  "title":        "Khan Academy — Intro to Limits",
  "url":          "https://www.khanacademy.org/math/calculus/...",
  "creator":      "Khan Academy",
  "duration_s":   30.0,
  "license":      "CC BY-NC-SA 3.0",
  "license_url":  "https://creativecommons.org/licenses/by-nc-sa/3.0/",
  "modified":     true,
  "modification_note": "Compressed via LiteLecture v0.1; transcript and LaTeX extracted."
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | Human-readable title |
| `url` | string | yes | Canonical URL of the original lecture |
| `creator` | string | yes | Attribution-required by most CC licenses |
| `duration_s` | number | yes | Total duration in seconds |
| `license` | string | yes | SPDX or CC short identifier |
| `license_url` | string | recommended | URL of the license text |
| `modified` | boolean | yes | Must be `true` for any LiteLecture output |
| `modification_note` | string | recommended | Short description of what was changed |

---

## 5. `audio`

Two modes, signaled by `"mode"`:

```jsonc
// Mode A — original audio embedded as Opus 8kbps base64
{
  "mode": "opus_8kbps",
  "data": "<base64 string>"
}

// Mode B — no audio; receiver TTS reads the transcript
{
  "mode": "tts_only"
}

// Or:
"audio": null
```

`mode: "tts_only"` and `audio: null` are equivalent. The Player MUST be able to handle both.

---

## 6. `transcript`

Ordered array of utterance objects:

```jsonc
[
  { "t": 0.0, "text": "Let's look at a function.", "speaker": "S1" },
  { "t": 3.2, "text": "f of x equals x squared minus one over x minus one.", "speaker": "S1" }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `t` | number | yes | Start time in seconds |
| `text` | string | yes | The spoken text; should be readable as-is by TTS |
| `speaker` | string | no | Speaker tag (`S1`, `S2`, ...); default `S1` |

The array MUST be sorted by `t`. Utterance durations are implicit (until the next utterance, or until `duration_s` for the last one).

---

## 7. `symbols`

Ordered array of symbolic-content objects. These are rendered **deterministically** — never generatively.

```jsonc
[
  {
    "t":     3.5,
    "kind":  "latex",
    "data":  "f(x) = \\frac{x^2 - 1}{x - 1}",
    "bbox":  [0.2, 0.3, 0.6, 0.15],
    "duration_s": 5.0,
    "verify": {
      "source":     "ocr+asr",
      "confidence": 0.97,
      "status":     "verified"
    }
  },
  {
    "t":     20.0,
    "kind":  "code",
    "lang":  "python",
    "data":  "def f(x):\n    return (x**2 - 1) / (x - 1)",
    "bbox":  [0.1, 0.4, 0.8, 0.3],
    "duration_s": 6.0
  }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `t` | number | yes | When the symbol appears on screen |
| `kind` | enum | yes | `"latex"` \| `"code"` \| `"text"` |
| `data` | string | yes | Source string — bit-exact |
| `lang` | string | only for `code` | Language identifier (e.g. `"python"`, `"c"`, `"javascript"`) |
| `bbox` | array of 4 numbers | no | Bounding box in **normalized coordinates** `[x, y, w, h]`, each in `[0, 1]`; origin is top-left |
| `duration_s` | number | no | How long the symbol stays on screen; defaults to "until the next symbol" |
| `verify` | object | no | Extraction provenance and verification status (v0.2, see below) |

LaTeX strings MUST escape backslashes in JSON (`\\frac`, not `\frac`).

### 7.1 `verify` (v0.2, optional)

Because symbolic content is only guaranteed correct *given a correct symbolic stream*,
each symbol may carry a record of how it was obtained and whether it was verified:

```jsonc
"verify": {
  "source":     "manual",     // "ocr" | "ocr+asr" | "manual"
  "confidence": 1.0,          // number in [0, 1], or null if not scored
  "status":     "verified"    // "verified" | "corrected" | "flagged"
}
```

| Field | Type | Notes |
|---|---|---|
| `source` | enum | `"ocr"` = machine-extracted only; `"ocr+asr"` = cross-checked against spoken math; `"manual"` = human-supplied or human-approved |
| `confidence` | number \| null | ASR–OCR agreement score in `[0, 1]`; `null` when no verification was run |
| `status` | enum | `"verified"` = agreement above threshold or human-approved; `"corrected"` = repaired by propose-and-verify and re-verified; `"flagged"` = unverified or disagreement; needs human review |

Rules:

1. `verify` is OPTIONAL; a symbol without it is treated as `status: "flagged"` provenance-unknown (v0.1 files therefore stay valid but unverified).
2. Encoders MUST NOT emit `status: "verified"` for machine-extracted symbols unless a verification check (cross-modal agreement or human approval) actually ran.
3. Players MAY visually mark `flagged` symbols (e.g., a subtle indicator) but MUST still render them deterministically from `data`.

---

## 8. `scenes`

Ordered array of scene descriptors. The Player uses these to choose a layout.

```jsonc
[
  { "t": 0,  "layout": "whiteboard", "background": "white" },
  { "t": 18, "layout": "split_slide_speaker", "speaker_position": "right" }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `t` | number | yes | When this scene starts |
| `layout` | enum | yes | `"whiteboard"` \| `"slide"` \| `"split_slide_speaker"` \| `"code_editor"` |
| `background` | string | no | CSS color or named theme |
| `speaker_position` | enum | no | `"left"` \| `"right"` \| `"center"` |

For v0.1 the Player MAY render all scenes as the `"whiteboard"` layout regardless of this field. Forward-compatible.

---

## 9. `accessibility`

Optional but strongly recommended.

```jsonc
{
  "math_speech": [
    { "t": 3.5, "text": "f of x equals the quantity x squared minus one, all over x minus one." }
  ],
  "alt_text": [
    { "t": 0, "text": "A diagram of a curve approaching the line y equals 2." }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `math_speech` | array | Natural-language speech for each `latex` symbol, aligned by `t`. Spoken by TTS in AccessLearn mode. |
| `alt_text` | array | Alt-text descriptions for any non-symbolic visual content. |

If `accessibility.math_speech` is absent, AccessLearn mode falls back to a built-in MathSpeak ruleset applied to the LaTeX string.

---

## 10. Size budget (informative)

For a 5-minute Khan Academy lecture:

| Section | Approximate size |
|---|---|
| `source` + `format` + `version` | ~0.4 KB |
| `transcript` (~700 words) | ~10 KB |
| `symbols` (~30 formulas) | ~5 KB |
| `scenes` (~5 transitions) | ~0.5 KB |
| `accessibility.math_speech` | ~5 KB |
| `audio` (`tts_only`) | 0 KB |
| **Total** | **~21 KB / 5 min ≈ 4 KB/min** |

With `audio.mode = "opus_8kbps"`:

| Section | Approximate size |
|---|---|
| All of the above | ~21 KB |
| Opus 8 kbps audio for 5 min | ~300 KB |
| **Total** | **~321 KB / 5 min ≈ 64 KB/min** |

Both are 50-1500× smaller than the source MP4.

---

## 11. Validation rules

A valid `.litelec` file MUST satisfy:

1. `format === "litelec"`
2. `version` is a valid semver string
3. `source.modified === true`
4. `transcript`, `symbols`, and `scenes` are arrays, each sorted by `t`
5. No timestamp is negative
6. No timestamp exceeds `source.duration_s`
7. Every `symbols[i]` with `kind === "code"` has a `lang` field
8. Every LaTeX `data` field parses with KaTeX in strict mode

The reference Player will refuse to load any file failing rules 1-6 and will display a warning for files failing rules 7-8.

---

## 12. Future versions

Backwards-incompatible changes (renaming fields, removing fields) will increment the major version. New optional fields will increment the minor version. The Player MUST refuse to load files with a major version higher than its own; MAY load files with a higher minor version, ignoring unknown fields.

---

## 13. Reference implementations

- **Encoder:** `litelecture-py` (TBD, Phase B)
- **Player:** `web/` in this repo (TBD, Phase A weeks 2-3)
- **Validator:** `tools/validate.py` (TBD)

---

## 9.5 `emphasis` (optional)

Captures instructor annotations — the moments a lecturer underlines, circles, or
highlights something to draw attention. LiteLecture stores the *intent* (which
element, when, what style), not the hand-drawn pixels, so the Player renders a
clean, deterministic annotation and AccessLearn mode can announce it aloud.

```jsonc
[
  { "t": 118.0, "target": 2, "style": "circle", "duration_s": 28.0 }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `t` | number | yes | When the annotation appears |
| `target` | number | yes | Index into the `symbols` array to annotate |
| `style` | enum | yes | `"circle"` \| `"box"` \| `"underline"` \| `"highlight"` |
| `duration_s` | number | no | How long it stays; defaults to a few seconds |

Auto-detecting these from video (stroke-difference / pointer tracking) is future
encoder work; for now they are authored or verified by hand.
