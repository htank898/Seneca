# Motion: standards, sources, and how the capture works

## The one rule
- **If there's a reference video, copy it.** `pose.py` captures that performance joint by joint, and it drives the character.
- **If there's no reference, use a real recorded walk** from the open mocap library (`gait.py`), shaped by cadence, stride and arm swing.
- **Never hand-animate a body motion** that either source can supply.

## Standards we use
| What | Standard | Where |
|---|---|---|
| Motion interchange | **BVH** (Biovision Hierarchy), Y-up: a joint hierarchy plus a rotation per joint per frame. Every DCC, game engine and mocap library reads it. | `rig.load_bvh`, `rig.export_bvh`, `scene.py --bvh-out` |
| Joint names | **VRM 1.0 humanoid** bone names (`hips`, `leftUpperArm`, `rightLowerLeg`...). These sit on glTF and are crosswalked to **H-Anim (ISO/IEC 19774)**. | `rig.VRM_NAMES`. Exports use them. |
| Reading foreign skeletons | By **structure, not name**: hand ← forearm ← upper arm, foot ← shin ← thigh. Naming conventions conflict (CMU's `LeftShoulder` is a clavicle; 100STYLE's and SMPL's are the upper arm). | `rig.resolve_skeleton`. Tested on CMU, VRM and SMPL/ExMR names. |
| Body proportions | **Drillis & Contini** segment ratios of standing height, as tabulated in Winter's *Biomechanics and Motor Control of Human Movement*. | `lift.ANTHRO` |

## Capture from video (`pose.py` → `motion.json`)
`pose.py` bootstraps its own Python environment (mediapipe, opencv, numpy) with `uv` in `skills/animate/.venv/` on first run, and downloads the pose model (~30 MB) to `~/.cache/seneca-adapt/`. It moved here from adapt, so the first run after the move rebuilds the environment, which takes a minute. Delete `.venv/` to force a clean rebuild.

1. **Detect** with MediaPipe Pose (Apache-2.0, local). It runs in two modes, merged: a temporal tracker plus per-frame re-detection.
2. **Track one subject.** Lock on `--pick-frame`, then match each frame by nose, shoulder and hip position (predicted forward from velocity), checked against a torso-color signature. Use crop re-detection when two people overlap, and re-identify by appearance after dropouts.
3. **Lift to 3D from the 2D keypoints** (`lift.py`, after Taylor 2000). Each bone keeps its exact on-screen direction, and only the depth is solved, from the bone's true length: `l = s·√(L² − dz²)`.
   - **Scale:** `s` (pixels per metre) comes from the least-foreshortened long bones.
   - **Bone lengths:** anthropometric, lengthened per person where the footage shows a bone is longer.
   - **Depth sign:** MediaPipe's 3D estimate only decides whether a bone points toward or away from the camera.
   - **Girdles:** hips, shoulders and ears are rigid bars through their center, so the torso can't collapse in profile.
   - **Occluded joints** (visibility below 0.15, such as a hand in a pocket) fall back to MediaPipe's 3D guess at the true length.
4. **Report.** `[pose] 2D-anchored lift: reprojection error A% -> B%` shows how far the 3D skeleton is from what the camera saw, as a percentage of torso length. On the Keaton test clip it went from 27.6% (MediaPipe 3D) to 7.6% (lifted).

**Retarget** (`rig.retarget`). Bone lengths stay fixed and directions come from the capture:
- The torso and head twist from the hip, shoulder and ear lines.
- The limbs are swing-only.
- Ground lock keeps the lowest foot point on the floor.
- **Travel** has three modes:
  - `footlock` integrates the planted foot (the one sliding backward relative to the hips), so a walk travels even under a tracking camera.
  - `root` copies a recorded root path, from a BVH or world-grounded capture.
  - `none` keeps the character in place.

**Known limits**:
- **One camera:** the depth sign can flip on bones pointing straight at the lens.
- **Hands:** they're three points each, with no fingers yet.
- **No camera solve:** handheld pans aren't removed. `footlock` copes for walking.
- **Look-alikes:** two similar people overlapping in lockstep can still swap identities. Check `motion.check.png` for this.

## Feet: contacts, pinning, grounding (every source)
`rig.retarget(..., foot_ik=True)` (the default):
- **Rest pose:** the rest foot angle is the performer's own standing-flat angle (`rig.stance_pitch`), so flat in the data means flat on our skeleton.
- **Contacts:** a contact is a foot near the floor moving under 0.6 m/s. Each contact uses the heel-to-toe roll:
  - **Heel phase:** the ankle is pinned in xy and the foot is held flat.
  - **Toe phase:** after heel-off, the toe is pinned and the heel can lift but never sinks below flat.
- **Grounding:** the whole performance is shifted once so the typical planted ankle sits at standing height. Each step then gets one constant height offset. Per-frame heights are never forced; forcing them made legs over-reach.
- **Smoothing:** pin targets are smoothed over time (σ 1.6 frames) and eased in and out over 4 frames.
- **Pelvis adjustment** (as engine foot IK does): if a planted foot can't be reached with at least 4° of knee bend, the hips drop slightly instead of the knee locking straight and snapping.
- **Leg solve:** the leg is re-solved with analytic two-bone IK in the original knee plane. Contacts are stored in `arm["contacts"]`.

**Loops:** `gait.loop` spreads the pose and height residual between a cycle's last and first frame across the cycle, so repeats are seamless. Before this, every cycle boundary produced the largest jerk in the clip.

**Measured** (knee angular acceleration, degrees/frame²; raw mocap → final):
| Gait | Average | Peak |
|---|---|---|
| CMU walk | 3.4 → 2.6 | 7.9 → 9.6 |
| Proud | 2.0 → 2.6 | 6.6 → 13.1 |
| Heavyset | 2.2 → 2.5 | 8.5 → 13.4 |

Before the loop and pelvis fixes, the CMU walk's peak was 33.5. Planted soles sit within about 3 mm of the floor on the CMU walk.

**Known limits:**
- **Bouncy styles** (Elated): contact detection misses many steps, so feet can float there.
- **Asymmetric performers** (Heavyset): one foot can rest a few degrees off flat.
- **No toe bone yet:** the foot can't bend at the ball during push-off. Add a toe bone before adding shoes; shoes are separate meshes skinned to the foot and toe bones.

## Bodies to judge motion on
- `bodies.body(arm, build=1.0)`: a smooth skinned human generated from the skeleton. It uses a skin-modifier mesh with anatomical radii and Gaussian nearest-bone weights, then subdivision. There's no external model and no weight painting; `build` sets the girth.
- `bodies.mannequin(arm)`: segmented capsules and ball joints, for debugging.
- **Judge motion on one of these first.** If a walk looks wrong on the body, the motion is the problem. If it looks right there but wrong on a character, the character design is.
- `templates/walk.py` is the test bench: it shows any gait on the body and prints its metrics. From this skill's folder: `node ../blender/scripts/blender.mjs templates/walk.py --pypath ../animate/scripts --preview --out walk.mp4`.

## Copy a BVH one-to-one
Set `"motion": {"file": "take.bvh"}` in `shot.json`. Root travel defaults to `root`, so the recorded path is reproduced. Sources include an ExMR export, a CMU or 100STYLE clip, a Mixamo download, or a previous shot's `--bvh-out`.

## Standard walks with no reference (`gait.py`)
```json
"motion": { "gait": { "source": "walk", "seconds": 8, "cadence": 1.0, "stride": 1.0, "arm_swing": 1.0 }, "heading": -90 }
```
- **`source`:**
  - a preset: `walk` = CMU 02_01, `slow` = 07_04, `brisk` = 07_12, `stride` = 08_05;
  - `cmu:<trial>` (search with `gait.search("sneak")`; about 2,600 clips, free for any use);
  - `100style:<Style>[/FW|BW|FR|BR|SW|SR|ID]` (100 styles such as Proud, Zombie, HandsInPockets, Drunk, Heavyset; walk and run forward, backward and sideways, plus idle, at 60 fps; list with `gait.styles()`; one 1.5 GB download with `node scripts/gait-fetch.mjs 100style`);
  - a `.bvh` path.
- **Cycle extraction:** the straightest full cycle (heel strike to heel strike, best root chord-to-path ratio) is cut out and looped, with a cross-fade at the seam and the root carried forward. 100STYLE performers walk loops around the capture volume, so a cycle taken from the middle of a clip can sit on a turn.
- **Shaping:**
  - `cadence` is the playback rate.
  - `stride` scales the thigh and shin swing about their mean; with `footlock`, speed follows the legs.
  - `arm_swing` scales the arm swing the same way.
  - Per-person gait matching can later set these from a short reference.
- **Credit:** 100STYLE is CC BY 4.0, so any video using it must say "The 100STYLE Dataset - Ian Mason". Say so in the hand-off.

## High-fidelity backend (opt-in): ExMR
[ExMR](https://github.com/twehrbein/ExMR) (2026-10) recovers body, hands and feet from one video. It's world-grounded, so the actor's real path comes out even under a moving camera. It also gives foot contacts and exports BVH.
- **Use it when:** fingers matter, the camera moves, or the free capture can't separate the subject.
- **Licence:** research, educational and non-profit use only. It also depends on SMPL-X (non-commercial), SAM 3D Body (SAM License) and Ultralytics YOLO (AGPL-3.0). Tell the user before using it, and don't use it for commercial work.
- **Hardware:** an NVIDIA GPU (about 8 GB), so it won't run on a Mac. Options:
  - **Hugging Face Space demo:** clips up to 20 s. Upload `ref.mp4` and download the `.bvh`.
  - **RunPod GPU pod:** follow ExMR's `docs/INSTALL.md`. It needs approved access to `facebook/sam-3d-body-dinov3` on Hugging Face. Run `python tools/demo.py --video ref.mp4 --no_render` (add `-s` for a static camera).
- **Then:** copy `<name>.bvh` into the shot folder and set `"motion": {"file": "<name>.bvh"}`. `load_bvh` resolves the SMPL joint names by structure.

## Statistical motion models (`motionmodel.py`): the average of many performances, plus variation
Use this to animate a gait (or any action) that is nobody's in particular: learn it from many performers, then generate.

**Build:** `templates/model_build.py` fits a model on the CMU walk set. Today that's 118 cycles from 32 people, fitted in about 12 s.
1. **Cut** every clean, straight cycle from left heel strike to the next left heel strike.
2. **Time-align** on all four gait events: R toe-off, R heel strike, L toe-off. Each is warped to its median phase across the library. The learned phases (0.12 / 0.50 / 0.63) match textbook gait.
3. **Normalize:** rotate each cycle to travel +Y. Store bone directions, so performer height drops out, and root bob, sway and speed in leg lengths, plus the duration.
4. **Fit:** the mean plus PCA components (23 cover 95%). Spread is measured two ways: between people (identity) and within one recording (step-to-step wobble).

**Generate:** `templates/model_walk.py`.
- `mm.generate(model)` gives the average person.
- `mm.person(model, seed)` draws a new individual from the between-people spread.
- Each repetition adds wobble, auto-calibrated so stride time varies 2.5%, matching measured human variability. Repetitions blend across the cycle, so there are no seams.
- **Measured components:** PC1 is vigor (cadence, speed, knee lift and arm swing together), PC2 is knee bend, PC3 is arm swing.

**Same recipe for other actions:** for a pitch, a jump or a swing, collect many instances, cut each at consistent events and fit them as a one-shot model. See "One-shot actions" below; `pitch.py` is the worked example.

Instances can come from BVH (mocap) or from video through `pose.py`, once the capture also records the root path.

**Limits:**
- **The mean is still slightly smoothed:** hip bob is about 60% of a single cycle's (1.9 against 3.0 cm). Dynamic time warping between events would sharpen it.
- **CMU takes are short** (start, 2–3 strides, stop). That's why wobble is calibrated to published stride variability instead of measured from the takes.

## One-shot actions (`pitch.py`, the template for future actions)
A pitch, a jump or a swing happens once rather than looping, so it's modelled as a **one-shot** statistical motion: the same `instance()` → `fit()` pipeline as gait, with `cyclic=False`, plus its own events and generator.

**Events.** `pitch.events(mo)` detects them in each performance:
| Event | Detection |
|---|---|
| `start` | Windup begins: scanning back from the leg lift, the last 0.2 s where hands, lead ankle and root were all still (under 0.35 m/s), i.e. the set position. |
| `lift` | Peak height of the lead (glove-side) ankle. |
| `plant` | First frame after the lift where the lead ankle is within 6 cm of the floor and slower than 1.5 m/s. |
| `release` | Peak speed of the throwing wrist. This lands a frame or two after the true release, but it's consistent. |
| `end` | Release + 0.6 s (follow-through). |

Every instance is time-warped piecewise-linearly so `lift`, `plant` and `release` fall at their median phase across the library. The throwing arm is the wrist with the higher peak speed.

**Left-handers.** `pitch.mirror(mo)` reflects across the body's sagittal plane and swaps every left/right landmark pair. `instances_from_mos` does this automatically, so one right-handed model covers both sides. To get a left-handed output, mirror the generated `mo`.

**Generation.** `pitch.generate(model, seed=, wobble=, tempo=)` returns `(mo, events)` for one pitch:
- **Holds:** the set position is held before the windup and the follow-through after.
- **Segment timing:** each event segment's duration can be overridden with `tempo` (e.g. `{"plant->release": 0.14}` for a pro arm).
- **Events in the output timeline:** `events` gives the frame numbers, which the ball needs.

**The ball.** `pitch.ball(arm, events, speed=)`:
- **Held:** until `release`, it's placed every frame in the fingers, just past the tip of the throwing hand bone.
- **In flight:** after release it follows a ballistic path, solved so it reaches the plate (18.44 m, at knee-to-chest height) at `speed` m/s under gravity, with backspin (~1800 rpm).
- **Field:** `pitch.field()` builds the mound (flush with the feet), the rubber and home plate.

**Measured on CMU 124_01 and 124_02** (two right-handed lab pitches from the windup, at 60 fps):
| Segment | Duration |
|---|---|
| start → lift | 1.78 / 1.65 s |
| lift → plant | 0.53 / 0.52 s (MLB is roughly 0.5–0.7 s) |
| plant → release | 0.17 / 0.20 s (MLB is about 0.14–0.15 s) |

- **Library event phases:** lift 0.567, plant 0.741, release 0.802 of a 3.03 s delivery.
- **Hand speed:** the lab performer's peaks at about 11 m/s, against well over 30 m/s for MLB. So the arm reads amateur and the ball speed is set independently.
- **Release height:** about 1.15 m, a three-quarter slot.

**Adding a new action.** Copy `pitch.py`:
1. Define the events for the new action and detect them from landmarks and root.
2. Mirror for handedness if it applies.
3. Reuse `motionmodel.instance(..., cyclic=False, events=...)`, `fit` and the same `generate` pattern (piecewise phase timing plus holds).
4. Add any props the way `ball()` does: attach to a bone until an event, then simulate.
