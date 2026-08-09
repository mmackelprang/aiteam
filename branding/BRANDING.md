# Foreman — brand guide

**Proposed display name:** Foreman
**Tagline:** *AI teams, human foreman.*

## Why this name

The harness runs per-project AI teams; the portfolio watches them; the human stays in charge.
**Foreman** names that arrangement in one word — the person on the floor who assigns work,
checks it, and answers for it. It covers both subtrees: the harness is the crew, the portfolio
is the foreman's clipboard.

**Alternates considered:** *Paperclip Crew* (ties to the orchestrator; scope too narrow),
*Overseer* (accurate, sinister), *Bench* (workshop feel, too vague).

## The mark

An org tree: one filled blue square (the human) above three open circles (the agents). The
hierarchy *is* the product — reviews flow up, work flows down. Open circles, filled square:
agents are interchangeable; the human is not.

## Palette

| Color | Hex | Role |
|---|---|---|
| Charcoal | `#23272E` | Background / primary brand color |
| Signal Blue | `#4C8DFF` | The foreman node, primary accent |
| Steel | `#8FA6C8` | Connectors, secondary strokes |
| White | `#E7EDF6` | Agent nodes, text on dark |

## Voice

Managerial and plain: "assigned", "reviewed", "signed off". Cost and status are always visible —
the brand promise is legibility, not magic.

## Files in this directory

| File | Use |
|---|---|
| `logo.svg` | Full lockup (mark + wordmark + tagline) for README headers and docs |
| `favicon.svg` | Square app mark, scales from 16px to full size |
| `favicon.ico` | Legacy multi-size favicon (16/32/48) for browsers that want `.ico` |
| `favicon-32.png` | 32px PNG favicon |
| `apple-touch-icon.png` | 180px iOS home-screen icon |
| `icon-512.png` | Large raster for app manifests, social cards, stores |

### Wiring the favicon into a web page

```html
<link rel="icon" href="/branding/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/branding/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/branding/apple-touch-icon.png">
```

### README header

```markdown
<p align="center"><img src="branding/logo.svg" alt="Foreman" width="520"></p>
```

## Typography

Wordmark: **Montserrat Bold** (falls back to Segoe UI / system sans). Body text: the platform
default sans. For code-adjacent surfaces, any monospace at hand — the brand doesn't pin one.

The logo's wordmark is live SVG text, so it renders with whatever sans is installed; if you want
it pixel-identical everywhere, convert the text to outlines in any SVG editor and re-save.

## Dark and light backgrounds

The tile carries its own background, so both `logo.svg` and `favicon.svg` work unchanged on
light or dark pages. The wordmark in `logo.svg` is dark ink — on a dark page, either rely on the
tile alone (use `favicon.svg`) or restyle the two `<text>` fills to `#F0F2F5`.

---
*Generated as a proposal — names, colors, and marks are suggestions to accept, tweak, or reject.*
