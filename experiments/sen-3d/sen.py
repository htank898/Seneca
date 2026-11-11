"""Sen, Seneca's messenger, as a rigged 3D character built entirely from code.

Matches the 2D Sen in examples/video/character-demo: slate cap with an envelope badge,
yellow jacket, red neckerchief, satchel, big round eyes, rosy cheeks. Cel-shaded with
inverted-hull outlines so it sits next to the flat 2D work.

    Blender -b -P sen.py -- --stills 0,40,75 [--scene hello]   # test frames -> frames/still_####.png
    Blender -b -P sen.py -- --anim [--scene hello]             # whole scene -> frames/f_####.png
    Blender -b -P sen.py -- --save                             # .cache/sen.blend to open in the UI
"""
import json, math, os, sys
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames")
CACHE = os.path.join(HERE, ".cache")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection

# ------------------------------------------------------------------ palette (from the 2D Sen)
SKIN   = (0.94, 0.70, 0.55)
CAP    = (0.27, 0.37, 0.50)
JACKET = (0.97, 0.76, 0.14)
RED    = (0.86, 0.17, 0.13)
PANTS  = (0.13, 0.14, 0.18)
SHOE   = (0.10, 0.10, 0.12)
SLATE  = (0.22, 0.29, 0.38)
WHITE  = (0.98, 0.98, 0.97)
INK    = (0.09, 0.10, 0.13)
BLUSH  = (0.96, 0.52, 0.48)
WALL   = (0.88, 0.91, 0.92)
LINE   = (0.10, 0.11, 0.15)

