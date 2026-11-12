---
name: animate
description: Make bodies move in Blender. Drives a character or model with real human motion — walks, runs, gaits and walk cycles from open mocap libraries (CMU, 100STYLE), BVH or mocap copied one-to-one onto a model, motion captured from ordinary video (local MediaPipe, no keys), and statistical motion models that average many performances and generate new ones that copy no one. Includes one-shot sports actions such as baseball pitching from the windup with a held, released ball. Use for "make my character/model walk", "run cycle", "give it a proud/old/zombie walk", "retarget this mocap/BVH onto my model", "average all these walks", "generate a unique gait", "animate a pitcher", "sports motion", "mocap this video", "motion capture from video".
---

# Animate: real human motion, on any body, in Blender

Paths are relative to this skill's base directory. It sits on top of `ai-blender` (`../blender/`), which owns bkit, the headless runner, scenes, materials, lights, cameras and rendering. This skill is the motion: rigs, retargeting, bodies, motion data, statistical models and actions. `ai-adapt` uses it to restage real footage.

Run every scene through the Blender runner with this skill's scripts on the path:
```bash
node ../blender/scripts/blender.mjs <scene>.py --pypath ../animate/scripts [--preview] [--out x.mp4]
# add --pypath ../adapt/scripts when the scene also uses ai-adapt's character parts (parts.py)
```
Read `reference/motion.md` for the full method, the standards and the measured numbers.

| Script | What it does |
|---|---|
| `rig.py` | Standard armature, retarget (contacts, foot IK, pelvis adjustment), BVH in and out, `match_camera` |
| `bodies.py` | `body()` (smooth skinned human) and `mannequin()`; placement helpers for attached parts |
| `pose.py`, `lift.py` | Video → `motion.json` |
| `gait.py`, `gait-fetch.mjs` | CMU and 100STYLE gait library |
| `motionmodel.py` | Statistical motion models |
| `pitch.py` | The pitching action, and the template for one-shot actions |
| `gvhmr.py`, `pod/` | GVHMR video capture on a RunPod GPU (non-commercial) |
| `physics.py` | Centre of mass and quasi-static balance |
| `checks.py` | Penetration, floor and jitter measurements |

## 1. Pick a motion source
- **Video capture:** `python3 scripts/pose.py clip.mp4 --preview [--pick-frame N] [--subject left|right|largest]` writes `motion.json`.
  - The 3D skeleton is rebuilt from the 2D keypoints, so bone directions match the image (`lift.py`).
  - The subject is tracked by position, using torso color only when several people are in view.
  - **Read `motion.check.png`.**
  - The first run builds `skills/animate/.venv` with `uv`. It moved from ai-adapt, so it rebuilds once.
- **Best-quality video capture (non-commercial only): GVHMR.** `python3 scripts/gvhmr.py clip.mp4` writes `clip.gvhmr.bvh`.
  - It gives the whole body plus its world path over the ground (static or moving camera), with far less foot sliding than MediaPipe. Use it for AI-generated clips of the character itself: the motion then already has the character's proportions.
  - It runs on a RunPod GPU. Each run creates a pod, installs GVHMR from upstream, and terminates the pod even on errors. `--keep-pod` with `--pod ID` reuses one pod across several clips.
  - Run `--check` first; it lists what's missing: `~/.config/runpod/api_key`, plus `SMPLX_NEUTRAL.npz` and `SMPL_NEUTRAL.pkl` in `~/.cache/seneca-gvhmr/body_models/`. Users download those from their own SMPL/SMPL-X registration; they are never bundled.
  - Load the result with `rig.load_bvh(path, height=H)`, then retarget with `locomotion="root", quality=True`.
  - **Non-commercial and research only** (GVHMR and SMPL licences). For commercial work use `pose.py`.
- **A BVH, copied one-to-one:** `rig.load_bvh(path)` gives a mo dict, then `rig.retarget(arm, mo, locomotion="root")`. Any skeleton naming works (CMU, 100STYLE, VRM, SMPL/ExMR), because joints are found by structure.
- **The gait library** (no reference): `mo, gains = gait.walk("walk"|"slow"|"brisk"|"cmu:<id>"|"100style:<Style>", seconds, cadence, stride, arm_swing)`.
  - The straightest cycle is cut out and looped seamlessly.
  - 100STYLE needs a one-time `node scripts/gait-fetch.mjs 100style` (1.5 GB).
- **A statistical model:** the average of many performers, or a new individual. See section 5.

