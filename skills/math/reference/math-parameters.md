# Math parameters

## Picking a route
- **Animate (Manim)** when the *change* is the point: a term moving, a shape rearranging, a limit closing in, a graph responding to a parameter. If a still image would say the same thing, don't animate.
- **Typeset (KaTeX)** when the math supports something else: a formula on a slide, a step in a guide, a box on a one-pager.
- **Document (LaTeX)** when the reader will study it: derivations longer than a screen, numbered equations they'll refer back to, problem sets, anything printed and annotated.

## Manim output presets
| Destination | `--size` | `--fps` | Extras |
|---|---|---|---|
| YouTube / deck video (16:9) | 1920x1080 | 30 or 60 | MP4 only |
| LinkedIn / X feed (1:1) | 1080x1080 | 30 | `--gif --scale 0.6` if a GIF is needed |
| Story / Shorts (9:16) | 1080x1920 | 30 | keep equations in the middle 60% |
| Slack / docs GIF | 800x450 | 24 | `--gif --gif-fps 20` |
| Clip in a gif-create / video-create page | the clip's on-screen size | the host's fps | `--clip --no-mp4` |
| Fast draft | any | — | `--quality l` (480p15) |

`--quality`: `l` 854×480 @15, `m` 1280×720 @30, `h` 1920×1080 @60 (the default), `k` 3840×2160 @60. `--size` and `--fps` override it. The short side of the frame is always 8 Manim units.

## Sizes that read
At 1080p:
- display equations: `size` 64–96 (`self.eq(..., size=88)`)
- labels and annotations: 30–40
- kickers: 24–28, bold, steel

Never go below 28 on a 1080-wide square. Keep at least 0.4 units clear of the frame edge (`to_edge(..., buff=0.4+)`).

## Timing
- **Write** an equation in 1–1.6 s. **Transform** in 0.8–1.4 s. **Indicate** in about 0.8 s.
- **Hold** each new idea for at least 1.2 s before the next animation. Viewers need time to read math.
- Without narration, a 3–5 beat explainer runs 8–15 s. GIFs should loop in 12 s or less.
- With narration (`--timings`), let `beat("id")` do the holding. Animate during the spoken line and settle before the cut. `cue("id", "start")` is when the line begins, `cue("id", "end")` is when it ends, and `"to"` is when the scene leaves the screen.

## Typst ↔ LaTeX cheatsheet
Manim equations use Typst. KaTeX and real LaTeX use LaTeX. Same math, different spelling:

| Meaning | Typst (Manim `self.eq`) | LaTeX (KaTeX, .tex) |
|---|---|---|
| fraction | `frac(a, b)` or `(a+b)/c` | `\frac{a}{b}` |
| root | `sqrt(x)`, `root(3, x)` | `\sqrt{x}`, `\sqrt[3]{x}` |
| sub/superscript | `x_i`, `x^2`, `x_(i j)` | `x_i`, `x^2`, `x_{ij}` |
| sum, product | `sum_(k=0)^n k`, `product_(i=1)^n` | `\sum_{k=0}^{n} k`, `\prod_{i=1}^{n}` |
| integral | `integral_a^b f(x) dif x` | `\int_a^b f(x)\,dx` |
| limit | `lim_(x -> 0) f(x)` | `\lim_{x \to 0} f(x)` |
| Greek | `alpha`, `beta`, `pi`, `theta` | `\alpha`, `\beta`, `\pi`, `\theta` |
| number sets | `RR`, `NN`, `ZZ`, `CC` | `\mathbb{R}` … |
| relations | `<=`, `!=`, `approx`, `in`, `subset.eq` | `\le`, `\ne`, `\approx`, `\in`, `\subseteq` |
| arrows | `->`, `=>`, `arrow.r.double` | `\to`, `\Rightarrow` |
| vector, matrix | `vec(x, y)`, `mat(1, 2; 3, 4)` | `\begin{pmatrix}…\end{pmatrix}` |
| accents | `hat(x)`, `overline(y)`, `tilde(z)`, `arrow(E)` | `\hat{x}`, `\overline{y}`, `\tilde{z}`, `\vec{E}` |
| abs, norm | `abs(x)`, `norm(v)` | `\lvert x \rvert`, `\lVert v \rVert` |
| cases | `cases(1 "if" x > 0, 0 "otherwise")` | `\begin{cases}…\end{cases}` |
| text in math | `"if"` (quoted) | `\text{if}` |
| styles | `bold(v)`, `cal(L)`, `upright(d)` | `\mathbf{v}`, `\mathcal{L}`, `\mathrm{d}` |
| partial, nabla | `partial f / partial x`, `nabla` | `\partial`, `\nabla` |
| binomial | `binom(n, k)` | `\binom{n}{k}` |
| operators | `times`, `dot`, `dots.c`, `infinity` | `\times`, `\cdot`, `\cdots`, `\infty` |
| custom operator | `op("argmax", limits: #true)_x` | `\operatorname*{argmax}_x` |

