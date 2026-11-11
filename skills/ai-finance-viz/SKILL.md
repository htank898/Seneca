---
name: ai-finance-viz
description: Turn stock and company financials into intuitive visual explanations, rendered as a looping GIF/MP4, an interactive HTML explorer, and PNG stills for slides. It covers valuation and fundamentals (P/E trailing and forward, earnings yield, PEG, P/S, P/B, EV/EBITDA, FCF yield, dividend yield, margins, growth, market cap) and side-by-side peer comparisons. Each metric gets a plain-language metaphor, such as P/E as years for $100 to pay you back, a company as a building whose floors are years of profit, or peers on a "price of growth" field. Use for "compare these stocks", "explain this P/E", "visualize NVDA vs AMD valuation", "make an investor-friendly chart of our multiples", or any numbers-heavy finance story for a non-specialist audience. It explains numbers and is not a source of them, so data comes from the user or from cited sources with a date.
---

# AI finance viz: make the multiple make sense

A table of multiples is a butler: accurate, and nobody remembers it. This skill turns each metric into a picture of what it *means*. P/E becomes how many years $100 takes to pay you back. Market cap and profit become a building and its rent. Margins become a $100 bill getting trimmed. A calculator does the math and writes the captions, and a prewritten engine draws it, so a new chart costs one small JSON file instead of hand-built SVG.

Paths below are relative to this skill's base directory.

## 1. Design pass
The look is fixed so charts from different sessions match: Archivo, the Seneca palette (bg `#e6eae8`, ink `#16191d`, muted `#5e7a94`, accent `#f5c518`, surface `#f3f5f4`, rule `#c3cbc7`), flat fills with ink outlines, figure numbers, patent-drawing labels. Brick red `#c4604b` is reserved for losses and never marks a ticker. Your design work is choosing **which figures tell the story** and in what order (see `reference/metaphors.md`). To restyle for a brand, set `"theme": {…}` in the scene JSON instead of editing the engine.

## 2. Gather only what's missing
- **Tickers**: 2–6. More than six stops being readable, so split into groups.
- **The question**: "is X expensive vs peers?" → payback, field, card. "Who actually makes money?" → margins, building. "What do I get paid?" → yields. "What would it cost to buy the whole thing?" → ev.
- **Numbers, with a date and a source for each.** Use what the user gives you. If they ask you to gather numbers, fetch them at build time from a filing (10-K/10-Q), the company's investor relations site, or a named data provider, and record the source and as-of date per ticker. **Never fill in numbers from memory.** If you can't source a number, leave it out (the calculator marks it n/a) or, for a demo, set `"sample": true` and label the data illustrative.
- **Audience and destination**: social post or Slack (1080×1350, the default), slides (`--size 1920x1080`), or a page to explore (the HTML).

## 3. Build
1. Write the input file next to the output, not inside this skill. Start from `templates/input-template.json` (or `.csv`). Field reference is in `reference/metaphors.md` → *Inputs*. Values can be numbers or short strings like `"3.4T"`, `"820M"`, or `"9%"`.
2. Run the calculator. It prints the metrics table, warns about anything undated or unsourced, and drops views the data can't support:
   ```bash
   node scripts/finance.mjs data.json --out out/peers [--views payback,building,yields,margins,field,ev,card] [--basis ttm|fwd] [--growth] [--size 1920x1080]
   ```
   This writes `out/peers.scene.json` (derived metrics, auto-captions, timing) and `out/peers.html` (self-contained: scene plus engine inlined, and Archivo from Google Fonts with a system-font fallback).
3. Read the printed table first. Sanity-check every multiple against the inputs (a P/E of 400 is usually a units mistake, like shares in millions vs billions).
4. To tune titles, captions, figure order, or timing (`build`, `hold` seconds per beat), edit the scene JSON and rebuild with `node scripts/finance.mjs build out/peers.scene.json`. Don't edit the engine for one chart.
5. **Layout rules.** The engine enforces these. Keep them when you edit a scene, and build them into anything you add to the engine:
   - **Nothing overlaps or clips**, in any frame or still: no text on text, no text on a bar, bubble, building or coin stack, and nothing cut off at the frame edge. When elements crowd, one fades out smoothly *before* they touch, or it moves to a fixed side lane. After drawing each frame, the engine's layout guard measures every label and named shape. Any label that would touch something already placed gets `fade = 1 − smooth(0, 0.12, overlap ratio)`. Its box is padded by 1.4% of the 1080-px type unit against other labels and 0.4% against shapes, and the ratio is measured against the smaller box. The fade is a safety net, not the layout: at a figure's built state, nothing should be faded. Lines that read together (title, caption, a ticker's label stack) are one `TB` block, and long names are shortened with `fit()` to their lane.
   - **Stable layout in motion:** each element's position, row, or lane is assigned once per scene, never recomputed every frame from its neighbors. Examples are the bubble label sides (`labelSides`, from final bubble sizes), the margin tick-number lanes, and legend spacing (measured from the real font). Something can grow or move along its own path, like a roof rising, but its label rides with it. Labels never hop around to dodge each other.
   - **Honest scale:** every magnitude comparison is drawn on one true linear scale in every frame. That means one scale per figure for buildings, bars, and EV in years of EBITDA, area ∝ value for bubbles, and no log axes. A value too big for the frame is cut at the edge with a zig-zag break, and its full value is printed. It is never drawn on a different scale.
   - Something meant to pass in front of the scene (a moving character, say) gets a box name starting with `actor:` so the check skips it.
6. Open the HTML to preview it. It autoplays. ←/→ or a click steps through figures, space pauses, and the scrubber seeks. Below the chart are the inputs, the derived metrics with formulas, a list of what's not meaningful and why, and the sources.

## 4. Render
```bash
node ../ai-gif/scripts/render-gif.mjs out/peers.html --scale 0.6 --mp4      # looping GIF + MP4 (ai-gif contract)
node scripts/render-stills.mjs out/peers.html --scale 2 [--only payback,card] # one fully built PNG per figure
```
For a GIF, build a shorter scene with 3–4 views (`--views payback,building,yields,field --fps 20`). Each figure runs about 7 s, and all seven make a 50 s loop. Rendering rotates the loop so frame 0 is figure 1, fully built, which gives a good preview thumbnail. The first run installs Playwright. GIFs need `ffmpeg`.

## 5. Verify before reporting
- **Run the overlap check. It must pass** (exit 0) for every page you ship, including each size you render:
  ```bash
  node scripts/check-overlaps.mjs out/peers.html      # ~600 frames + every figure's built state
  ```
  It reads `window.__boxes` (`{name, box:[x0,y0,x1,y1], op}` for every label and named shape, published each frame). It fails if any two boxes with op ≥ 0.3 intersect by more than 2 px, or if one runs past the frame edge. If it fails, fix the layout (a fixed lane, more room, `fit()`), not the check.
- Look at every PNG still, plus a few GIF frames (`--keep-frames`): one mid-build, frame 0, and the last frame. Check that no label collides with a bar or line, that negative values are drawn as losses (not as small positives), and that every n/m has a reason.
- **Check the honesty rules** in `reference/metaphors.md`: trailing vs forward is labeled, the as-of date and source are in the footer, sample data says so, there's no buy/sell language, and areas scale correctly.
- Delete `.frames/` when you're done. Report each file path, its size, which figures it contains, and any metric that was n/m and why.
