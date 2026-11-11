---
name: ai-scale
description: Make big numbers and scale understandable with animated comparisons. Covers money stacked as $100 bills next to a person, scaling from $100K to $1T past buildings, mountains, and space; amounts converted to time ("$1 a second, how far back?") that walk back through history to the Ice Age or the dinosaurs; and exponential growth, like folding paper to the Moon. One scene file becomes a short-form MP4/GIF, an interactive explorer, or slide stills. The math and comparison captions are computed, not guessed. Use for "how big is a billion", "visualize this number", "put this in perspective", "show the scale of", "explain exponential growth", "compare these magnitudes", national debt, market caps, populations, distances, durations, and other math or physics intuition pieces.
---

# AI scale: big numbers you can feel

People can't feel "a trillion". They can feel a stack of bills that passes the Space Station, or a walk back in time that ends among mammoths. This skill turns a number into that experience. Real math picks a familiar ruler, a camera that zooms in powers of ten carries the viewer across scales, and a caption at every stop says "taller than X, short of Y".

It's built to be **cheap to reuse**. The calculator does the math and writes the captions, and a prewritten engine draws and animates. A new piece is usually one command plus light edits to a JSON file, not new animation code.

Paths below are relative to this skill's base directory.

## 1. Pick the concept and the ruler
Read `reference/patterns.md` and match the request to a pattern:

| The number is… | Pattern | Engine |
|---|---|---|
| An amount of money or stuff | Stack it in a physical unit next to a person, passing landmarks | `tower` |
| A height, distance, or depth | Compare against landmarks directly | `tower --heights` |
| An amount you can turn into time (dollars at $1/sec, seconds, heartbeats) | Walk back in time past historical eras | `timeline` |
| Doubling or compounding (folding, viral spread, interest, chessboard rice) | Each step doubles, with a pause each time it passes a landmark | `doubling` |
| Something else (probability, area, speed, ratios) | Pick the closest pattern in the reference, or build a custom scene with the same engine conventions | custom |

**Ask only when the ruler can't be inferred**, for example "stack it, or turn it into time?" when both fit. If the user gave several examples, build each one as its own scene.

## 2. Compute the scene
```bash
node scripts/scale.mjs preset money-tower --out scene.json          # $100K → $1T in $100 bills
node scripts/scale.mjs preset money-time  --out scene.json          # $1/sec back to the dinosaurs
node scripts/scale.mjs preset paper-moon  --out scene.json          # folds of paper to the Moon
node scripts/scale.mjs tower    --unit usd100 --amounts 1e6,1e9,1e12,3.6e13 --title "The US national debt in $100 bills" --out scene.json
node scripts/scale.mjs tower    --heights 0.3,8849,10935 --labels "A ruler,Everest,Mariana Trench depth" --out scene.json
node scripts/scale.mjs timeline --seconds 86400,3.15e7,3.15e9 --out scene.json
node scripts/scale.mjs doubling --start-m 0.001 --target "Mount Everest" --label "Day" --out scene.json
```
Units: `usd100`, `usd1`, `paper`, `penny`, `goldbar`. Landmarks, units, and historical events live in `data/references.json`. **Add a reference there** if the story needs one, rather than hardcoding it in a scene. Options: `--size 1080x1920` (vertical short-form; 1080x1350 is the default), `--title`, `--note`, `--now YYYY-MM-DD`, `--prefix`.

The command prints every stop's headline, subline, and auto-caption. **Read them**: they are the script of the piece. Then edit `scene.json` only where it needs a human touch:
- `title` (the question being answered), `steps[].caption` (punchier wording), `steps[].hold` / `move` (seconds)
- `theme` to restyle colors, for example `{ "accent": "#ff6b35" }`
- Timeline `pace`: `{ "first": 2.5, "growth": 1.45, "max": 9 }` sets the leg run times in seconds; `steps[].run` overrides one leg. Longer legs must take longer to watch, because that's how the viewer feels the difference. Total length grows with the number of stops (about 80 s for 8 legs), so cut stops for social rather than flattening the pace.
- Remove or add steps. Every step needs `h` (tower) or `seconds` (timeline), plus `headline`, `sub`, `caption`.

Don't invent numbers in captions. If you change a figure, recompute it with the script.

## 3. Build and preview
```bash
node scripts/build.mjs scene.json        # → scene.html: one self-contained file
```
Open it in a browser. It's an **interactive explorer**: it autoplays, ◀ ▶ (or the arrow keys, or a click) jump between stops, the slider scrubs, and space pauses. You can send this file as-is as the interactive version.

## 4. Render
- **Short-form video / GIF:** the page follows the `ai-gif` motion contract, so use its renderer:
  ```bash
  node ../ai-gif/scripts/render-gif.mjs scene.html --mp4 --mp4-loops 1 --fps 30     # full-size MP4 (+ GIF)
  node ../ai-gif/scripts/render-gif.mjs scene.html --scale 0.5 --fps 20 --colors 128  # lighter GIF for chat/README
  ```
  Use MP4 for LinkedIn, Reels, and Shorts. Pieces longer than about 15 s get big as GIFs.
- **Slides / docs:** `node scripts/render-steps.mjs scene.html [--scale 2]` writes `scene.step-N.png`, one per stop. Drop them into an `ai-slide-deck` deck, one stop per slide. You can also embed the HTML.
- **Interactive guide:** the built HTML is the explorer. For a fuller lesson, embed it in an `ai-interactive-guide` step.

## 5. Verify before reporting
- **Run the overlap check. It must pass:** `node scripts/check-overlaps.mjs scene.html --samples 900`. It steps through the whole animation and fails if any two visible labels or icons collide. If it fails, fix the scene (shorter captions or names, fewer steps, `theme`) or the engine. Don't ship around it.
- Render the stills and look at every stop. Check that captions are accurate and readable, that no landmark label collides with the stack or the title area, and that the person, the stack, and the landmark being compared are all visible.
- For video, sample a few transition frames (`ffmpeg -i out.mp4 -vf "select=eq(n\,N)" …`). Check that the counter counts, the camera zooms smoothly, and the loop resets cleanly.
- State the assumptions on screen (`note`): unit size, "1 year = 365.25 days", "heights approximate". Report the files, their length, and their size.
