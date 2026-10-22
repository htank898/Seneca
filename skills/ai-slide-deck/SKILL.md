---
name: ai-slide-deck
description: Build presentation slide decks as a single self-contained HTML file (keyboard/click/swipe navigation, transitions, builds, speaker notes, overview grid), with a one-command PDF export. Use for any deck, slides, presentation, pitch, keynote, training, workshop, readout, QBR, status update, or "make me a PowerPoint", unless the user explicitly needs an editable .pptx file (then use a pptx skill).
---

# AI slide deck: presentations as code

PowerPoint is an interface built for a human with a mouse. Driving it from AI means fighting a file format. A browser is already a perfect presentation engine, so build the deck the way you're good at building things: HTML, CSS, and JavaScript. You get exact typography, real layouts, code-driven diagrams and charts, and animation, all in one file that opens anywhere and exports to PDF.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it before writing slides and commit to an aesthetic direction that fits the audience: palette, type pairing, and a recurring visual motif. If it isn't available, choose those deliberately yourself. Avoid the defaults that make decks look generated: centered bullets on white, blue-to-purple gradients, emoji as icons, a title on every slide in the same spot.

## 2. Gather only what's missing
Infer from the request and use `reference/deck-parameters.md` defaults. Ask only for what you can't infer and what would change the deck:
- **Mode**: pitch / proposal, training, status update, narrative keynote, data readout. This sets slide count, density, and structure.
- **Audience and setting**: presented live, sent async to read, or both. Async decks need more words on the slide; live decks need fewer, with the rest in speaker notes.
- **Form factor**: 16:9 is the default. 9:16 for mobile/social, 1:1 for LinkedIn carousels, 4:3 for legacy rooms.
- **Brand**: colors, fonts, logo, if any.
- **Content source**: notes, a doc, data, or a topic for you to write about.

## 3. Build
1. Copy `templates/deck-shell.html` to the output location (not inside this skill).
2. Set `data-width` / `data-height` on `#deck` for the form factor, and the default `data-transition`.
3. Restyle the **THEME** block (tokens plus layout archetypes) to the design direction. Add new layout classes as needed.
4. Write slides as `<section class="slide layout-…">`. Per slide, you can use:
   - `data-transition="fade|slide|zoom|rise|none"`
   - `data-build` on elements to reveal them one at a time (`data-build="dim"` shows them faded until revealed)
   - `<aside class="notes">` for speaker notes
5. Build visuals as code: inline SVG diagrams, CSS/SVG charts drawn from the real numbers, and code-native illustrations. Don't leave "image here" placeholders unless the user will supply photos.
6. Stay inside the safe area (`--pad`). Nothing may overflow a slide.

Engine keys: ←/→ or space to navigate, `F` fullscreen, `N` speaker notes, `O` overview, `Home`/`End`. Links like `deck.html#/5` open slide 5.

## 4. Render
```bash
node scripts/render-deck-pdf.mjs path/to/deck.html --png
```
This writes `deck.pdf` (one slide per page, at the deck's exact size, with all builds shown) and, with `--png`, `deck.slide-N.png` for QA. The first run installs Playwright into this skill folder.

## 5. Verify before reporting
- Look at every slide PNG. Check for overflow or clipping, text below the minimum size, unbalanced layouts, contrast, and repeated layouts more than two slides in a row.
- The PDF page count must equal the slide count (the script warns if it doesn't).
- Delete the QA PNGs unless the user wants thumbnails. Report the HTML path (the live deck) and the PDF path (for attaching or emailing).