In Typst, single letters are variables and multi-letter words are symbols or functions (`pi`, `sin`). Write `a b` for a product of two variables, because `ab` reads as one symbol. Quote words: `"rate"`.

**Groups for animation:** `self.eq("{{ a^2 + b^2 : lhs }} = {{ c^2 }}")`, then `eq.select("lhs")` and `eq.select(0)`. Groups can nest. Use them to color a term, move it, or `ReplacementTransform` it into the next equation.

## KaTeX notes
- Delimiters: `$…$` and `\(…\)` for inline; `$$…$$` and `\[…\]` for display; `<span class="tex">` and `<div class="tex">`.
- `$` heuristics: an opening `$` can't be followed by a space, and a closing `$` can't be preceded by a space or followed by a digit. `\$` gives a literal dollar.
- Supported: most of `amsmath` in display math (`align`, `aligned`, `gather`, `cases`, `pmatrix`, `\tag`, `\boxed`, `\color{#hex}{…}`, `\text{}`). Not supported: `\label`/`\ref` cross-references across the page, TikZ, `\usepackage`. Anything heavier belongs in route C.
- Output size: about 25–90 KB of fonts plus 23 KB of CSS per page, inlined once. `--mathml` drops both.
- Decks: typeset the deck HTML before `render-deck-pdf.mjs`. Slides that are hidden on load still get typeset, because typesetting happens at build time and doesn't depend on visibility.

## LaTeX notes
- Tectonic runs XeTeX. `fontspec` and `unicode-math` work, and so does any installed system font: `\setmainfont{Helvetica Neue}`.
- The first build of a document downloads the packages it uses (one time, cached in `tectonic -X show user-cache-dir`). Later builds work offline.
- Tectonic reruns as needed to resolve references and the table of contents. There's no `latexmk` step.
- Keep one `.tex` per document, with images next to it. `latex-pdf.mjs` compiles from the file's own folder.

## Licenses
Everything this skill runs is open source and free to use commercially. None of it is copied into this repo; it's installed on the user's machine.

| Component | License | How it's used |
|---|---|---|
| Manim Community 0.22 | MIT | pip, into `.venv/` |
| ManimPango | MIT (bundled Pango/Cairo binaries: LGPL) | pip dependency |
| pycairo | LGPL-2.1 or MPL-1.1 | pip dependency, links system Cairo |
| PyAV / FFmpeg | BSD-3 / LGPL | pip dependency / system tool |
| Typst (pip `typst`) | Apache-2.0 | Manim's equation engine |
| KaTeX 0.19 (code and fonts) | MIT | npm, CSS and fonts inlined into outputs |
| Tectonic | MIT | system binary (`brew install tectonic`) |
| TeX Live packages fetched by Tectonic | LPPL and other free licenses | downloaded on demand |

KaTeX's CSS and fonts are embedded in typeset HTML. To meet the MIT notice requirement, the inlined `<style>` starts with KaTeX's copyright and license line.
