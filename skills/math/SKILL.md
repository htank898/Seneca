---
name: math
description: Render math the way a machine should. Animated math explainers with Manim (3Blue1Brown-style, Typst equations) as MP4, GIF, or a transparent clip that drops into other Seneca videos, GIFs, and guides; LaTeX equations typeset into any Seneca HTML (guides, decks, PDFs, GIF pages) with KaTeX at build time; and real LaTeX documents compiled to PDF with Tectonic. Use for "animate this proof", "explain this formula visually", "math animation", "manim", "put the equation in the deck/guide/PDF", "typeset this math", "LaTeX", "write this up as a paper / problem set / derivation", or any content with formulas.
---

# AI Math: equations and math animation as code

Math is the one place where "draw it by hand" breaks first. This skill gives you three routes. Pick by what the math is *for*:

| The math is… | Route | Output |
|---|---|---|
| **the story**: a proof, a transformation, a quantity changing | **A. Manim animation** | MP4, GIF, or a transparent clip for another piece |
| **inside** a guide, deck, PDF, or GIF page | **B. KaTeX typesetting** | the same HTML, with math rendered and fonts inlined |
| **a document**: paper, derivation, problem set, handout | **C. LaTeX → PDF** | a real LaTeX PDF |

These combine. An explainer video can use a Manim clip in one scene and KaTeX labels in another. A one-pager (route B) can come with a full derivation (route C).

Paths below are relative to this skill's base directory. Write the user's files next to their project, not inside this skill.

## 1. Design pass
If the `frontend-design` skill is available, invoke it before writing a scene or page. If the piece belongs to an existing set (a deck, a video, a brand sheet), reuse its palette and type instead.

Math-specific rules:
- **One idea per beat.** Show one equation, then change one thing about it. Never put a wall of algebra on screen.
- **Color is meaning.** Give each quantity one color for the whole piece. Keep the signal color for the one thing to look at.
- **Equations move; they don't reappear.** When a term changes, transform it in place (`ReplacementTransform`, or `.select()` groups), so the viewer can track it.
- **Check the math.** Compute every number you show (run it in Python), and check every identity before you animate it.

## 2A. Manim animation

1. Copy `templates/scene.py` next to the user's project and write the scene. `from seneca_scene import *` gives you all of Manim plus:
   - `SenecaScene`: the Seneca palette (`self.palette["ink"|"steel"|"signal"|"paper"|"mute"|"card"]`) and the house font.
   - `self.eq("…")`: Typst display math (`MathTypst`). Group terms with `{{ a^2 + b^2 : lhs }}` and pick them out with `eq.select("lhs")` to color, move, or transform them.
   - `self.typst("text with $x^2$")`: mixed text and math. `self.text("…")`: plain text.
   - `self.beat("scene-id", hold=2)`: hold until that narration scene leaves the screen (with `--timings`), or for `hold` seconds without it.
   - `self.cue("scene-id", "start")` and `self.wait_until(t)`: land a moment on a spoken line.
2. **Equations use Typst syntax, not LaTeX.** `frac(a, b)` or `a/b`, `sqrt(x)`, `sum_(k=0)^n`, `integral_a^b`, `x^2`, `alpha`, `->`, `RR`. See `reference/math-parameters.md` for a side-by-side cheatsheet.
3. The frame's short side is always 8 units, at any size. Lay out with `config.frame_width` and `config.frame_height` and `to_edge`, not fixed coordinates, so a scene works at 16:9, 1:1, and 9:16.
4. Render:
```bash
node scripts/render-math.mjs path/to/scene.py SceneName --size 1080x1080 --fps 30 --gif
```
Flags:
- `--out name.mp4`
- `--quality l|m|h|k`: 480p15, 720p30, 1080p60 (the default), 4K60. `--size` and `--fps` override it.
- `--gif` also writes a GIF. GIF options: `--gif-fps 24 --scale 0.6 --colors 256 --dither sierra2_4a --budget-mb 5`.
- `--no-mp4`
- `--clip`: see below.
- `--timings voice/timings.json`
- `--keep-media`

**First run sets itself up.** It creates a Python 3.12 venv at `.venv/` inside this skill with `uv`, installs Manim and Typst, and smoke-tests an equation render.
- If `pycairo` fails to build, it prints `brew install cairo pkgconf`.
- `uv` and `ffmpeg` are required. No TeX install is needed.
- For anything else Manim can do: `python3 scripts/manim.py <manim args>`.

