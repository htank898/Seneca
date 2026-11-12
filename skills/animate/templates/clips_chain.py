"""Chain ready-made clips into one performance: walk in, then a few actions, on a studio backdrop.

  node ../blender/scripts/blender.mjs templates/clips_chain.py --pypath ../animate/scripts --out chain.mp4 \\
       [--shot "Walk_Loop:2.6,Idle_Talking_Loop,Yes,Punch_Jab,Idle_Loop"] [--mode body|native]
       [--blend 0.3] [--fps 24] [--color "#e0512f"] [--build 1.0]
  (paths relative to skills/; run  node animate/scripts/clips-fetch.mjs quaternius  once first)

--mode body   (default) the clips drive Seneca's skinned body through rig.retarget(quality=True):
              the same route as any character attached to the standard rig. Prints [checks].
--mode native the pack's own mannequin plays the clips untouched (NLA cross-fades, no retarget).
Every clip in a native shot must come from one pack (UAL1 or UAL2).
List clips: clips.find("walk"), or python: import clips; print(sorted(clips.catalog())).
"""
import math

from mathutils import Vector

import bkit as k
import bodies
import checks
import clips
import rig

fps = int(k.arg("fps", 24))
mode = k.arg("mode", "body")
default = ("Walk_Loop:2.6,Idle_Talking_Loop,Dance_Loop*3,Punch_Jab,Idle_Loop" if mode == "native"   # one pack
           else "Walk_Loop:2.6,Idle_Talking_Loop,Yes,Punch_Jab,Idle_Loop")                         # mixes UAL1 + UAL2
shot = [s.strip() for s in k.arg("shot", default).split(",")]
blend = float(k.arg("blend", 0.3))

k.reset()
k.frames(1, 2, fps=fps)
k.render_settings(res=(1280, 720))
k.world("#1d1f24", 0.3)
k.backdrop("#ece7df", width=30, depth=16)
skin = k.material(k.arg("color", "#e0512f"), roughness=0.4, coat=0.3)

if mode == "native":
    arm, mesh = clips.native(shot, blend=blend)
    arm.rotation_euler.z = math.radians(90)      # authored facing -Y: turn to travel screen-right
    k.assign(mesh, skin)
    sc = k.scene()
    path = []
    for f in (sc.frame_start, sc.frame_end):
        sc.frame_set(f)
        path.append(arm.matrix_world @ arm.pose.bones[0].head)
    subject = [mesh]
else:
    mo = clips.sequence(shot, blend=blend, fps=fps)
    arm = rig.armature(mo)
    body = bodies.body(arm, build=float(k.arg("build", 1.0)))
    k.assign(body, skin)
    roots = rig.retarget(arm, mo, locomotion="root", heading=90, quality=True)
    path = [roots[0], roots[-1]]
    sc = k.scene()
    checks.report(body, arm, mo=mo, frames=(sc.frame_start, sc.frame_end))
    subject = [body]

# frame the whole path: centred on where the performer ends up, the walk-in starting near the edge
start, end = Vector((path[0].x, path[0].y, 0)), Vector((path[-1].x, path[-1].y, 0))
marks = [k.cube(0.5, loc=tuple(p + Vector((0, 0, 0.95))), scale=(1, 1, 3.8)) for p in (start, end)]
k.studio_lights(target=marks)
span = max(1.2, (end - start).length)
k.camera(loc=(end.x - 0.15 * span, end.y - 3.2 - 1.6 * span, 1.5), look_at=(end.x - 0.15 * span, end.y, 0.95),
         lens=40, fit=marks, margin=1.25)
import bpy
for m in marks:
    bpy.data.objects.remove(m)
k.finish()
