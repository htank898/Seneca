"""Fit a statistical gait model (mean + PCA + between/within-person spread) from many walkers.

  node ../blender/scripts/blender.mjs templates/model_build.py --pypath ../animate/scripts --no-render \\
       [--set ~/.cache/seneca-adapt/cmu/walk_set.txt] [--out walk_model.json] [--keep 0.95]

--set lists CMU trial ids (one per line); fetch them first with
  node animate/scripts/gait-fetch.mjs cmu <trial> ...   (or the list in reference/motion.md)
"""
import os, json, time
import numpy as np
import bkit as k, rig, gait, motionmodel as mm
k.reset(); k.scene().render.fps = 60
cmu = os.path.join(gait.CACHE, "cmu")
set_path = os.path.expanduser(k.arg("set", os.path.join(cmu, "walk_set.txt")))
trials = open(set_path).read().split()
t0 = time.time()
insts = mm.gait_cycles_from_bvh([gait.fetch_cmu(t) for t in trials], verbose=False)
model = mm.fit(insts, keep=float(k.arg("keep", 0.95)))
out = k.arg("out", "walk_model.json")
mm.save(model, out)
durs = sorted(i["duration"] for i in insts)
print("[model] %d cycles from %d clips (%d people) in %.0fs; cycle %.2f-%.2f s (median %.2f); %d components; saved %s" % (
    model["n"], len(model["sources"]), len({s.split('_')[0] for s in model["sources"]}), time.time() - t0,
    durs[0], durs[-1], durs[len(durs)//2], len(model["sigma"]), out), flush=True)
print("[model] spread (first 6 components): between-people", np.round(model["between"][:6], 2).tolist(),
      "within-recording", np.round(model["within"][:6], 2).tolist(), flush=True)
print("[model] event phases:", {k_: round(v, 3) for k_, v in insts[0]["event_phases"].items()}, flush=True)
for d in mm.describe(model):
    print("[model] " + json.dumps(d), flush=True)
