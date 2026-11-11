"""Golden hour: an 8-second acting beat for Snow (Blender Studio, CC-BY) rendered headless.

    Blender -b -Y .cache/Snow/snow_v4.2.blend -P shot.py -- --stills 0,60,110 [--eevee] [--small]
    Blender -b -Y .cache/Snow/snow_v4.2.blend -P shot.py -- --anim

-Y keeps the rig's bundled UI script (cloudrig.py) from running; the rig's drivers are all simple
expressions, so it deforms correctly without it.

Snow Rig (CC) Blender Foundation | studio.blender.org
"""
import glob, math, os, sys
import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
s = bpy.context.scene
rig = bpy.data.objects["RIG-Snow"]
pb = rig.pose.bones
FPS, SECONDS = 24, 8
FRAMES = FPS * SECONDS

# ------------------------------------------------------------------ rig setup: FK arms, clean pose
P = pb["Properties"]
P["ik_left_upperarm"] = 0.0; P["ik_right_upperarm"] = 0.0
pb["Properties_Character_Snow"]["Quality"] = 2          # render-quality geometry
for b in pb:
    b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0)

def wrot(b, rx=0.0, ry=0.0, rz=0.0):
    """Rotate a pose bone by world-axis angles in degrees (character faces -Y), relative to rest."""
    b.rotation_mode = "QUATERNION"
    M = b.bone.matrix_local.to_3x3()
    R = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix()
    b.rotation_quaternion = (M.inverted() @ R @ M).to_quaternion()

def wloc(b, offset):
    """Move a pose bone by a world-space offset (metres), for bones whose parents are unrotated."""
    b.location = b.bone.matrix_local.to_3x3().inverted() @ Vector(offset)

# ------------------------------------------------------------------ lighting: golden hour
for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(o)
W = glob.glob("/Applications/Blender.app/Contents/Resources/*/datafiles/studiolights/world")[0]
world = s.world; world.use_nodes = True
nt = world.node_tree; nt.nodes.clear()
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(os.path.join(W, "sunset.exr"))
bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 0.9
out = nt.nodes.new("ShaderNodeOutputWorld")
mp.inputs["Rotation"].default_value = (0, 0, math.radians(-95))    # hazy sea and pink sky behind him
SUN_DIR = Vector((0.45, 1.0, 0.35)).normalized()                     # implied low sun: behind, camera-right
nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], env.inputs[0])
nt.links.new(env.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])

def area(name, loc, target, size, energy, color):
    d = bpy.data.lights.new(name, "AREA"); d.size = size; d.energy = energy; d.color = color
    o = bpy.data.objects.new(name, d); s.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o
area("key", (-1.1, -1.2, 1.85), (0, -0.05, 1.6), 1.4, 80, (1.0, 0.80, 0.62))     # warm bounce, camera left
rim_pos = Vector((0, 0, 1.6)) + SUN_DIR * 1.6 + Vector((0, 0, 0.35))
area("rim", rim_pos, (0, -0.02, 1.62), 0.35, 190, (1.0, 0.70, 0.42))           # the low sun, behind
area("rim2", (-0.8, 1.0, 1.8), (0, 0, 1.55), 0.6, 120, (1.0, 0.75, 0.5))        # soft kicker, other side
area("fill", (1.3, -1.0, 1.4), (0, 0, 1.55), 2.0, 10, (0.70, 0.80, 1.0))         # cool sky fill