## 2. Bodies: judge motion before characters
`bodies.body(arm, build=1.0)` is a smooth skinned human with flat-soled feet. `bodies.mannequin(arm)` is segmented, for debugging. **Judge every motion on one of these first.** If it looks wrong on the body, the motion is the problem. If it only looks wrong on a character, the character design is. Characters (ai-adapt's `parts.py`, or ai-character rigs) attach to the same bones.

## 3. Retarget
`rig.armature(mo)` builds a T-pose skeleton sized to the performer, with the rest foot angle taken from their own stance. `rig.retarget(arm, mo, locomotion=, ground=, heading=, gains=, foot_ik=True)` keys it:
- **Feet:**
  - **Contacts:** a foot near the floor moving under 0.6 m/s counts as planted.
  - **Heel-to-toe roll:** the ankle is pinned while the heel is down, then the toe after heel-off.
  - **Leg solve:** analytic two-bone IK, with targets smoothed over time and eased in and out over 4 frames.
  - **Grounding:** the body is grounded once, then each step gets one constant height offset.
- **Pelvis adjustment:** the hips dip slightly rather than let a planted leg lock straight.
- **Locomotion:**
  - `root` copies a recorded path (BVH or a model).
  - `footlock` integrates the planted foot (video, tracking cameras, gains).
  - `none` keeps the character in place.
- **Gains:** `gains={"thigh": 1.2, "upper_arm": 0.5}` scales swing about the mean. That's stride and arm-swing shaping.
- **Loops:** `gait.loop` spreads the end-to-start residual across the cycle, so repeats don't hitch.
- **Export:** `rig.export_bvh(arm, path)` writes Y-up BVH with VRM joint names.

### Clean-up passes (`quality=True` turns them all on)
`rig.retarget(arm, mo, ..., quality=True)` runs these. Each is also available on its own, and all are off by default.

- **Clearance:** `clearance=rig.measure_girth(body, arm)`. Measure the skinned character first.
  - It keeps arms out of the torso (a polar profile per torso bone, so a bag or pouch counts), the head and the thighs, and legs out of each other.
  - A penetrating limb swings about its shoulder or hip, keeping its bend, and corrections are eased over time.
  - It is calibrated on the rest pose, so the mesh's own stance never counts as a collision.
- **Stride:** `stride_scale="auto"` scales the recorded root path and bob by leg length, so short legs don't over-stride.
- **Floor:** `ground="local"` (root locomotion) puts the floor at the lowest foot within ±0.4 s. Chained clips from different performers each land on the floor, and runs keep their flight phase.
- **Foot pitch:** `foot_pitch="match"` maps each segment's flat performer foot to the character's flat foot. CMU feet are about 30° flat, many meshes about 17°. Copied raw, the toes point down and the body floats about 6 cm.
- **Feet:**
  - `toe_contacts`: the toe phase counts as contact by the toe's own speed.
  - `level_feet`: planted soles stay level side to side.
  - `floor_guard`: a swing foot never dips through the floor (smoothed lift).
  - `max_drop=0.08`: caps the pelvis adjustment.
- **Balance:** `physics=True` (`physics.py`, Winter's segment masses) keeps the centre of mass over the planted feet, but only while the body is nearly still. Dynamic gaits are left alone.
- **Hand IK:** `hand_targets={"L": fn(i) -> Vector | None}` puts the wrist on a world point.
- **Not in `quality`:** `twist="hinge"` (the upper arm and thigh roll follows the elbow or knee bend). On CMU runs it carried the capture's hip rotation into the knees, raising leg-leg overlap from 1% to 21% of frames.
- Results land in `arm["retarget_stats"]`.

### Skinning a generated character
`rig_character.skin(..., "capsule")` (character-3d) is the skinning to use for AI-generated meshes. They are open shells, and Blender's bone heat fails on 100% of the vertices.
- Each vertex goes to the nearest body-part capsule.
- Accessories (satchel, strap, coat hem) far off a thigh or upper arm move to the torso.
- Weights then diffuse along the surface, giving about a 5 cm blend at joints, and are bound with preserve-volume.

Also:
- Symmetrize the landmarks with `rig.symmetrize_joints(J)`.
- `armature_from_joints` no longer deforms the `shoulder.*` and `hip.*` bones.

## 4. Templates
| Template | Use |
|---|---|
| `templates/walk.py` | Any library gait on the body, plus metrics (`--src`, `--stride`, `--cadence`, `--arms`, `--build`, `--body mannequin`) |
| `templates/model_build.py` | Fit a gait model from a CMU trial list (`--set`, `--out`) |
| `templates/model_walk.py` | Walk from a model (`--model`, `--person N`, `--wobble`, `--seed`, `--sec`, `--fps`) |
| `templates/pitch_build.py` | Fit the pitching model (`--trials 124_01,124_02`, `--bvh more.bvh`, `--out`) |
| `templates/pitch_render.py` | Render one pitch with the ball (`--seed`, `--speed` m/s, `--cam side|cf`, `--fps`) |

## 5. Statistical models (`motionmodel.py`)
- **Build:** `gait_cycles_from_bvh(paths)` cuts every clean, straight cycle and time-aligns them on R toe-off, R heel strike and L toe-off, each at its median phase. It stores bone directions plus root bob, sway and speed in leg lengths, plus the duration. `fit(insts)` gives the mean, the PCA components, and the spread **between people** and **within a recording**.
- **Individuals:** `person(model, seed)` draws a new individual from the between-people spread.
- **Wobble:** `generate(model, person_z=, wobble=None)` varies every repetition slightly. The `wobble=None` default auto-calibrates to a 2.5% stride-time coefficient of variation, matching measured human variability. Repetitions blend across the cycle, so there are no seams.
- **One-shot generation:** `instance(..., cyclic=False, events=...)` plus an action module's `generate`. See section 6.
- **Measured (CMU walks):**
  - 118 cycles from 32 people, 23 components.
  - Learned event phases 0.124 / 0.50 / 0.629, which are textbook.
  - PC1 is vigor (speed, cadence, knee lift and arm swing together).

## 6. Actions: `pitch.py` is the template
A one-shot action has its own module:
1. **Event detection:** `events()`. For pitching: start, lift, plant, release, end.
2. **Handedness mirroring:** `mirror()`.
3. **Instances:** `instances_from_mos()` / `instances_from_bvh()`, warped to the median event phases.
4. **Generation:** `generate()`, with piecewise phase timing, holds, and an optional `tempo` per segment.
5. **Props:** `ball()` keeps the ball in the fingers until release, then flies it ballistically to the plate.

For a new action (a jump, a swing, a kick), copy `pitch.py` and redefine the events and props.

## 7. Verify before reporting
- **`checks.py`:** `checks.report(body, arm, mo=mo, props=[...], frames=(f0, f1))` prints `[checks] {...}`.
  - **Penetration:** per region pair, % of frames and vertices, against the rest pose. Regions come from geometry, not skin weights, so two skinning methods are graded on the same regions.
  - **Floor:** lowest mesh point, and signed sole height on contact frames (aim for under 10 mm).
  - **Jitter:** knee and elbow angular acceleration, rig vs source.
  - Measured on the archery scene, legacy → quality:
    | Measure | Legacy | Quality |
    |---|---|---|
    | Arm L into torso (verts/frame) | 210 | 36 |
    | Bow into body | 194 | 69 |
    | Frames with the mesh more than 1 cm below the floor | 92 | 24 |
    | Planted soles above the floor (median) | ~38 mm | 6 mm |
  - Read the numbers next to stills; the archery scene's `--stills dir` and `--debug-pen dir` (penetrating vertices painted red) show where problems are.
- **Gait metrics** (`[gait] {...}` from the templates). Healthy everyday walking is roughly:

  | Metric | Healthy range |
  |---|---|
  | Knee | about 0–70° |
  | Speed | 1.0–1.5 m/s |
  | Hip bob | 2–5 cm |
  | Contact | 50–62% per foot |
  | Stride-time variation | 2–3% |

  Styled gaits (Old, Zombie) differ on purpose.
- **Foot contact:** measure the sole profile on flat-foot frames. It should sit within about ±3 mm of the floor.
- **Jitter:** knee angular acceleration should stay close to the raw mocap's. If spikes land on cycle boundaries, suspect a seam.
- **Compare sheets:** use ai-adapt's `compare.mjs` with source frames and renders side by side. Read the sheets; don't just trust the numbers.
- **Look:** read stills from the start, middle and end, plus a low close-up of the feet.

## 8. Licences
- **CMU mocap:** free for any use.
- **100STYLE:** CC BY 4.0. **Credit "The 100STYLE Dataset - Ian Mason"** in any video that uses it, and say so in the hand-off.
- **MediaPipe:** Apache-2.0.
- **GVHMR** (`gvhmr.py`): (c) Zhejiang University, educational, research and non-profit use only. It is cloned from upstream at run time and never vendored. It needs SMPL and SMPL-X, which users register for and download themselves. Cite Shen et al., SIGGRAPH Asia 2024.
- **ExMR** (the optional high-fidelity video capture: body, hands, feet, world path): research and non-profit only. It depends on SMPL-X (non-commercial). Never use it by default; ask first.
- **Broadcast footage** (MLB etc.) is acceptable as a motion reference for non-commercial work. Keep clips local in gitignored `adapt-dev/` and never commit them.
