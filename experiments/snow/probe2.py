import bpy, math, os
from mathutils import Euler
s = bpy.context.scene
rig = bpy.data.objects["RIG-Snow"]; pb = rig.pose.bones
P = pb["Properties"]; P["ik_left_upperarm"] = 0.0; P["ik_right_upperarm"] = 0.0
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: s.render.engine = eng; break
    except TypeError: pass
s.eevee.taa_render_samples = 16
s.render.resolution_x = s.render.resolution_y = 500
cam = bpy.data.objects["Camera"]
def wpose(b, rx=0, ry=0, rz=0):
    b.rotation_mode = "QUATERNION"
    M = b.bone.matrix_local.to_3x3()
    R = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix()
    b.rotation_quaternion = (M.inverted() @ R @ M).to_quaternion()
def reset():
    for b in pb:
        b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0)
def face():
    cam.location = (0.0, -0.75, 1.6); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 135
def body():
    cam.location = (0.0, -3.2, 1.1); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 50
L, R = "ACT-Lips_Corner.L", "ACT-Lips_Corner.R"
probes = [
    ("smile_a", face, {L: (0.01, 0.015), R: (-0.01, 0.015)}),
    ("smile_b", face, {L: (-0.01, 0.015), R: (0.01, 0.015)}),
    ("smile_c", face, {L: (0, 0.025), R: (0, 0.025)}),
    ("frown", face, {L: (0, -0.015), R: (0, -0.015)}),
    ("blink", face, {"MSTR-Eyelid_Upper.L": (0, -0.025), "MSTR-Eyelid_Upper.R": (0, -0.025)}),
    ("brow_up", face, {"MSTR-Eyebrow.L": (0, 0.02), "MSTR-Eyebrow.R": (0, 0.02)}),
    ("arms", body, "arms"),
    ("arms2", body, "arms2"),
]
out = os.path.abspath("../frames/probe")
for name, cfn, sets in probes:
    reset(); cfn()
    if sets == "arms":
        wpose(pb["FK-UpperArm.L"], 0, 72, 0); wpose(pb["FK-UpperArm.R"], 0, -72, 0)
    elif sets == "arms2":
        wpose(pb["FK-UpperArm.L"], 0, -72, 0); wpose(pb["FK-UpperArm.R"], 0, 72, 0)
    else:
        for bn, (x, y) in sets.items(): pb[bn].location = (x, y, 0)
    s.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