### Using a Manim clip inside other content
- **In an ai-video:** render with `--timings path/to/voice/timings.json`, using the same scene ids as `scenes.json`, so each `beat()` ends where its narration does. Then either:
  - use the MP4 as a whole scene, or
  - composite it into the video's animation as a clip (below).
- **As a clip in any `renderFrame(t)` page** (ai-gif, ai-video, interactive guides): add `--clip`. It writes a transparent PNG sequence to `name.clip/`, plus `clip.json`, `clip.js`, and `clip-player.js`. In the page:
  ```html
  <canvas id="proof"></canvas>
  <script src="proof.clip/clip.js"></script>
  <script src="proof.clip/clip-player.js"></script>
  <script>
    const proof = SenecaClip.mount("proof", document.getElementById("proof"));
    // in renderFrame(t):  proof.draw(seconds)  (ai-gif: t * MOTION.seconds; ai-video: t - s.from)
  </script>
  ```
  - `draw()` is deterministic and frames are preloaded before the page's load event, so the host's renderer works unchanged.
  - Render clips at the host's fps and roughly its on-screen size (`--fps 30 --size 720x720`) to keep memory and file size down. Pass `{ loop: true }` to `mount` to loop it.

## 2B. KaTeX in HTML
Write LaTeX math straight into the page source:
- inline: `$…$` or `\(…\)`
- display: `$$…$$` or `\[…\]`
- or wrap it: `<span class="tex">…</span>` (inline) and `<div class="tex">…</div>` (display)

Then typeset before rendering or delivering:
```bash
node scripts/typeset.mjs page.src.html --out page.html
```
- Keep the TeX in `page.src.html` and treat `page.html` as build output. The command is idempotent, so `--out page.html` on a single file also works.
- Prices are safe. `$5 to $10` is not math, because a closing `$` can't be followed by a digit. Write `\$` for a literal dollar sign in text near math.
- `<code>`, `<pre>`, `<script>`, `<style>`, and anything inside `class="no-math"` are left alone.
- A bad expression fails the run with its line number and KaTeX's message, and nothing is written. `--check` validates without writing.
- The output needs no JavaScript and no network. KaTeX's CSS is inlined with **only the fonts the page uses**, as base64 woff2: typically 5 of 20, about 80 KB.
- `--mathml` emits MathML only: no CSS, no fonts, the smallest output, and a plainer look.
- `--macros macros.json` sets shared shortcuts, e.g. `{ "\\R": "\\mathbb{R}" }`.
- Style it from the page's CSS: `.katex { font-size: 1.1em }`, `.katex-display { margin: … }`. Math inherits `color`.

Then render with the host skill as usual: ai-pdf `render-pdf.mjs`, ai-slide-deck `render-deck-pdf.mjs`, ai-gif `render-gif.mjs`, ai-interactive-guide `render-steps.mjs`.

## 2C. LaTeX → PDF
1. Copy `templates/article.tex`: Seneca palette, sans headings, `amsmath`/`mathtools`, theorem/definition/problem environments, `unicode-math`.
2. Write the document.
3. Build:
```bash
node scripts/latex-pdf.mjs path/to/doc.tex --preview
```
- It uses **Tectonic**, a single binary with no TeX Live install. Packages download the first time a document uses them, then come from cache.
- If Tectonic is missing, the script prints `brew install tectonic`.
- Errors are reported with file and line. `--keep-logs` keeps the `.log`. `--preview` writes a PNG of page 1.

## 3. Verify before reporting
- **Numbers:** recompute every figure on screen or on the page in Python, and say so.
- **Animation:**
  - Extract frames at each beat (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`) and look at them. Equations should be crisp, nothing clipped at the frame edge, and labels sitting on what they label.
  - Check that the last frame holds the conclusion.
  - With `--timings`, check that the MP4's duration equals `timings.json`'s `duration`.
- **Clip:** `clip.json`'s `duration` matches the MP4's, and the frame corners are transparent. Render the host page with `--keep-frames` and look at the frames where the clip appears.
- **KaTeX:**
  - Render the host format and look at it (ai-pdf `--preview`, a deck PNG, or GIF frames).
  - Confirm there are no `src=`/`href=`/`url(` references to external files. `[math] inlined N/20 KaTeX fonts` should be small.
- **LaTeX:** read the `--preview` PNG. No overfull lines in the margins, no `??` references.
- Report each output's path, size, duration or page count, and dimensions.

See `reference/math-parameters.md` for quality presets, a Typst ↔ LaTeX cheatsheet, timing guidance, and licenses.
