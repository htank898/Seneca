import bpy, math, os, sys
from mathutils import Vector
s = bpy.context.scene
rig = bpy.data.objects["RIG-Snow"]
P = rig.pose.bones["Properties"]
for side in ("left", "right"):
    P[f"ik_{side}_upperarm"] = 0.0
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: s.render.engine = eng; break
    except TypeError: pass
s.eevee.taa_render_samples = 16
s.render.resolution_x = s.render.resolution_y = 400
cam = bpy.data.objects["Camera"]
cam.location = (0.0, -1.0, 1.62); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 85
pb = rig.pose.bones
def reset():
    for b in pb:
        b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0)
probes = [
    ("neutral", {}),
    ("lid_y-", {"MSTR-Eyelid_Upper.L": ("location", (0, -0.012, 0)), "MSTR-Eyelid_Upper.R": ("location", (0, -0.012, 0))}),
    ("lid_y+", {"MSTR-Eyelid_Upper.L": ("location", (0, 0.012, 0)), "MSTR-Eyelid_Upper.R": ("location", (0, 0.012, 0))}),
    ("brow_y+", {"MSTR-Eyebrow.L": ("location", (0, 0.012, 0)), "MSTR-Eyebrow.R": ("location", (0, 0.012, 0))}),
    ("brow_x+", {"MSTR-Eyebrow.L": ("location", (0.012, 0, 0)), "MSTR-Eyebrow.R": ("location", (0.012, 0, 0))}),
    ("lips_y+", {"ACT-Lips_Corner.L": ("location", (0, 0.012, 0)), "ACT-Lips_Corner.R": ("location", (0, 0.012, 0))}),
    ("lips_x+", {"ACT-Lips_Corner.L": ("location", (0.012, 0, 0)), "ACT-Lips_Corner.R": ("location", (0.012, 0, 0))}),
    ("jaw_x+", {"Jaw": ("rotation_euler", (math.radians(15), 0, 0))}),
    ("jaw_x-", {"Jaw": ("rotation_euler", (math.radians(-15), 0, 0))}),
    ("eyes_x", {"TGT-Eyes": ("location", (0.15, 0, 0.0))}),
    ("lowlid_y+", {"MSTR-Eyelid_Lower.L": ("location", (0, 0.01, 0)), "MSTR-Eyelid_Lower.R": ("location", (0, 0.01, 0))}),
    ("mouth_y+", {"MSTR-Mouth": ("location", (0, 0.01, 0))}),
]
out = os.path.abspath("../frames/probe")
os.makedirs(out, exist_ok=True)
for name, sets in probes:
    reset()
    for bn, (prop, val) in sets.items():
        setattr(pb[bn], prop, val)
    s.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
print("PROBES", [p[0] for p in probes])
