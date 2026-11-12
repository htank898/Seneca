"""Render one pitch from the windup: the ball is held in the throwing hand until release, then flies
to home plate (18.44 m) on a ballistic path with backspin.

  node ../blender/scripts/blender.mjs templates/pitch_render.py --pypath ../animate/scripts --out pitch.mp4 \\
       [--model pitch_model.json] [--seed 1] [--wobble 0.5] [--speed 30] [--cam side|cf] [--fps 120]
       [--res 1280x720] [--frames a-b] [--preview]

--speed is ball speed in m/s (30 ~ 67 mph; MLB fastballs are ~40-45). --cam side frames the delivery and
release; --cam cf is a broadcast-style centre-field telephoto. Render at --fps 120 and play back at
30 for 4x slow motion. Prints "[pitch] {...}": event frames and ball release point / flight time.
"""
import json, math
import bkit as k, rig, bodies, motionmodel as mm, pitch
k.reset(); k.render_settings(res=(1280, 720), motion_blur=False)
fps = int(k.arg("fps", 120))
sc = k.scene(); sc.render.fps = fps
model = mm.load(k.arg("model", "pitch_model.json"))
mo, ev = pitch.generate(model, fps=fps, seed=int(k.arg("seed", 1)), wobble=float(k.arg("wobble", 0.5)))
arm = rig.armature(mo)
bodies.body(arm, build=float(k.arg("build", 1.0)))
rig.retarget(arm, mo, locomotion="root", heading=0.0, foot_ik=True)
pitch.field()
b, info = pitch.ball(arm, ev, speed=float(k.arg("speed", 30)))
print("[pitch] " + json.dumps({"events": ev, "ball": info, "frames": [sc.frame_start, sc.frame_end]}), flush=True)
k.world("#9fb7cc", 1.0)
k.light("SUN", loc=(-5, -3, 9), look_at=(0, 2, 0), power=4.0, color="#fff4e2")
if k.arg("cam", "side") == "side":
    cam = k.camera(loc=(-4.6, 0.9, 1.25), lens=35); cam.rotation_euler = (math.radians(88), 0, math.radians(-90))
else:  # broadcast-style: behind the pitcher, raised, telephoto, looking at the plate
    cam = k.camera(loc=(0.9, -38.0, 5.5), look_at=(0, 9.0, 1.0), lens=160)
k.finish()
