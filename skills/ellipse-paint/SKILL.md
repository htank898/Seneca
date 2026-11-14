---
name: ellipse-paint
description: Paint images from vector shapes. A Python engine rebuilds any source image (a Gemini/Nano Banana concept, a photo, a sketch) either soft, as layered translucent ellipses blocked in like a painter (shape count is the style dial: bold ~300, painterly ~1500, near-photographic 2500+), or hard-edged, posterized to a few flat colours and traced into razor-sharp paths (screen-print / risograph look, optional palette recolour). It also generates seeded procedural art from scratch: soft ellipse styles (mandala bloom, flow field, op-art orbits, terrazzo pebbles) and crisp geometric styles (Bauhaus tile grids, Truchet curves, circle packing, topographic contours and terraced bands, the last three optionally driven by a source image). The result is vector, so it renders sharply at any size, and it can cut the subject out of a plain background. Outputs SVG/PNG, a build-up timelapse MP4 of the painting forming, and 300 DPI print-ready sets (posters in every standard ratio, transparent tee PNGs, mug wraps, die-cut stickers) for print-on-demand and Etsy. Use for "ellipse art", "turn this image into ellipses/shapes", "vectorize / posterize / screen-print look", "Bauhaus / mid-century geometric print", "topographic / contour line art", "circle packing", "geometric/primitive-style painting", "generative art", "paint this from shapes", "Nano Banana / Gemini concept then stylise it", "poster / wall art / t-shirt / mug / sticker design", "print on demand", "Printify / Printful files". Use graphic for designed layouts with type, not paintings.
---

# ellipse-paint: images painted from layered ellipses

The process: start from a source (a Gemini concept, a photo, a sketch, or nothing), then paint it back up from ellipses. Each shape is placed where the canvas differs most from the source, big masses first and fine detail last, so the result reads as a deliberate, recognisable style rather than a filtered photo. Because the painting is a list of vector shapes, it renders at any size: a social image, a listing timelapse, or a 24x36 in. print at 300 DPI with no upscaler. Print-on-demand export is one destination among several.

Paths below are relative to this skill's base directory. Requires `uv`, Node, and ffmpeg (timelapse only). The first Python run builds `.venv/` here with numpy, Pillow, resvg, vtracer and contourpy (it reinstalls by itself when `requirements.txt` changes). `GEMINI_API_KEY` is needed only for the Gemini step. The client looks in the environment, then in the nearest `.env` up the tree (Seneca's root `.env`). Get a key at aistudio.google.com/apikey.

```
E="python3 scripts/ellipses.py"
X="python3 scripts/pod_export.py"
G="node ../adapt/scripts/gemini.mjs"     # shared Gemini client (Nano Banana), owned by adapt
```

## 1. Decide the product and the route
Ask only what you can't infer: **what it's for** (posters, tees, mugs, stickers, digital download, or `all`) and **the subject or theme**. Then pick a route:

| Route | When | Steps |
|---|---|---|
| **Concept → ellipses** (soft) | A subject (an animal, a place, a character, a still life), painterly look | Gemini concept → `fit` → export |
| **Concept → trace** (sharp) | Same subjects, flat screen-print look; **the best fit for tees and stickers** (opaque, few colours, crisp edges) | Gemini concept → `trace` → export |
| **Image → ellipses / trace** | They have a photo, sketch, or their own art | `fit` or `trace` → export |
| **Pure generative** | Abstract or pattern art, wall-art sets, quick collections | `generate` (geometric styles for sharp, ellipse styles for soft) → export |
| **Image-driven generative** | A subject rendered as packed circles or contour lines | `generate --style packing|contours --source img --knockout auto` |
| **Gemini direct** | Rarely: when the look must stay photographic | Gemini at 4K → `fit --shapes 6000 --work 400` keeps detail and still gives you vector |

## 2. Concept art with Gemini (concept routes)
```bash
$G image --prompt "<recipe from reference/prompting.md>" --aspect 2:3 --size 4K --out work/concept.png --n 3
```
- Use `--aspect 2:3` for wall art (it crops the least across the poster set) and `1:1` for tees and stickers.
- Generate 3 and pick one, or pass the best back with `--ref work/concept-2.png` and a change request.
- For anything that goes on apparel or stickers, prompt for **one subject on a flat, solid, light background with no shadow, text, or frame**. That lets `--knockout auto` cut it out cleanly.
- Every call is logged to `work/log.json` (prompt, refs, model), which is your provenance record for the listing.
- Read `reference/prompting.md` before prompting. It covers the IP rules: no brands, characters, celebrities, or living artists' names.

## 3. Build the art
**Fit** (soft, painterly; any target image):
```bash
$E fit work/concept.png --out work/art --shapes 2000            # full-bleed art: posters, mugs
$E fit work/concept.png --out work/art --shapes 2000 --knockout auto   # cut-out subject: tees, stickers
```
- Shape count is the style dial: **150–400** is bold, abstract, modern; **800–1500** is painterly; **2500+** is near-photographic. Make two strengths and show both.
- `--alpha 0.5` is the default. `0.8` gives flatter, poster-like blocks, and `0.3` gives soft, watercolour layering.
- `--work 200` is the scoring canvas. Raise it to 300–400 for fine detail; it's slower (1500 shapes at 220 takes about 40 s).
- `--knockout auto` reads the background colour from the corners. Only background connected to the border is removed, so white eyes and highlights survive. Use `--tol` to tighten or loosen it, and `--knockout #ffffff` to name the colour. A source PNG with real transparency is used as-is.

