"""Fit a one-shot pitching model (events: start, lift, plant, release, end) from BVH pitches.

  node ../blender/scripts/blender.mjs templates/pitch_build.py --pypath ../animate/scripts --no-render \\
       [--trials 124_01,124_02] [--bvh a.bvh,b.bvh] [--out pitch_model.json] [--keep 0.99]

--trials are CMU ids (fetched on demand); --bvh adds any other BVH files (e.g. ExMR exports of MLB
footage). Left-handers are mirrored automatically. Prints per-pitch segment timings.
"""
import os
import bkit as k, rig, gait, motionmodel as mm, pitch
k.reset(); k.scene().render.fps = 60
paths = [gait.fetch_cmu(t) for t in k.arg("trials", "124_01,124_02").split(",") if t]
paths += [os.path.abspath(p) for p in (k.arg("bvh") or "").split(",") if p]
insts = pitch.instances_from_bvh(paths)
model = mm.fit(insts, keep=float(k.arg("keep", 0.99)))
model["event_phases"] = insts[0]["event_phases"]
out = k.arg("out", "pitch_model.json")
mm.save(model, out)
print("[model] %d pitches, event phases %s, mean duration %.2fs, %d component(s); saved %s" % (
    model["n"], {kk: round(v, 3) for kk, v in model["event_phases"].items()}, model["mean"][-1], len(model["sigma"]), out), flush=True)
