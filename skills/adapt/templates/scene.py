"""One shot of an adapt video: the captured performance, worn by a coded character, in a
coded environment, framed like the reference. Everything is deterministic and re-runnable.

  (from skills/adapt/; scene.py lives in your shot folder)
  node ../blender/scripts/blender.mjs <shot>/scene.py --pypath ../animate/scripts --pypath scripts --preview --frame 40
  node ../blender/scripts/blender.mjs <shot>/scene.py --pypath ../animate/scripts --pypath scripts --out shot.mp4
rig/gait come from animate; character.py (next to this file) uses adapt's parts.py.

Custom flags (read with k.arg): --motion motion.json|take.bvh  --shot shot.json  --rest (T-pose
turnaround, no animation)  --turn 0|90|180  --bvh-out take.bvh (export the performance)  --stats
"""
import json
import math
import os

import bkit as k
import rig
import character

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = json.load(open(os.path.join(HERE, k.arg("shot", "shot.json"))))
REST = bool(k.arg("rest"))

k.reset()
res = tuple(SHOT["render"]["resolution"])
k.render_settings(res=res, transparent=SHOT["render"].get("transparent", False),
                  motion_blur=not REST)

# ---- performance
# Motion comes from one of three sources (shot.json "motion"):
#   file: motion.json  -> captured from the reference video by animate's pose.py (copied joint by joint)
#   file: take.bvh     -> any BVH (ExMR export, CMU, 100STYLE, Mixamo...), copied one-to-one
#   gait: {...}        -> no reference: a standard walk from the open mocap library (gait.py)
m = SHOT["motion"]
src = k.arg("motion", m.get("file"))
if m.get("gait") and not k.arg("motion"):
    import gait
    g = m["gait"]
    fps = g.get("fps", 24)
    k.scene().render.fps = fps
    mo, gains = gait.walk(g.get("source", "walk"), seconds=g.get("seconds", 8), cadence=g.get("cadence", 1.0),
                          stride=g.get("stride", 1.0), arm_swing=g.get("arm_swing", 1.0), fps=fps,
                          height=g.get("height", 1.75))
elif src.lower().endswith(".bvh"):
    mo, gains = rig.load_bvh(os.path.join(HERE, src), fps=m.get("fps", 24), height=m.get("height", 1.75)), None
else:
    mo, gains = rig.load_motion(os.path.join(HERE, src)), None
arm = rig.armature(mo, scale=SHOT["character"].get("scale", 1.0))
objs, pal = character.build(arm)
if REST:
    arm.rotation_euler.z = math.radians(float(k.arg("turn", 0)))
    k.frames(1, 1)
else:
    default_loco = "root" if mo.get("root") and not gains and not m.get("gait") else "footlock"
    roots = rig.retarget(arm, mo, locomotion=m.get("locomotion", default_loco), ground=m.get("ground", "lock"),
                         heading=m.get("heading", 0.0), frames=tuple(m["frames"]) if m.get("frames") else None,
                         gains=gains or m.get("gains"))

# ---- environment (replace with the concept's world: terrain, props, sky)
env = SHOT["environment"]
k.world(env.get("sky", "#9fb6c9"), env.get("sky_strength", 0.6))
ground = k.plane(80, mat=k.material(env.get("ground", "#7a6a55"), roughness=0.9), name="ground")
rnd = k.rng(SHOT.get("seed", 7))
for i in range(env.get("rocks", 0)):
    x, y = rnd.uniform(*env.get("rock_x", [-12, 12])), rnd.uniform(*env.get("rock_y", [2, 25]))
    k.icosphere(rnd.uniform(0.2, 0.9), loc=(x, y, 0.1), scale=(1, rnd.uniform(0.6, 1.3), rnd.uniform(0.4, 0.8)),
                mat=k.material(env.get("rock", "#5b544c"), roughness=0.85), subdivisions=1, name=f"rock{i}")
sun = k.light("SUN", loc=tuple(env.get("sun_from", [4, -6, 10])), look_at=(0, 0, 0), power=env.get("sun", 4.0),
              color=env.get("sun_color", "#fff1dc"))
sun.data.angle = math.radians(2.0)

# ---- camera: matched to the reference framing, then (optionally) dollying with the actor
c = SHOT["camera"]
if REST:  # turnaround: frame the whole character, front/side/back via --turn
    cam = k.camera(loc=(0, -5, 1.0), look_at=objs[0], lens=70, fit=objs, margin=1.15)
elif c.get("match") and mo.get("image"):  # place the camera so the character lands where the actor was in the reference
    cam = k.camera(loc=(0, -6, 1), lens=c.get("lens", 35))
    m0 = SHOT["motion"].get("frames") or [1]
    print("[adapt] camera", rig.match_camera(cam, mo, roots, frame=c["match"].get("frame", 1),
          scale=SHOT["character"].get("scale", 1.0), src_offset=m0[0] - 1), flush=True)
    cam.rotation_euler.x += math.radians(c["match"].get("tilt", 0))
else:
    cam = k.camera(loc=tuple(c["loc"]), look_at=tuple(c["look_at"]), lens=c.get("lens", 35))
if c.get("follow") and not REST:
    rig.follow_camera(cam, arm, axes=c.get("follow_axes", "XY"))
for kf in ([] if REST else c.get("keys", [])):  # beats from shot.json: {"frame": 1, "loc": [...], "lens": 35}
    if "loc" in kf:
        k.key(cam, "location", kf["frame"], tuple(kf["loc"]))
    if "lens" in kf:
        k.key(cam.data, "lens", kf["frame"], kf["lens"])

if not REST and k.arg("bvh-out"):  # the performance as a standard BVH (VRM joint names, Y-up)
    print("[adapt] bvh", rig.export_bvh(arm, os.path.abspath(k.arg("bvh-out"))), flush=True)
if not REST and k.arg("stats"):
    print("[adapt] stats", json.dumps(rig.stats(arm, mo)), flush=True)
k.finish()
