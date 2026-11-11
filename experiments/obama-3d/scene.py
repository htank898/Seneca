"""Blender scene: loads .cache/rig.npz, rigs it, keys a performance, renders.

    Blender -b -P scene.py -- --stills 0,62,134     # a few test frames -> frames/still_####.png
    Blender -b -P scene.py -- --anim                 # the whole performance -> frames/f_####.png
    Blender -b -P scene.py -- --save                 # also write .cache/obama.blend to open in the UI
"""
import math, os, sys
import bpy
from mathutils import Matrix
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(HERE, ".cache")
OUT = os.path.join(HERE, "frames")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
R = np.load(os.path.join(C, "rig.npz"))
FPS, FRAMES = 24, 288
S = 1 / 1000

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ------------------------------------------------------------------ materials
def emissive(name, image=None, color=None, alpha=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(C, image))
        tex.interpolation = "Cubic"
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*color, 1)
    if alpha:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m

def mouth_material():
    """Near-black cavity with a dim tongue low and back; darkest right under the upper teeth."""
    m = bpy.data.materials.new("mouth"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (0, 0, 0.75); mp.inputs["Scale"].default_value = (0.9, 1, 1.6)
    gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.012, 0.004, 0.004, 1)
    ramp.color_ramp.elements[1].position = 0.8; ramp.color_ramp.elements[1].color = (0.20, 0.055, 0.05, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], gr.inputs["Vector"])
    nt.links.new(gr.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m

# ------------------------------------------------------------------ the person mesh
basis = R["basis"]
faces = [tuple(f) for f in R["quads"]] + [tuple(f) for f in R["tris"]]
me = bpy.data.meshes.new("person")
me.from_pydata(basis.tolist(), [], faces)
me.update()
uv = me.uv_layers.new(name="photo")
li = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", li)
uv.data.foreach_set("uv", R["uv"][li].ravel())
person = bpy.data.objects.new("person", me)
scene.collection.objects.link(person)
me.materials.append(emissive("photo", "fg.png", alpha=True))

person.shape_key_add(name="Basis")
keys = {}
for name in ("blinkA", "blinkB", "browUp", "smileRelax", "jawOpen", "breath"):
    sk = person.shape_key_add(name=name, from_mix=False)
    sk.data.foreach_set("co", R["key_" + name].ravel())
    keys[name] = sk

# ------------------------------------------------------------------ head bone
arm = bpy.data.armatures.new("rig")
rig = bpy.data.objects.new("rig", arm)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
hb = arm.edit_bones.new("head")
piv = R["head_pivot"]
hb.head = piv; hb.tail = (piv[0], piv[1], piv[2] + 0.3); hb.roll = 0
bpy.ops.object.mode_set(mode="OBJECT")
vg = person.vertex_groups.new(name="head")
w = R["w_head"]
for val in np.unique(np.round(w, 3)):
    if val > 0:
        vg.add(np.nonzero(np.round(w, 3) == val)[0].tolist(), float(val), "REPLACE")
mod = person.modifiers.new("rig", "ARMATURE"); mod.object = rig
pose_head = rig.pose.bones["head"]
pose_head.rotation_mode = "XYZ"

# Mouth cavity: a dark, flattened ellipsoid behind the teeth, carried by the head.
cx, cy, cz, crx, cry = R["cavity"]
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(cx, cy, cz))
cav = bpy.context.active_object; cav.name = "mouth"
cav.scale = (crx, 0.04, cry)
cav.data.materials.append(mouth_material())
cav.parent = rig; cav.parent_type = "BONE"; cav.parent_bone = "head"
# Bone parenting anchors at the bone's tail, so include the bone length.
cav.matrix_parent_inverse = (rig.matrix_world @ pose_head.matrix @ Matrix.Translation((0, pose_head.bone.length, 0))).inverted()

# ------------------------------------------------------------------ background plate
W, H, ucen, vcen = R["photo_size"]
k = float(R["bg_scale"][0]) * S
bme = bpy.data.meshes.new("bg")
corners = [(0, 0), (W, 0), (W, H), (0, H)]
bme.from_pydata([((u - ucen) * k, 0.9, (vcen - v) * k) for u, v in corners], [], [(0, 1, 2, 3)])
buv = bme.uv_layers.new(name="photo")
for loop, (u, v) in zip(bme.loops, corners):
    buv.data[loop.index].uv = (u / W, 1 - v / H)
bg = bpy.data.objects.new("bg", bme); scene.collection.objects.link(bg)
bme.materials.append(emissive("bg", "bg.png"))

