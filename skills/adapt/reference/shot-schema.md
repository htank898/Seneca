# shot.json

`shot.json` is the single source of truth for one shot. `templates/scene.py` reads every field listed here.

| Field | Meaning |
|---|---|
| `title` | Short slug. |
| `source.video`, `source.shot`, `source.trim` | Where the performance came from: the file, the shot index from `shots.json`, and the trim in seconds. Provenance only. |
| `render.resolution` | `[w, h]`. Match the source aspect (4:3 film → `[1440, 1080]`), or the destination (16:9, 9:16). |
| `render.transparent` | `true` for composite mode (an alpha background). |
| `motion.file` | `motion.json` from ai-animate's `pose.py`, or any `.bvh` (copied one-to-one; `motion.height` rescales the performer, default 1.75 m). |
| `motion.gait` | Use this when there's no reference: `{source, seconds, cadence, stride, arm_swing, fps}` from the open mocap library. See ai-animate's `../animate/reference/motion.md`. |
| `motion.gains` | Optional per-bone swing scaling, such as `{"upper_arm": 0.6}`, on any source. |
| `motion.locomotion` | `footlock`: the body travels past the planted foot (the default for video and gait). `root`: copy the recorded path (the default for BVH). `none`: in place. |
| `motion.ground` | `lock`: the lowest foot point sits on z=0 every frame. `free`: keeps the vertical motion, for jumps. |
| `motion.heading` | Degrees about Z. Rotates the whole performance, for example to turn a profile walk toward the camera. |
| `motion.frames` | `[a, b]`: a 1-based capture range to use, or `null` for all of it. |
| `character.scale` | 1.0 means actor-sized. A 2.4 m creature is about `2.4 / actor_height`. |
| `character.concept` | The turnaround sheet this character was built from. |
| `camera.lens` | Focal length in mm, on a 36 mm sensor. 35 is film-like and 50 is natural. |
| `camera.match` | `{frame, tilt}`: places a level camera so the character projects where the actor was on that frame, at the same height in frame. `tilt` adds degrees of pitch. |
| `camera.loc`, `camera.look_at` | Manual placement, used when `match` is absent. |
| `camera.follow`, `camera.follow_axes` | Dolly with the hips, for example along `"XY"` for a tracking shot. |
| `camera.keys` | `[{frame, loc?, lens?}]`: beats keyed on top of the base placement. |
| `environment.*` | Placeholder world settings: sky, ground, rock color and count, `rock_x`/`rock_y` scatter ranges, sun strength, color and `sun_from` (a point the sun shines from, toward the origin). Replace them with the concept's world in `scene.py`. |
| `beats` | `[{t, frame, what}]`: what happens when. Use it to plan camera keys and effects. |
| `palette` | The concept's colors, with `from` naming the image they were sampled from. |
| `seed` | For `k.rng`. |

Frames and time: frame 1 of the render is frame 1 of `ref.mp4`, or of `motion.frames[0]`. The fps is set from `motion.json`, including NTSC rates such as 23.976.