def srgb(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

# ------------------------------------------------------------------ materials: 3-step cel shading
_mats = {}
def toon(color, name=None, flat=False):
    key = (color, flat)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name or f"toon_{len(_mats)}")
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    base = srgb(color)
    if flat:
        em.inputs["Color"].default_value = (*base, 1)
    else:
        diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
        s2r = nt.nodes.new("ShaderNodeShaderToRGB")
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        e = ramp.color_ramp.elements
        e[0].position = 0.0; e[0].color = (0.70, 0.70, 0.74, 1)       # shadow, slightly cool
        e[1].position = 0.22; e[1].color = (1, 1, 1, 1)
        hi = e.new(0.75); hi.color = (1.08, 1.08, 1.06, 1)              # small highlight band
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        mul.inputs[6].default_value = (*base, 1)
        nt.links.new(diff.outputs[0], s2r.inputs[0]); nt.links.new(s2r.outputs[0], bw.inputs[0])
        nt.links.new(bw.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], mul.inputs[7])
        nt.links.new(mul.outputs[2], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    _mats[key] = m
    return m

def outline_mat():
    if "outline" in _mats:
        return _mats["outline"]
    m = bpy.data.materials.new("outline"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*srgb(LINE), 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = True
    _mats["outline"] = m
    return m

def outline(obj, width=0.006):
    obj.data.materials.append(outline_mat())
    sol = obj.modifiers.new("outline", "SOLIDIFY")
    sol.thickness = width; sol.offset = 1; sol.use_flip_normals = True
    sol.material_offset = len(obj.data.materials) - 1
    sol.use_rim = False

# ------------------------------------------------------------------ primitives
def finish(obj, color, line=0.006, flat=False, smooth=True):
    obj.data.materials.append(toon(color, flat=flat))
    if smooth:
        obj.data.shade_smooth()
    if line:
        outline(obj, line)
    return obj

def sphere(name, loc, r, scale=(1, 1, 1), color=SKIN, line=0.006, rot=(0, 0, 0), flat=False):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = scale
    return finish(o, color, line, flat)

def cylinder(name, loc, r, depth, scale=(1, 1, 1), color=SKIN, line=0.006, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, vertices=48, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = scale
    bev = o.modifiers.new("bevel", "BEVEL"); bev.width = min(r, depth) * 0.25; bev.segments = 4
    return finish(o, color, line)

def box(name, loc, size, color, line=0.005, rot=(0, 0, 0), bevel=0.01):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bev = o.modifiers.new("bevel", "BEVEL"); bev.width = bevel; bev.segments = 4
    return finish(o, color, line)

def torus(name, loc, R, r, color, rot=(0, 0, 0), scale=(1, 1, 1), line=0.005):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot,
                                     major_segments=64, minor_segments=16)
    o = bpy.context.active_object; o.name = name; o.scale = scale
    return finish(o, color, line)

def limb(name, a, b, r, color, line=0.006):
    """Capsule from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a + b) / 2, vertices=40)
    o = bpy.context.active_object; o.name = name
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return finish(o, color, line)

# ------------------------------------------------------------------ proportions (metres; chibi: big head)
HC = Vector((0, 0, 0.88))      # head centre
R = 0.20                       # head radius
def on_head(x, z, out=0.0):
    """Point on the head sphere (front side) at local x, height z above HC, plus outward offset."""
    y = -math.sqrt(max(R * R - x * x - z * z, 0))
    n = Vector((x, y, z)).normalized()
    return HC + n * (R + out), n
def face_rot(n):
    return n.to_track_quat("-Y", "Z").to_euler()

# ------------------------------------------------------------------ rig
arm_data = bpy.data.armatures.new("rig")
rig = bpy.data.objects.new("rig", arm_data); col.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
def bone(name, head, tail, parent=None):
    b = arm_data.edit_bones.new(name); b.head = head; b.tail = tail
    if parent: b.parent = arm_data.edit_bones[parent]
    return b
bone("root", (0, 0, 0), (0, 0, 0.1))
bone("spine", (0, 0, 0.28), (0, 0, 0.62), "root")
bone("head", (0, 0, 0.66), (0, 0, 1.05), "spine")
SH = {"L": Vector((0.15, 0, 0.575)), "R": Vector((-0.15, 0, 0.575))}
for s, sx in (("L", 1), ("R", -1)):
    el = SH[s] + Vector((sx * 0.045, 0, -0.135))
    wr = el + Vector((sx * 0.03, 0, -0.125))
    bone(f"upper.{s}", SH[s], el, "spine")
    bone(f"fore.{s}", el, wr, f"upper.{s}")
    bone(f"hand.{s}", wr, wr + Vector((sx * 0.01, 0, -0.06)), f"fore.{s}")
bpy.ops.object.mode_set(mode="OBJECT")
for pb in rig.pose.bones:
    pb.rotation_mode = "QUATERNION"

def pose(pb, rx=0.0, ry=0.0, rz=0.0):
    """Rotate a pose bone by world-axis angles (degrees; character faces -Y), relative to its rest pose."""
    from mathutils import Euler
    M = pb.bone.matrix_local.to_3x3()
    Rw = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix()
    pb.rotation_quaternion = (M.inverted() @ Rw @ M).to_quaternion()

def attach(obj, bone_name):
    pb = rig.pose.bones[bone_name]
    obj.parent = rig; obj.parent_type = "BONE"; obj.parent_bone = bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))).inverted()
    return obj

def empty(name, loc, parent_bone=None, parent=None):
    e = bpy.data.objects.new(name, None); e.location = loc; col.objects.link(e)
    if parent_bone: attach(e, parent_bone)
    if parent: e.parent = parent; e.matrix_parent_inverse = parent.matrix_world.inverted()
    return e

def child(obj, parent):
    bpy.context.view_layer.update()
    obj.parent = parent; obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return obj

# ------------------------------------------------------------------ head
attach(sphere("head", HC, R, scale=(1, 0.97, 1), color=SKIN, line=0.007), "head")
for s, sx in (("L", 1), ("R", -1)):
    attach(sphere(f"ear.{s}", HC + Vector((sx * 0.195, 0.01, -0.015)), 0.048, scale=(0.55, 0.8, 1), color=SKIN), "head")
p, n = on_head(0, -0.025, -0.004)
attach(sphere("nose", p, 0.022, scale=(1, 0.8, 0.85), color=(0.92, 0.62, 0.48)), "head")
for s, sx in (("L", 1), ("R", -1)):
    p, n = on_head(sx * 0.115, -0.045, -0.004)
    attach(sphere(f"blush.{s}", p, 0.032, scale=(1, 0.25, 0.65), color=BLUSH, line=0, rot=face_rot(n), flat=True), "head")

# Eyes: blink empty (scaled in z) > white + gaze empty > iris + highlight.
EYES = {}
for s, sx in (("L", 1), ("R", -1)):
    p, n = on_head(sx * 0.072, 0.022, -0.022)
    blink = empty(f"blink.{s}", p, "head")
    white = child(sphere(f"eye.{s}", p, 0.048, scale=(0.9, 0.75, 1.1), color=WHITE, line=0.006), blink)
    gaze = empty(f"gaze.{s}", p, parent=blink)
    ip = p + n * 0.030
    child(sphere(f"iris.{s}", ip, 0.024, scale=(1, 0.5, 1.15), color=INK, line=0, rot=face_rot(n), flat=True), gaze)
    child(sphere(f"spark.{s}", ip + n * 0.009 + Vector((0.008, 0, 0.012)), 0.007, color=WHITE, line=0, flat=True), gaze)
    EYES[s] = (blink, gaze)    # no brows: the cap brim covers them, as in the 2D design

# Mouth: a decal on the face whose shape keys are the viseme set.
VIS = {   #  width, height, smile-curve   (fractions of MOUTH_R)
    "smile": (0.50, 0.20, 0.38), "rest": (0.40, 0.05, 0.25), "MBP": (0.36, 0.012, 0.15),
    "AI": (0.50, 0.62, 0.18), "E": (0.58, 0.34, 0.24), "O": (0.32, 0.50, 0.02), "U": (0.24, 0.28, 0.0),
    "FV": (0.46, 0.10, 0.12), "L": (0.46, 0.42, 0.14), "etc": (0.46, 0.30, 0.15),
}
MOUTH_R, MOUTH_Z = 0.11, -0.085
def mouth_mesh():
    rings, segs = 10, 40
    verts2d = [(0.0, 0.0)]
    for i in range(1, rings + 1):
        rr = i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs
            verts2d.append((rr * math.cos(a), rr * math.sin(a)))
    faces = []
    for j in range(segs):
        faces.append((0, 1 + j, 1 + (j + 1) % segs))
    for i in range(rings - 1):
        for j in range(segs):
            a = 1 + i * segs + j; b = 1 + i * segs + (j + 1) % segs
            faces.append((a, a + segs, b + segs, b))
    return verts2d, faces
V2, F2 = mouth_mesh()
def mouth_shape(w, h, c):
    pts = []
    for s_, t_ in V2:
        x = w * s_ * MOUTH_R
        z = MOUTH_Z + h * t_ * MOUTH_R * 0.55 + c * (s_ * s_) * MOUTH_R * 0.35
        p, _ = on_head(x, z, 0.0015)
        pts.append(p)
    return pts
me = bpy.data.meshes.new("mouth")
me.from_pydata([tuple(p) for p in mouth_shape(*VIS["smile"])], [], F2)
uvl = me.uv_layers.new(name="uv")
for poly in me.polygons:
    for li in poly.loop_indices:
        s_, t_ = V2[me.loops[li].vertex_index]
        uvl.data[li].uv = ((s_ + 1) / 2, (t_ + 1) / 2)
mouth = bpy.data.objects.new("mouth", me); col.objects.link(mouth)
m = bpy.data.materials.new("mouth"); m.use_nodes = True
nt = m.node_tree; nt.nodes.clear()
uvn = nt.nodes.new("ShaderNodeUVMap"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
e = ramp.color_ramp.elements
e[0].position = 0.0; e[0].color = (*srgb((0.93, 0.45, 0.45)), 1)       # tongue
e[1].position = 0.36; e[1].color = (*srgb((0.30, 0.06, 0.07)), 1)      # mouth
t = e.new(0.84); t.color = (*srgb(WHITE), 1)                           # upper teeth
em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(uvn.outputs[0], sep.inputs[0]); nt.links.new(sep.outputs[1], ramp.inputs[0])
nt.links.new(ramp.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
me.materials.append(m)
outline(mouth, 0.004)
attach(mouth, "head")
mouth.shape_key_add(name="Basis")
MKEYS = {}
for name, wh in VIS.items():
    sk = mouth.shape_key_add(name=name, from_mix=False)
    for i, p in enumerate(mouth_shape(*wh)):
        sk.data[i].co = p
    MKEYS[name] = sk

# Cap: dome, brim, band, envelope badge.
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.212, location=HC + Vector((0, 0.01, 0.035)), segments=48, ring_count=24)
cap = bpy.context.active_object; cap.name = "cap"
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.bisect(plane_co=HC + Vector((0, 0, 0.05)), plane_no=(0, 0.25, 1), clear_inner=True, use_fill=True)
bpy.ops.object.mode_set(mode="OBJECT")
finish(cap, CAP, 0.007)
attach(cap, "head")
brim = cylinder("brim", HC + Vector((0, -0.13, 0.072)), 0.175, 0.016, scale=(1, 0.72, 1), color=CAP, rot=(math.radians(-8), 0, 0))
attach(brim, "head")
attach(torus("band", HC + Vector((0, 0.01, 0.06)), 0.205, 0.012, SLATE, rot=(math.radians(-14), 0, 0)), "head")
p = HC + Vector((0, -0.185, 0.135)); n = (p - HC).normalized()
attach(cylinder("badge", p, 0.036, 0.01, color=JACKET, rot=face_rot(n)), "head")
env = box("envelope", p + n * 0.007, (0.034, 0.004, 0.022), WHITE, line=0.003, rot=face_rot(n), bevel=0.002)
attach(env, "head")

# ------------------------------------------------------------------ body
attach(cylinder("neck", (0, 0, 0.665), 0.05, 0.07, color=SKIN), "spine")
attach(sphere("torso", (0, 0, 0.44), 1.0, scale=(0.165, 0.135, 0.205), color=JACKET, line=0.007), "spine")
attach(cylinder("hem", (0, 0, 0.275), 0.158, 0.05, scale=(1, 0.82, 1), color=SLATE), "spine")
attach(box("zip", (0, -0.133, 0.42), (0.008, 0.01, 0.26), (0.85, 0.62, 0.10), line=0, bevel=0.003), "spine")
attach(box("pocket", (0.075, -0.128, 0.36), (0.06, 0.012, 0.05), (0.93, 0.70, 0.12), line=0.004, bevel=0.005,
           rot=(math.radians(-8), 0, math.radians(-25))), "spine")
attach(torus("scarf", (0, -0.005, 0.625), 0.078, 0.026, RED, scale=(1, 0.92, 0.7)), "spine")
attach(sphere("knot", (0, -0.09, 0.61), 0.03, scale=(1.1, 0.8, 0.9), color=RED), "spine")
for sx in (1, -1):
    attach(limb(f"tail.{sx}", (sx * 0.008, -0.1, 0.6), (sx * 0.035, -0.13, 0.47), 0.016, RED), "spine")

# Satchel: strap across the chest from the right shoulder, bag at the left hip.
strap = torus("strap", (0.0, -0.0, 0.45), 0.205, 0.011, SLATE, rot=(0, math.radians(38), 0), scale=(0.85, 0.75, 1.15))
attach(strap, "spine")
attach(box("bag", (-0.2, -0.04, 0.3), (0.06, 0.13, 0.11), SLATE, bevel=0.015), "spine")
attach(box("flap", (-0.232, -0.04, 0.33), (0.008, 0.135, 0.07), (0.17, 0.23, 0.31), line=0.004, bevel=0.006), "spine")
attach(box("letter", (-0.2, -0.02, 0.37), (0.04, 0.07, 0.05), WHITE, line=0.003, bevel=0.003,
           rot=(math.radians(10), 0, 0)), "spine")

# Arms: sleeves on upper/fore bones, round cuffs, mitten hands.
for s, sx in (("L", 1), ("R", -1)):
    ub, fb, hb = (arm_data.bones[f"{k}.{s}"] for k in ("upper", "fore", "hand"))
    attach(sphere(f"shoulder.{s}", ub.head_local, 0.048, color=JACKET), f"upper.{s}")
    attach(limb(f"upperarm.{s}", ub.head_local, ub.tail_local, 0.042, JACKET), f"upper.{s}")
    attach(sphere(f"elbow.{s}", ub.tail_local, 0.042, color=JACKET), f"upper.{s}")
    attach(limb(f"forearm.{s}", fb.head_local, fb.tail_local - (fb.tail_local - fb.head_local) * 0.1, 0.039, JACKET), f"fore.{s}")
    attach(torus(f"cuff.{s}", fb.tail_local - (fb.tail_local - fb.head_local) * 0.12, 0.036, 0.011, (0.93, 0.70, 0.12),
                 rot=(fb.tail_local - fb.head_local).to_track_quat("Z", "Y").to_euler()), f"fore.{s}")
    hc = hb.head_local + (hb.tail_local - hb.head_local) * 0.45
    attach(sphere(f"hand.{s}", hc, 0.043, scale=(0.85, 0.7, 1), color=SKIN), f"hand.{s}")
    attach(sphere(f"thumb.{s}", hc + Vector((-sx * 0.012, -0.03, 0.012)), 0.017, color=SKIN), f"hand.{s}")

# Legs and shoes.
for sx in (1, -1):
    attach(limb(f"leg.{sx}", (sx * 0.065, 0, 0.29), (sx * 0.068, 0, 0.06), 0.048, PANTS), "root")
    attach(sphere(f"shoe.{sx}", (sx * 0.07, -0.025, 0.035), 1.0, scale=(0.062, 0.095, 0.042), color=SHOE), "root")

# ------------------------------------------------------------------ set: wall, floor, window, mail slots
def flatbox(name, loc, size, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = size
    o.data.materials.append(toon(color, flat=True)); return o
flatbox("floor", (0, 0.3, -0.05), (6, 3, 0.1), (0.80, 0.83, 0.85))
flatbox("wall", (0, 0.75, 1.5), (6, 0.1, 3.2), WALL)
flatbox("skirting", (0, 0.69, 0.04), (6, 0.02, 0.08), (0.70, 0.74, 0.78))
shadow = sphere("shadow", (0, 0, 0.001), 1.0, scale=(0.26, 0.17, 0.002), color=(0.66, 0.70, 0.74), line=0, flat=True)

box("winframe", (-0.62, 0.69, 1.1), (0.5, 0.03, 0.5), (0.47, 0.55, 0.64), line=0.004, bevel=0.01)
flatbox("glass", (-0.62, 0.675, 1.1), (0.43, 0.01, 0.43), (0.72, 0.84, 0.94))
flatbox("mullion", (-0.62, 0.668, 1.1), (0.02, 0.01, 0.43), (0.47, 0.55, 0.64))
flatbox("transom", (-0.62, 0.668, 1.1), (0.43, 0.01, 0.02), (0.47, 0.55, 0.64))
box("slots", (0.62, 0.68, 0.42), (0.42, 0.04, 0.26), (0.62, 0.67, 0.71), line=0.004, bevel=0.01)
for i in range(3):
    for j in range(2):
        box(f"mail{i}{j}", (0.49 + i * 0.13, 0.655, 0.36 + j * 0.12), (0.1, 0.01, 0.075), WHITE, line=0.002, bevel=0.004)
        box(f"stamp{i}{j}", (0.52 + i * 0.13, 0.648, 0.38 + j * 0.12), (0.018, 0.004, 0.018),
            (RED, JACKET, CAP)[(i + j) % 3], line=0, bevel=0)

# ------------------------------------------------------------------ light, camera, world
sun = bpy.data.lights.new("key", "SUN"); sun.energy = 3.2; sun.angle = math.radians(4)
key = bpy.data.objects.new("key", sun); col.objects.link(key)
key.rotation_euler = (math.radians(48), math.radians(-28), math.radians(-35))
world = bpy.data.worlds.new("world"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (*srgb((0.86, 0.89, 0.92)), 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
cam_data = bpy.data.cameras.new("cam"); cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data); col.objects.link(cam)
cam.location = (0.42, -2.05, 0.82)
target = empty("look", (0.02, 0, 0.62))
tc = cam.constraints.new("TRACK_TO"); tc.target = target; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
scene.camera = cam

# ------------------------------------------------------------------ performance
FPS = 30
SCENES = json.load(open(os.path.join(HERE, "scenes.json")))
SC = SCENES[arg("--scene", "hello")]
SC["visemes"] = os.path.join(HERE, SC["visemes"])
VIS_DATA = json.load(open(SC["visemes"]))
vs = next(s for s in VIS_DATA["scenes"] if s["id"] == SC["id"])
LEAD = SC.get("lead", 0.5)
DUR = LEAD + vs["duration"] + SC.get("tail", 1.2)
FRAMES = int(round(DUR * FPS))

def ss(a, b, x):
    k = min(1, max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k)
def keys(pts, t):
    """Eased interpolation through (time, value) pairs."""
    if t <= pts[0][0]: return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1: return v0 + (v1 - v0) * ss(t0, t1, t)
    return pts[-1][1]
def bump(t, c, w):
    return math.exp(-((t - c) / w) ** 2)

def viseme_weights(t):
    """Blend of mouth shapes at time t (seconds into the voice), with 50 ms crossfades."""
    if t < 0 or t > vs["duration"]:
        return {"smile": 1.0}
    w = {}
    X = 0.05
    for c in vs["cues"]:
        a = ss(c["t0"] - X, c["t0"] + X, t) * (1 - ss(c["t1"] - X, c["t1"] + X, t))
        if a > 0:
            w[c["v"]] = w.get(c["v"], 0) + a
    tot = sum(w.values()) or 1
    w = {k: v / tot for k, v in w.items()}
    # Ease back into the smile across pauses and at the ends.
    edge = ss(-0.15, 0.05, t) * (1 - ss(vs["duration"] - 0.1, vs["duration"] + 0.15, t))
    w = {k: v * edge for k, v in w.items()}
    w["smile"] = w.get("smile", 0) + (1 - edge)
    if "rest" in w:
        w["smile"] += w.pop("rest") * 0.6; w["rest"] = 0
    return w

def word_stress(t):
    """Small head dips on stressed words."""
    v = 0
    for wd in vs["words"]:
        if wd["text"].strip(".,!?").lower() in SC.get("stress", []):
            v += bump(t, wd["t0"] + 0.08, 0.12)
    return v

up = {s: rig.pose.bones[f"upper.{s}"] for s in "LR"}
fo = {s: rig.pose.bones[f"fore.{s}"] for s in "LR"}
ha = {s: rig.pose.bones[f"hand.{s}"] for s in "LR"}
head_b, spine_b = rig.pose.bones["head"], rig.pose.bones["spine"]

for f in range(FRAMES + 1):
    t = f / FPS; tv = t - LEAD
    # Wave with the left arm (viewer's right): raise, wave from the elbow, lower.
    raise_ = keys([(0.15, 0), (0.6, 1), (2.6, 1), (3.2, 0.25), (3.7, 0)], t)
    wave = math.sin(2 * math.pi * 2.6 * (t - 0.6)) * ss(0.55, 0.8, t) * (1 - ss(2.3, 2.7, t))
    pose(up["L"], 0, -140 * raise_, 0)
    pose(fo["L"], -10 * raise_, 25 * raise_ + 28 * wave, 0)
    pose(ha["L"], 0, 10 * wave, 0)
    # Right arm: relaxed, settles a little, then a small "for Seneca" present gesture.
    pres = bump(tv, 3.3, 0.45)
    pose(up["R"], -40 * pres, 8 + 18 * pres + 2 * math.sin(t * 2), 0)
    pose(fo["R"], -55 * pres, 0, -15 * pres)
    # Body: breathing bob and a lean into the wave.
    pose(spine_b, 1.5 * math.sin(t * 2.4), -4 * raise_, 0)
    spine_b.location = (0, 0.004 * math.sin(t * 2.4), 0)
    # Head: tilt toward the wave, look at camera, nod on stressed words.
    nod = word_stress(tv)
    pose(head_b, 1 + 4 * nod + 2 * math.sin(t * 1.3),
         6 * raise_ - 3 * pres,
         -4 * math.sin(t * 0.9) + 5 * pres)
    # Eyes: blinks and a small glance.
    bl = 0
    for b in SC.get("blinks", []):
        bl = max(bl, 1 - min(1, abs(t - b) / 0.07) if abs(t - b) < 0.07 else 0)
    glance = keys([(0, 0), (1.6, 0), (1.75, 1), (2.1, 1), (2.25, 0), (9, 0)], t)
    for s in "LR":
        blink, gaze = EYES[s]
        blink.scale = (1, 1, max(0.08, 1 - bl)); blink.keyframe_insert("scale", frame=f)
        gaze.rotation_euler = (math.radians(-6 * glance), 0, math.radians(14 * glance)); gaze.keyframe_insert("rotation_euler", frame=f)
    # Mouth.
    wts = viseme_weights(tv)
    for name, sk in MKEYS.items():
        sk.value = wts.get(name, 0.0); sk.keyframe_insert("value", frame=f)
    for pb in list(up.values()) + list(fo.values()) + list(ha.values()) + [head_b, spine_b]:
        pb.keyframe_insert("rotation_quaternion", frame=f)
    spine_b.keyframe_insert("location", frame=f)

# ------------------------------------------------------------------ render
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng; break
    except TypeError:
        continue
scene.eevee.taa_render_samples = 32
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x = scene.render.resolution_y = 1080
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, FRAMES - 1
scene.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
print(f"[sen] scene {SC['id']}: {FRAMES} frames, engine {scene.render.engine}")

if "--save" in argv:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, "sen.blend"))
if "--stills" in argv:
    for f in map(int, arg("--stills").split(",")):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(OUT, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
if "--anim" in argv:
    scene.render.filepath = os.path.join(OUT, "f_")
    scene.render.use_overwrite = False
    bpy.ops.render.render(animation=True)
