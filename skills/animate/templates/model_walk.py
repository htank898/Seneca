"""Walk from a statistical gait model: the average person, or a new individual, each step a bit different.

  node ../blender/scripts/blender.mjs templates/model_walk.py --pypath ../animate/scripts --preview --out avg.mp4 \\
       [--model walk_model.json] [--person 7] [--pv 1.0] [--wobble auto|0.5] [--seed 1] [--sec 6] [--fps 24]
       [--label "..."] [--build 1.0]

--person N draws individual N from the between-people spread (omit for the average person);
--wobble scales the step-to-step variation (default auto: stride-time CV 2.5%).
Prints "[gait] {...}" including stride_cv_pct and per-cycle durations.
"""
import json, math
import bkit as k, rig, bodies, motionmodel as mm
k.reset(); k.render_settings(res=(int(k.arg("w", 960)), int(k.arg("h", 720))), motion_blur=False)
fps = int(k.arg("fps", 24))
sc = k.scene(); sc.render.fps = fps
model = mm.load(k.arg("model", "walk_model.json"))
wob = k.arg("wobble", "auto")
wobble = None if wob == "auto" else float(wob)
seed, sec = int(k.arg("seed", 1)), float(k.arg("sec", 6))
who = None if k.arg("person") is None else mm.person(model, seed=int(k.arg("person")), variety=float(k.arg("pv", 1.0)))
mo = mm.generate(model, seconds=sec, fps=fps, person_z=who, wobble=wobble, seed=seed)
arm = rig.armature(mo)
bodies.body(arm, build=float(k.arg("build", 1.0)))
d = (mo["root"][-1] - mo["root"][0]).xy
rig.retarget(arm, mo, locomotion="root", heading=-math.degrees(math.atan2(d.y, d.x)))
arm.hide_viewport = False
con = json.loads(arm["contacts"]); rows = []
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    P = lambda b, t=False: arm.matrix_world @ (arm.pose.bones[b].tail if t else arm.pose.bones[b].head)
    th = (P("thigh.L", True) - P("thigh.L")).normalized(); sh = (P("shin.L", True) - P("shin.L")).normalized()
    rows.append((math.degrees(th.angle(sh)), P("hips")))
kn = [r[0] for r in rows]; zs = sorted(r[1].z for r in rows)
cd = mo["cycle_durations"]
cv = (sum((x - sum(cd) / len(cd)) ** 2 for x in cd) / len(cd)) ** 0.5 / (sum(cd) / len(cd)) if len(cd) > 1 else None
print("[gait] " + json.dumps({"label": k.arg("label", ""), "person": k.arg("person"), "wobble": round(mo["wobble"], 3),
      "seed": seed, "stride_cv_pct": round(100 * cv, 1) if cv is not None else None, "cycle_s": cd,
      "knee": [round(min(kn)), round(max(kn))],
      "speed_m_s": round((rows[-1][1] - rows[0][1]).xy.length / (len(rows) / fps), 2),
      "hip_bob_cm": round((zs[int(len(zs)*.95)] - zs[int(len(zs)*.05)]) * 100, 1),
      "contact_pct": round(100 * sum(con["L"]) / len(con["L"]))}), flush=True)
arm.hide_viewport = True
k.world("#c3ccd3", 0.9); k.plane(400, mat=k.material("#9a958f", roughness=0.9))
lm = k.material("#7d7873", roughness=0.9)
for i in range(-120, 121):
    k.cube(1.0, loc=(i * 0.5, 0, 0.002), scale=(0.012, 40, 0.004), mat=lm, name=f"gx{i}")
k.light("SUN", loc=(-4, -6, 9), look_at=(0, 0, 0), power=3.5)
cam = k.camera(loc=(0, -4.2, 0.95), lens=38); cam.rotation_euler = (math.radians(87), 0, 0)
rig.follow_camera(cam, arm, axes="XY")
if k.arg("label"):
    t = k.text(k.arg("label"), size=0.075, align="LEFT", extrude=0.0, bevel=0.0, mat=k.material("#1d1f24"))
    t.parent = cam; t.location = (-0.63, 0.43, -1.5); t.visible_shadow = False
k.finish()
