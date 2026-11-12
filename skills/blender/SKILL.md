---
name: blender
description: Build and render 3D scenes in Blender by writing Python (bpy) scripts that run headless, with no clicking around the Blender UI. Use for product shots, 3D hero images, logo or text renders, turntable spins, abstract 3D compositions, mockups of a physical object, 3D visuals for decks/PDFs/graphics, or any "make this in Blender", "render a 3D…", "model a…", "quick 3D scene". Also exports .blend (to open and tweak in Blender) and .glb (for the web).
---

# AI Blender: 3D scenes as code

Blender's UI is built for a person with a mouse and a 3-button shortcut vocabulary. Blender's Python API isn't. Write the whole scene as a script, run Blender with no window, look at the render, fix the script, and repeat. The script is the source of truth: exact, re-runnable, and easy to edit.

Paths below are relative to this skill's base directory. Requires Blender (found at `/Applications/Blender.app`, on PATH, or `$BLENDER`) and Node.

## 1. Design pass
Decide the shot before writing geometry, the way a product photographer would:
- **What it's for** sets the size: slide 1920×1080, square post 1080×1080, story 1080×1920, banner 2400×1000, transparent cut-out for compositing (`transparent=True`).
- **Mood** sets the backdrop and lights: a bright seamless studio (light backdrop, soft key) for products; dark and moody (dark backdrop, hard rim) for drama; a saturated color field for brand or social.
- **Palette:** 2–3 materials, not ten. One accent, one neutral, at most one metal or glass.
- **Camera:** 70–100 mm, slightly above and off-axis (around 30° around, 15° down) for objects; 35 mm for environments. Dead-on front views look like CAD.

Generic gray primitives under a default point light are the "humanoid robot" here. Avoid them.

## 2. Gather only what's missing
Infer what you can. Ask only when the answer changes the scene substantially: what the object is, if it's vague; whether a brand color must match exactly (then use `Standard` view transform; see reference); whether they want an editable `.blend`.

## 3. Write the scene
1. Copy `templates/scene.py` next to where the output should live (the user's project or the current folder, not inside this skill).
2. Edit it. Every scene follows the same shape:
   ```python
   import bkit as k
   k.reset()                                   # empty scene
   k.render_settings(res=(1920, 1080))         # EEVEE; transparent=True for cut-outs
   k.world("#1d1f24", 0.25)                    # ambient + what reflections see
   k.backdrop("#ece7df")                       # seamless floor-to-wall sweep
   ...geometry, materials...
   k.studio_lights(target=objs)                # key/fill/rim sized to the subject
   k.camera(loc=(4, -6, 2.5), look_at=hero, lens=70, fit=objs, margin=1.3)
   k.finish()                                  # renders / saves per CLI flags
   ```
3. **bkit cheat sheet** (all in `scripts/bkit.py`; read it for the full signatures):
   - Shapes: `cube(size, bevel=)`, `sphere`, `icosphere`, `cylinder(bevel=)`, `cone`, `torus`, `plane`, `monkey`, `text(body, size, extrude, bevel, font=path)`, `mesh(verts, faces)`, `backdrop`. All take `loc`, `rot` (degrees), `scale`, `mat`.
   - Materials: `material(hex, roughness, metallic, coat, transmission, emission=)`, `metal()`, `glass()`, `emissive()`. Hex is sRGB; bkit converts to linear.
   - Modifiers: `add_bevel`, `add_subsurf`, `add_boolean(obj, cutter, 'DIFFERENCE'|'UNION'|'INTERSECT')`, `add_array`, `add_solidify`, `shade_smooth(obj, angle)`, `duplicate(obj, loc, linked=True)`.
   - Placement: `bounds(objs)`, `drop_to_floor(obj)`, `look_at(obj, target)`, `empty()` (use as a pivot or parent), `collection()`.
   - Lights and world: `studio_lights(target, key=1.0)`, `light('AREA'|'SPOT'|'POINT'|'SUN', loc, look_at, power, color, size)`, `world(hex, strength)`, `hdri(path)`.
   - Camera: `camera(loc, look_at, lens, fit=[objs], margin, dof=obj, fstop, ortho=scale)`. `fit=` dollies the camera until everything is in frame, so you never guess distances.
   - Animation: `frames(1, 120, fps=30)`, `key(obj, "location", frame, value)`, `turntable(obj_or_pivot, turns=1)` (a seamless loop).
   - Randomness: `rng(seed)` only. Never the global `random`, so re-renders match.
   - Custom inputs: `arg("color", "#e0512f")` reads `--color` from the command line.
4. Build complex shapes from simple ones: bevel everything that would be manufactured (sharp CG edges catch no light), use booleans for cuts and holes, arrays for repetition, and subsurf for organic forms. When bkit doesn't cover something, write raw `bpy` in the same file. Read `reference/bpy-reference.md` first; it lists the 5.x API changes that break older examples you may remember.

## 4. Render: preview first, then final
```bash
node scripts/blender.mjs scene.py --preview                 # half-res, low samples, ~2 s
node scripts/blender.mjs scene.py --out hero.png            # full EEVEE, ~3–5 s
node scripts/blender.mjs scene.py --engine CYCLES --out hero.png   # path traced; best glass/metal/GI
```
Flags: `--out file.png|.jpg|.webp|.exr|.mp4|dir/`, `--preview`, `--engine EEVEE|CYCLES|WORKBENCH`, `--samples N`, `--res 1920x1080`, `--anim`, `--frames 1-120`, `--frame N` (one still from an animation), `--blend scene.blend` (save an editable file), `--glb model.glb`, `--no-render`, `--open`. `--pypath dir` (repeatable, or `$BKIT_PATH`) puts extra helper modules on the import path; the scene's own folder is always importable. Any other `--flag value` passes through to `k.arg()`.

The output path defaults to the scene name with `.png`. An `.mp4` output renders the frame range as H.264. The first Cycles run on a Mac compiles GPU shaders once (about a minute); after that it's fast.

## 5. Look before you report
Open every preview PNG with the Read tool and check it like an art director would:
- **Framing:** is the subject large enough, with breathing room and nothing clipped? Change `margin` or `lens`, not the camera distance.
- **Grounding:** is everything touching the floor with a contact shadow? Use `drop_to_floor`. Floating objects are the most common tell.
- **Light:** is there a clear key direction, with highlights that show the form? Are there blown-out whites or crushed blacks? Adjust `studio_lights(key=)`, move the key, or change `exposure`.
- **Materials:** does chrome reflect something (it needs a backdrop or bright world)? Does the color match the intent? `--preview` turns off EEVEE raytracing, so metal looks dull and glass looks like gray plastic until a full render. Judge those materials from a full EEVEE or Cycles render, and use Cycles for anything where glass matters.
- **Background:** no visible horizon line or backdrop edge.

Fix, re-preview, and only then render the final. For animation, render `--frame` stills at the start, middle, and end before rendering the full MP4.

Report the output path(s), resolution, engine, and render time. Offer the `.blend` if the person might want to tweak it by hand in Blender.

## Pairs well with
- `ai-gif`: a turntable MP4 can become a GIF with ffmpeg, or a render can be layered into a motion graphic.
- `ai-slide-deck`, `ai-pdf`, `ai-graphic`: render with `transparent=True` and place the PNG.
- `ai-animate`: makes bodies move (rig, retargeting, gait library, motion capture from video, statistical motion models) on top of bkit.
- `ai-adapt`: restages real footage with a coded character (kitbash parts), using ai-animate for the motion.
- `text-to-cad`: export a part to GLB, `bpy.ops.import_scene.gltf`, then light and render it here.
