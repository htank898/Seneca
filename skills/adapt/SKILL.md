---
name: adapt
description: Restage real footage as a fully animated 3D scene. Take a human-captured video (the user's own clip, or any reference), use Gemini (Nano Banana for stills, Omni Flash for video) only as the art department to imagine the character and world, then build that character and world as code in Blender and drive it with the human performance captured from the video (local MediaPipe pose capture, retargeted onto a rig). Rendered, not generated, so nothing hallucinates. Use for "turn me into a robot/creature/armoured warrior in this clip", "restage this video in another world", "make an animated version of this footage", "mocap this video onto a character", "reshoot this as 3D", "put a 3D character in this scene".
---

# AI Adapt: real performance, imagined world, rendered for real

Generative video is creative but unreliable: limbs melt, the character drifts between frames, and nothing can be edited afterwards. This skill splits the job:
- **The human video supplies the performance.** Pose capture extracts the actual motion.
- **Gemini supplies the imagination.** Nano Banana proposes the character and the world, and Omni Flash can suggest how the shot evolves. Its outputs are **art targets only**.
- **Blender supplies the pixels.** The character and environment are code (`bkit` + `parts`), the motion is keyed from the capture, and the camera is matched to the source. Every frame is rendered, deterministic, and editable.

Paths below are relative to this skill's base directory. Sibling skills: `../blender/` (`blender`: bkit and the `scripts/blender.mjs` runner) and `../animate/` (`animate`: capture, rig, retarget, bodies, motion). Scenes run with both on the path: `--pypath ../animate/scripts --pypath scripts`. Requires Blender, ffmpeg, Node, and `uv` (for the pose env). Needs `GEMINI_API_KEY` only for the concept stages (create a key at aistudio.google.com/apikey). Everything else runs without keys.

Work in a project folder (not inside the skill), one folder per shot:
```
<shot>/ ref.mp4  frames/ contact.png  motion.json  concept/ reference/  shot.json  character.py  scene.py  renders/
```

## 1. Ingest the footage
```bash
node scripts/ingest.mjs source.mp4 --out <shot>                  # shots.json, frames/, contact.png
node scripts/ingest.mjs source.mp4 --out <shot> --trim 14.2-22    # cut the working clip -> <shot>/ref.mp4
```
- Read `contact.png`. Tiles run row-major in time order, and the printed table maps each tile to its time and frame.
- Pick **one continuous shot** with the performer's **full body visible**, ideally separated from other people. Trim to it.
- One shot means one scene. A multi-shot sequence is several shot folders, edited together at the end.

## 2. Get the performance (animate)
Motion is **animate**'s job (`../animate/`): capture, retargeting, bodies, the gait library, statistical models and actions. Load that skill and follow its "Pick a motion source" section. For a restage, the normal case is to capture the reference clip:
```bash
python3 ../animate/scripts/pose.py <shot>/ref.mp4 --out <shot>/motion.json --preview [--pick-frame N] [--subject largest|left|right|center]
```
**Read `<shot>/motion.check.png`.** Check that the skeleton is on the right person in every tile, and that coverage is at least 90%. In `shot.json`, `motion.file` can instead name a BVH (copied one-to-one), and `motion.gait` uses the gait library when there's no reference. The method, the standards and the licences are in `../animate/reference/motion.md`. Judge the motion on `bodies.body()` before blaming the character.

## 3. Concept with Nano Banana (the art target)
Use the recipes in `reference/prompts.md`. Write the brief first: what the character is, the world, the mood, and the palette. **Never name a trademarked character.** Describe the genre instead: "a biomechanical masked warrior of interlocking armour plates and ball joints", not a brand name.
```bash
G="node scripts/gemini.mjs"
$G image --ref <shot>/frames/<hero>.jpg --prompt "<restage recipe>"   --aspect 16:9 --out <shot>/concept/restaged.png --n 3
$G image --ref <shot>/concept/restaged.png --prompt "<turnaround recipe>" --aspect 16:9 --out <shot>/concept/turnaround.png
$G image --ref <shot>/concept/restaged.png --prompt "<environment plate recipe>" --aspect 16:9 --out <shot>/concept/environment.png
```
- Read every output.
- Show the user the options and let them **pick one of each**. The look is their call.
- `concept/log.json` records the prompts and references, so the look stays reproducible.

**Still mode, the default and cheapest route:** one hero frame restaged by Nano Banana *is* the scene concept. Skip step 4.

## 4. Optional: reference video with Omni Flash
Use this when the shot needs staging ideas that a still can't give: a camera move, an effect, a beat.
```bash
$G video --image <shot>/concept/restaged.png --ref-video <shot>/ref.mp4 --ref-start 2.0 \
   --prompt "<motion recipe>" --duration 6s --out <shot>/reference/omni.mp4
```
- Omni Flash takes reference clips of 3 s or less, and the script trims them.
- Pull frames with `compare.mjs --videos`, read them, and write down **only the beats** into `shot.json`: camera moves, timing, effects.
- Its character animation is never used. The capture drives the body.

## 5. Write `shot.json`
Copy `templates/shot.json`. The field reference is in `reference/shot-schema.md`. Fill it in from what you observed:
- **Render size:** match the source aspect.
- **Motion options:** `locomotion` is `footlock` or `none`, `ground` is `lock` or `free`, `heading`, and an optional `frames` range.
- **Camera:** `match.frame` places the camera so the character lands where the actor was. Add `follow` for tracking shots, and `keys` for the Omni beats.
- **Environment colors:** sampled from the concept.
- **Beats:** with timestamps.

## 6. Build the character as code
Copy `templates/character.py`, `templates/scene.py`, and `templates/shot.json` into the shot folder. `character.build(arm)` starts from `parts.biomech(arm, palette)`, a complete masked biomechanical warrior. Then change it to match the turnaround sheet:
- **Palette:** take the hex values from the concept.
- **Silhouette:** `bulk`, mask `style` (`hau` broad, `kaukau` tall, `pakari` wide-jawed), crest fins, back spikes.
- **Extra pieces:** add them with `parts.plate`, `shell`, `rod`, `piston`, `spikes`, `claws`, `joint`, `boot`, `shoulder_pad`, plus raw `bkit` geometry placed with `parts._put` (shoulder armor, weapons, capes as plates).

Bone-local axes: **Y** runs along the bone. **Z** is the character's front on the torso and limbs. **X** is the character's left on the torso and head. `at` is 0 at the head of the bone and 1 at its tail.

Every part is **rigidly parented to a bone**. This is why mechanical and armored characters need no skinning or weight painting. For a soft or organic character, use bkit's skin, subsurf, and solidify modifiers on a mesh, parented with automatic weights in raw bpy, and say that it's slower to get right.

Turnaround check, rendered in T-pose:
```bash
# a function, not B="node ...": zsh doesn't word-split $B. Paths relative to this skill.
B() { node ../blender/scripts/blender.mjs "$1" --pypath ../animate/scripts --pypath scripts "${@:2}"; }
B <shot>/scene.py --rest --preview --out <shot>/renders/turn0.png
B <shot>/scene.py --rest --turn 90 --preview --out <shot>/renders/turn90.png
node scripts/compare.mjs --out <shot>/renders/turn-vs-concept.png <shot>/concept/turnaround.png,<shot>/renders/turn0.png,<shot>/renders/turn90.png
```
Read the sheet. Silhouette, proportions, palette, and the mask read should be recognizably the concept. Iterate until they are.

## 7. Build the environment
Replace the placeholder ground and rocks in `scene.py` with the concept's world, using bkit primitives, booleans, arrays, and `k.rng(seed)` scatter. Model the hero props properly. Far scenery can be a **camera-facing card textured with `concept/environment.png`**: an emission or principled image texture on a big plane behind the action. It's a static, authored backdrop, so it can't drift. Match the sun direction and color to the concept's lighting.

## 8. Animate and review
`scene.py` runs `rig.retarget` automatically, unless you pass `--rest`. The rig keeps bone lengths fixed, so limbs never stretch:
- The torso and head twist from the hip, shoulder, and ear lines.
- The limbs are swing-only.
- `footlock` moves the body past the planted foot, so a walk travels even when the source camera tracked the actor. A BVH source defaults to `root`, which copies its recorded path.

```bash
B <shot>/scene.py --no-render --stats --bvh-out <shot>/take.bvh   # stats + the performance as standard BVH
B <shot>/scene.py --preview --frame 1 --out <shot>/renders/f1.png      # + a middle and a last frame
B <shot>/scene.py --preview --out <shot>/renders/preview.mp4
node scripts/compare.mjs --out <shot>/renders/vs-source.png --videos <shot>/ref.mp4,<shot>/renders/preview.mp4 --frames 1,60,120
```
Check:
- **Feet:** the stats `min_foot_z` should be at least −0.02 and `max_foot_low_z` at most 0.04 (planted, no sinking).
- **Travel:** plausible for the action. A walk runs about 1–1.4 m/s, and a slow sneak is lower.
- **Poses:** each row of the compare sheet should show the same pose as the source.
- **Framing:** the character sits where the actor was.
- **Clipping:** nothing passes through the body or the floor.

**Optional paint-over.** Run `gemini.mjs image` with refs `[render frame, concept/restaged.png]` and the paint-over recipe. Nano Banana returns the render redrawn toward the concept. Read it and **fix the code** toward it: materials, lighting, missing details. The paint-over is the next art target, never a frame of the video.

## 9. Modes
- **Full render (default):** everything is Blender.
- **Composite:** use this to put the character into the original footage.
  1. Set `render.transparent: true` and `camera.match` with `follow`, and leave out the environment except a shadow catcher: a ground plane with `is_shadow_catcher = True` in Cycles.
  2. Render a PNG sequence or `.mov`, then overlay it with ffmpeg: `ffmpeg -i ref.mp4 -i char_%04d.png -filter_complex overlay out.mp4`.
  3. Check feet alignment at three frames with `compare.mjs`.
  `match_camera` solves a level camera from one frame. For handheld or panning source cameras, key `camera.keys` by eye at the beats. There is no automatic camera solve.

## 10. Final render and hand-off
```bash
B <shot>/scene.py --out <shot>/renders/final.mp4                 # EEVEE, full res
B <shot>/scene.py --engine CYCLES --out <shot>/renders/final.mp4 # slower, best metal/glass
B <shot>/scene.py --no-render --blend <shot>/renders/shot.blend  # editable file
```
For sound or narration, pass the MP4 to `video-edit` or `video-create`.

Report:
- the MP4 path, resolution, fps, duration, and render time (from ffprobe);
- the stats line;
- the compare sheets you checked;
- which concept images were the art targets, and where `log.json` is;
- the motion source. A 100STYLE clip must be credited as "The 100STYLE Dataset - Ian Mason". If ExMR was used, say the result is non-commercial only;
- what didn't transfer, plainly: interpolated stretches, overlap swaps, a camera that was matched by hand.

## Rules
- Gemini outputs are references. They never appear in the final video.
- Don't name or copy trademarked characters, logos, or real people's likeness in prompts or models. Design in the genre.
- Development clips from films stay out of the repo (`adapt-dev/` is gitignored). Shipped examples use the user's own footage or public-domain/CC0 footage.
- Randomness only through `k.rng(seed)`, so re-renders match frame for frame.