**Trace** (hard-edged flat colour; any target image):
```bash
$E trace work/concept.png --out work/flat --colors 6                       # the image's own colours
$E trace work/concept.png --out work/riso --colors 4 --palette riso --knockout auto   # recoloured cut-out
```
- `--colors` is the style dial: **3–4** is bold, poster/screen-print; **5–7** keeps faces and folds readable; **8+** gets busy.
- `--palette` recolours by tone: the darkest region gets the darkest palette colour, the lightest the lightest. This is how a collection gets one consistent house palette. Without it, the image's own cluster colours are kept.
- `--smooth` (default 5) simplifies region shapes; raise to 7–9 for chunkier, rounder forms. `--speckle` drops tiny regions. `--work` (default 1600) is the tracing resolution.
- A cut-out is pure vector (no raster mask), so its outline is as sharp as everything else. It takes about 2 s.

**Generate** (no source):
```bash
$E generate --style bloom --palette terracotta --seed 7 --out work/bloom-7
$E palettes                                     # named palettes; or --palette "#bg,#c1,#c2,..."
```
- **Soft ellipse styles:**
  - `bloom`: radial mandala
  - `field`: ellipses flowing along a smooth field
  - `orbits`: op-art moiré from two families of stroked rings
  - `pebbles`: packed terrazzo
- **Hard-edged geometric styles** (opaque, crisp at any size):
  - `bauhaus`: a margined grid of tiles, each a quarter/half circle, triangle, bars or ring. `--count` = tiles across (4–7).
  - `truchet`: continuous curving lines from rotated arc tiles, in solid, tube or two-colour variants (picked by seed). `--count` = tiles across.
  - `packing`: non-overlapping solid circles. With `--source img --knockout auto`, circles fill the subject, coloured from it, small at edges and detail, big in flat areas. Add `--palette` to snap those colours to a palette.
  - `contours`: topographic lines with index contours every fifth line. With `--source`, lines follow the image's tones (dark = dense) inside a clean silhouette.
  - `topo`: the same landscape as terraced filled bands. `--source` works full-frame only; for a flat-colour cut-out, use `trace`.
- Change `--seed` for variations. A collection is one style and palette across 4–6 seeds, which sells better on Etsy than unrelated one-offs.
- `--transparent` drops the background (for tees). `--aspect` sets the canvas ratio (with `--source`, the image's ratio is used).

Each build writes `art.json` (the artwork itself), `art.svg`, and `preview.png`. **Read `preview.png` before exporting.**

## 4. Export print files
```bash
$X work/art/art.json --out print/ --preset all --name fox-bloom
$X --list                                       # every preset and set
```
- **Sets:**
  - `wall-art`: 5 JPGs covering 2:3, 3:4, 4:5, 11x14 and ISO, each under Etsy's 20 MB. That's the standard 5-file digital download, and also the provider uploads.
  - `apparel`: a transparent 4500x5400 PNG
  - `mug`: an 11oz wrap with the art on both sides of the handle
  - `stickers`: a die-cut sticker with a white outline
  - `all`: everything above
- Full-bleed art is cropped to fill each poster ratio (`--focus x,y` chooses what's kept). Cut-out art is never cropped; it floats on its backdrop. Use `--backdrop "#hex"` to change the field colour and `--wall-fit` to override.
- Apparel and stickers are transparent. Pass `--keep-background` to print the art as a rectangle instead.
- Every file gets 300 DPI metadata, and `export.json` lists sizes, MB and warnings.
- Specs and provider caveats are in `reference/pod-specs.md`. Check mug, hoodie and tote templates against the chosen provider before uploading.

## 5. Listing assets
- **Timelapse video** (Etsy listing videos are 5–15 s, with no sound):
  ```bash
  $E timelapse work/art/art.json --out print/listing.mp4 --seconds 10
  ```
- **Mockups and the listing hero image:** use the `graphic` skill. Put the poster JPG in a framed-room or flat-lay scene, and the tee PNG on a garment colour block, at 2000 px or more on the short side.
- **Copy:** a title with the subject, style and product (≤140 characters, front-loaded), 13 tags, and a description that states sizes, file count, that it's a digital download where it is, the production partner for physical items, and that the design was made with AI tools (see `reference/pod-specs.md`, Etsy rules).

## 6. Verify before reporting
- Open `preview.png` and every exported file at small size. Faces should read, and no stray background shapes should show outside a cut-out. For a trace, check that the face and hands survived the colour count; if not, add a colour or lower `--smooth`.
- **Cut-outs:**
  - Look at the tee PNG on both black and white.
  - A leftover floor shadow or halo means the knockout missed: re-prompt Gemini for a cleaner background, or lower `--tol`.
- **Act on every warning in `export.json`:**
  - near-black or near-white designs disappear on matching garments
  - a see-through body means using `--flatten-alpha` or a higher `--alpha`
  - files over 20 MB
- Report each file's path, pixel size, inch size and MB, and which provider templates still need checking. Delete `work/` scratch only if asked.

## What not to do
- Don't sell a plain Gemini output upscaled to poster size. It's soft at 300 DPI, and it isn't distinctive. Fit or trace it first.
- Don't put text in Gemini prompts. AI lettering is unreliable. If the design needs words, set real type over the art with the `graphic` skill.
- Don't use trademarked names, franchise characters, sports teams, celebrities, or "in the style of <living artist>". These are the main reason print-on-demand shops get taken down.
