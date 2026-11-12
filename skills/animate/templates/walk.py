"""Make a body walk: a standard gait from the open mocap library on a code-generated skinned human,
side-on tracking camera, gait metrics printed. The fundamentals test bench.

  node ../blender/scripts/blender.mjs templates/walk.py --pypath ../animate/scripts --preview --out walk.mp4 \\
       [--src walk|slow|brisk|cmu:<trial>|100style:<Style>] [--label "Proud"] [--stride 1.0] [--cadence 1.0]
       [--arms 1.0] [--build 1.0] [--sec 4.2] [--fps 24] [--body body|mannequin]
  (paths relative to skills/; copy the template next to your outputs if you like)

Prints "[gait] {...}": knee range, speed, hip bob, contact %, cycle straightness.
Healthy everyday walking: knee ~0-70 deg, 1.0-1.5 m/s, hip bob 2-5 cm, contact 50-62% (per foot).
"""
import json, math
import bkit as k, rig, gait, bodies
k.reset(); k.render_settings(res=(960, 720), motion_blur=False)
fps = int(k.arg("fps", 24))
sc = k.scene(); sc.render.fps = fps
src, label = k.arg("src", "walk"), k.arg("label", k.arg("src", "walk"))
stride, arms, cad = float(k.arg("stride", 1)), float(k.arg("arms", 1)), float(k.arg("cadence", 1))
mo, gains = gait.walk(src, seconds=float(k.arg("sec", 4.2)), cadence=cad, stride=stride, arm_swing=arms, fps=fps)
arm = rig.armature(mo)
(bodies.mannequin(arm) if k.arg("body") == "mannequin" else bodies.body(arm, build=float(k.arg("build", 1.0))))
d = (mo["root"][-1] - mo["root"][0]).xy
heading = -math.degrees(math.atan2(d.y, d.x))  # travel screen-right (+X)
rig.retarget(arm, mo, locomotion="footlock" if gains else "root", gains=gains, heading=heading)
arm.hide_viewport = False
con = json.loads(arm["contacts"]); rows = []
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    P = lambda b, t=False: arm.matrix_world @ (arm.pose.bones[b].tail if t else arm.pose.bones[b].head)
    th = (P("thigh.L", True) - P("thigh.L")).normalized(); sh = (P("shin.L", True) - P("shin.L")).normalized()
    rows.append((math.degrees(th.angle(sh)), P("hips")))
kn = [r[0] for r in rows]; zs = sorted(r[1].z for r in rows)
print("[gait] " + json.dumps({"label": label, "cycle": mo.get("cycle"), "straight": mo.get("straightness"),
      "knee": [round(min(kn)), round(max(kn))],
      "speed_m_s": round((rows[-1][1] - rows[0][1]).xy.length / (len(rows) / fps), 2),
      "hip_bob_cm": round((zs[int(len(zs)*.95)] - zs[int(len(zs)*.05)]) * 100, 1),
      "contact_pct": round(100 * sum(con["L"]) / len(con["L"]))}), flush=True)
arm.hide_viewport = True
k.world("#c3ccd3", 0.9); k.plane(300, mat=k.material("#9a958f", roughness=0.9))
lm = k.material("#7d7873", roughness=0.9)
for i in range(-80, 81):  # 0.5 m floor lines: make foot sliding visible
    k.cube(1.0, loc=(i * 0.5, 0, 0.002), scale=(0.012, 40, 0.004), mat=lm, name=f"gx{i}")
k.light("SUN", loc=(-4, -6, 9), look_at=(0, 0, 0), power=3.5)
cam = k.camera(loc=(0, -3.6, 1.0), lens=40); cam.rotation_euler = (math.radians(87), 0, 0)
rig.follow_camera(cam, arm, axes="XY")
t = k.text(label, size=0.075, align="LEFT", extrude=0.0, bevel=0.0, mat=k.material("#1d1f24"))
t.parent = cam; t.location = (-0.63, 0.43, -1.5); t.visible_shadow = False
k.finish()