# ------------------------------------------------------------------ camera: 85 mm, shallow focus
cam = s.camera
cam.data.lens = 85
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.0
EYE = Vector((0, -0.14, 1.635))
def place_camera(t):
    push = 1 - 0.06 * (0.5 - 0.5 * math.cos(math.pi * t / SECONDS))      # slow push-in
    drift = Vector((0.004 * math.sin(t * 0.9), 0.0, 0.003 * math.sin(t * 1.3 + 1)))
    base = Vector((0.32, -1.38, 1.67)) - EYE
    cam.location = EYE + base * push + drift
    look = Vector((0.035, -0.05, 1.545)) + drift * 0.5
    cam.rotation_euler = (look - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (EYE - cam.location).length

# ------------------------------------------------------------------ performance
def ss(a, b, x):
    k = min(1, max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k)
def keys(pts, t):
    if t <= pts[0][0]: return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1: return v0 + (v1 - v0) * ss(t0, t1, t)
    return pts[-1][1]
def blink(t, at, close=0.07, hold=0.03, open_=0.12):
    v = 0
    for b in at:
        if b - close <= t <= b: v = max(v, ss(b - close, b, t))
        elif b < t <= b + hold: v = 1
        elif b + hold < t <= b + hold + open_: v = max(v, 1 - ss(b + hold, b + hold + open_, t))
    return v

BLINKS = [1.55, 4.9, 6.35]
EYE_TARGET_DIST = 1.0
TGT = pb["TGT-Eyes"]
TGT_REST = TGT.bone.head_local.copy()
GAZE = [TGT_REST]

def aim_eyes():
    """Put the eye target at a world point (rig sits at the origin), whatever its parents are doing."""
    bpy.context.view_layer.update()
    TGT.matrix = Matrix.Translation(GAZE[0]) @ TGT.bone.matrix_local.to_3x3().to_4x4()

def frame(t):
    # Gaze: 0 = down-left (thinking), 1 = into the lens, 2 = off to camera-right.
    look_cam = keys([(0, 0), (1.5, 0), (2.0, 1), (5.6, 1), (6.1, 2), (8, 2)], t)
    down = (0.24, -0.15, -0.62)      # world offsets for the eye target at its rest distance
    away = (-0.22, 0.0, 0.02)
    to_cam = (cam.location - EYE).normalized() * EYE_TARGET_DIST + EYE - TGT_REST
    if look_cam <= 1:
        g = Vector(down).lerp(Vector(to_cam), look_cam)
    else:
        g = Vector(to_cam).lerp(Vector(away), look_cam - 1)
    g += Vector((0.006 * math.sin(t * 7.1), 0, 0.004 * math.sin(t * 5.3)))   # micro-saccade drift
    GAZE[0] = TGT_REST + g

    # Head and neck lead the eyes a beat late, then settle; a small tilt as the smile arrives.
    yaw = keys([(0, 14), (1.6, 14), (2.5, 2), (5.6, 1), (6.4, -10), (8, -11)], t)
    pitch = keys([(0, 20), (1.6, 19), (2.6, 1), (4.4, -2), (5.0, 1), (5.6, 0), (6.4, 3), (8, 3)], t)
    tilt = keys([(0, -3), (2.4, -3), (3.6, 4), (5.6, 3), (6.6, -2), (8, -2)], t)
    laugh = keys([(0, 0), (4.0, 0), (4.25, 1), (4.45, 0.4), (4.65, 0.8), (5.0, 0), (8, 0)], t)
    wrot(pb["FK-Neck"], pitch * 0.4 + 1.5 * laugh, 0, yaw * 0.35)
    wrot(pb["FK-Head"], pitch * 0.6 - 3 * laugh, tilt, yaw * 0.65)
    breathe = math.sin(2 * math.pi * t / 3.6)
    wrot(pb["FK-Chest"], -1.2 * breathe - 2 * laugh, 0, yaw * 0.12)
    wrot(pb["FK-UpperArm.L"], 0, 74, -4); wrot(pb["FK-UpperArm.R"], 0, -74, 4)
    wrot(pb["FK-Forearm.L"], -10, 0, 0); wrot(pb["FK-Forearm.R"], -10, 0, 0)

    # Face.
    smile = keys([(0, 0), (2.6, 0), (3.8, 0.55), (4.2, 0.9), (5.2, 0.85), (6.3, 0.45), (8, 0.4)], t)
    brow = keys([(0, -0.2), (1.6, -0.2), (2.2, 0.6), (3.0, 0.25), (4.3, 0.5), (5.5, 0.1), (8, 0.0)], t)
    b = blink(t, BLINKS)
    look_cam = keys([(0, 0), (1.5, 0), (2.0, 1), (5.6, 1), (6.1, 2), (8, 2)], t)
    squint = 0.6 * smile + 0.3 * laugh
    for side, sx in (("L", 1), ("R", -1)):
        lid_down = 0.009 * (1 - min(1, look_cam))          # lids follow a downward gaze
        pb[f"MSTR-Eyelid_Upper.{side}"].location = (0, -0.025 * b - 0.004 * squint + 0.002 * brow - lid_down, 0)
        pb[f"MSTR-Eyelid_Lower.{side}"].location = (0, 0.007 * squint, 0)
        pb[f"MSTR-Eyebrow.{side}"].location = (0, 0.012 * brow, 0)
        pb[f"ACT-Lips_Corner.{side}"].location = (-sx * 0.007 * smile, 0.016 * smile, 0)
    wrot(pb["Jaw"], 0, 0, 0)
    pb["Jaw"].rotation_mode = "XYZ"; pb["Jaw"].rotation_euler = (math.radians(4 * smile + 9 * laugh), 0, 0)

def key_all(f):
    for b in pb:
        if b.rotation_mode == "QUATERNION":
            b.keyframe_insert("rotation_quaternion", frame=f)
        else:
            b.keyframe_insert("rotation_euler", frame=f)
        b.keyframe_insert("location", frame=f)
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.dof.keyframe_insert("focus_distance", frame=f)

ANIMATED = ["TGT-Eyes", "FK-Neck", "FK-Head", "FK-Chest", "FK-UpperArm.L", "FK-UpperArm.R", "FK-Forearm.L",
            "FK-Forearm.R", "Jaw"] + [f"{n}.{sd}" for n in ("MSTR-Eyelid_Upper", "MSTR-Eyelid_Lower", "MSTR-Eyebrow",
                                                             "ACT-Lips_Corner") for sd in "LR"]
for f in range(FRAMES + 1):
    t = f / FPS
    place_camera(t); frame(t); aim_eyes()
    for n in ANIMATED:
        b = pb[n]
        b.keyframe_insert("rotation_quaternion" if b.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
        b.keyframe_insert("location", frame=f)
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.dof.keyframe_insert("focus_distance", frame=f)

# ------------------------------------------------------------------ render
if "--eevee" in argv:
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try: s.render.engine = eng; break
        except TypeError: pass
    s.eevee.taa_render_samples = 64
else:
    s.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"; prefs.get_devices()
    for d in prefs.devices: d.use = True
    s.cycles.device = "GPU"; s.cycles.samples = 96; s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
s.view_settings.view_transform = "AgX"; s.view_settings.look = "AgX - Medium High Contrast"
s.render.resolution_x, s.render.resolution_y = (960, 540) if "--small" in argv else (1920, 1080)
s.render.resolution_percentage = 100
s.render.fps = FPS; s.frame_start, s.frame_end = 0, FRAMES - 1
s.render.use_motion_blur = True; s.render.motion_blur_shutter = 0.5
s.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True)
if "--stills" in argv:
    for f in map(int, argv[argv.index("--stills") + 1].split(",")):
        s.frame_set(f)
        s.render.filepath = os.path.join(OUT, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
if "--anim" in argv:
    s.render.filepath = os.path.join(OUT, "f_")
    s.render.use_overwrite = False
    bpy.ops.render.render(animation=True)