# ------------------------------------------------------------------ camera
dist, crop_h = (float(x) for x in R["camera"])
cam_data = bpy.data.cameras.new("cam")
cam_data.sensor_fit = "VERTICAL"; cam_data.sensor_height = 24
cam_data.lens = dist / crop_h * 24
cam_data.clip_start = 0.1; cam_data.clip_end = 100
cam = bpy.data.objects.new("cam", cam_data); scene.collection.objects.link(cam)
cam.location = (0, -dist, 0); cam.rotation_euler = (math.pi / 2, 0, 0)
scene.camera = cam

# ------------------------------------------------------------------ performance
def ease(a, b, x):
    k = min(1, max(0, (x - a) / (b - a)))
    return k * k * (3 - 2 * k)

def track(keys_):
    """Smooth (ease in/out) interpolation through (frame, value) keys -> value per frame."""
    out = []
    for f in range(FRAMES + 1):
        for (f0, v0), (f1, v1) in zip(keys_, keys_[1:]):
            if f0 <= f <= f1:
                out.append(v0 + (v1 - v0) * ease(f0, f1, f)); break
        else:
            out.append(keys_[-1][1])
    return out

yaw   = track([(0, 0), (30, 0), (62, 17), (84, 15), (110, 6), (150, 4), (178, -13), (215, -11), (245, -2), (288, 0)])
pitch = track([(0, 0), (30, 0), (62, -3), (84, -2), (100, 1), (118, 6), (140, 5), (155, 0), (166, -5), (176, 1),
               (186, -4), (198, 0), (288, 0)])
roll  = track([(0, 0), (70, 0), (92, 5), (110, 4), (140, -2), (170, 0), (210, -3), (250, 0), (288, 0)])
brow  = track([(0, 0), (80, 0), (90, 1), (108, 1), (118, 0.1), (222, 0), (228, 1), (238, 1), (248, 0), (288, 0)])
relax = track([(0, 0), (80, 0), (95, 0.7), (108, 0.7), (116, 0), (190, 0), (205, 0.5), (240, 0.5), (270, 0), (288, 0)])
jaw   = track([(0, 0), (112, 0), (118, 0.55), (122, 0.35), (126, 0.65), (130, 0.4), (134, 0.7), (138, 0.42),
               (142, 0.6), (150, 0.25), (160, 0), (288, 0)])
squint = track([(0, 0), (112, 0), (118, 0.35), (148, 0.35), (160, 0), (288, 0)])
BLINKS = [18, 76, 166, 214, 260, 267]
def blink(f):
    v = 0.0
    for b in BLINKS:
        u = f - b
        if -2 <= u <= 0: v = max(v, (u + 2) / 2)          # close in 2 frames
        elif 0 < u <= 4: v = max(v, 1 - u / 4)            # open in 4
    return v

for f in range(FRAMES + 1):
    scene.frame_set(f)
    pose_head.rotation_euler = (math.radians(pitch[f]), math.radians(yaw[f]), math.radians(roll[f]))
    pose_head.keyframe_insert("rotation_euler", frame=f)
    b = max(blink(f), squint[f])
    for name, val in (("blinkA", b), ("blinkB", b), ("browUp", brow[f]), ("smileRelax", relax[f]),
                      ("jawOpen", jaw[f]), ("breath", 0.5 - 0.5 * math.cos(2 * math.pi * f / 96))):
        keys[name].value = val
        keys[name].keyframe_insert("value", frame=f)
    cam.location = (0, -dist * (1 - 0.05 * ease(0, FRAMES, f)), 0)   # slow push-in
    cam.keyframe_insert("location", frame=f)

# ------------------------------------------------------------------ render settings
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"; prefs.get_devices()
    for dev in prefs.devices: dev.use = True
    scene.cycles.device = "GPU"
except Exception:
    scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.cycles.filter_width = 1.0
scene.cycles.max_bounces = 0
scene.cycles.transparent_max_bounces = 8
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.resolution_x, scene.render.resolution_y = 864, 1080
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, FRAMES - 1
scene.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True)

if "--save" in argv:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(C, "obama.blend"))
if "--stills" in argv:
    for f in map(int, argv[argv.index("--stills") + 1].split(",")):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(OUT, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
if "--anim" in argv:
    scene.render.filepath = os.path.join(OUT, "f_")
    scene.render.use_overwrite = False      # resumable: the Metal kernel cache occasionally crashes Blender
    bpy.ops.render.render(animation=True)
