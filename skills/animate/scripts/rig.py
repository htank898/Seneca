"""rig: a standard humanoid armature, retargeted from pose.py's motion.json. Runs inside Blender.

    import bkit as k, rig
    mo  = rig.load_motion("motion.json")
    arm = rig.armature(mo)                    # T-pose skeleton sized to the actor (scale= to resize)
    rig.retarget(arm, mo)                     # keys every frame; sets the scene's frame range + fps
    rig.follow_camera(cam, arm)               # optional: camera tracks the hips like a dolly

The skeleton (names are what bodies.py and adapt's parts.py attach to):
    hips > spine > chest > neck > head
    chest > shoulder.L/R > upper_arm.L/R > forearm.L/R > hand.L/R
    hips  > hip.L/R > thigh.L/R > shin.L/R > foot.L/R

Rest pose: T-pose standing on the floor at the origin, facing -Y (toward a camera at -Y), so the
character's left (.L) is +X. Bone lengths are fixed, so limbs never stretch: each frame only the
bones' *directions* come from the landmarks. Torso/head take their twist from the hip, shoulder
and ear lines; limbs are swing-only (no twist), which keeps mechanical parts from popping.

Locomotion (retarget(locomotion=...)):
    "footlock" (default) the planted foot stays put and the body moves past it, so a walk travels
                         even when the source camera tracked the actor
    "root"               copy the recorded root path (BVH / mocap / world-grounded capture)
    "none"               in place (treadmill), e.g. to place the travel yourself
Ground (retarget(ground=...)):
    "lock" (default)     the lowest foot point sits on z=0 every frame (smoothed)
    "free"               keeps the capture's vertical motion (jumps), floor set from the median stance
"""
import json
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

# Landmark indices (MediaPipe Pose)
NOSE, L_EAR, R_EAR = 0, 7, 8
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR = 11, 12, 13, 14, 15, 16
L_PI, R_PI, L_IN, R_IN = 17, 18, 19, 20
L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 23, 24, 25, 26, 27, 28
L_HEEL, R_HEEL, L_TOE, R_TOE = 29, 30, 31, 32

# name, parent, mode ("root" | "twist" | "swing")
BONES = [
    ("hips", None, "root"), ("spine", "hips", "twist"), ("chest", "spine", "twist"),
    ("neck", "chest", "twist"), ("head", "neck", "twist"),
    ("shoulder.L", "chest", "swing"), ("upper_arm.L", "shoulder.L", "swing"),
    ("forearm.L", "upper_arm.L", "swing"), ("hand.L", "forearm.L", "swing"),
    ("shoulder.R", "chest", "swing"), ("upper_arm.R", "shoulder.R", "swing"),
    ("forearm.R", "upper_arm.R", "swing"), ("hand.R", "forearm.R", "swing"),
    ("hip.L", "hips", "swing"), ("thigh.L", "hip.L", "swing"), ("shin.L", "thigh.L", "swing"),
    ("foot.L", "shin.L", "swing"),
    ("hip.R", "hips", "swing"), ("thigh.R", "hip.R", "swing"), ("shin.R", "thigh.R", "swing"),
    ("foot.R", "shin.R", "swing"),
]
PARENT = {n: p for n, p, _ in BONES}
MODE = {n: m for n, _, m in BONES}
NON_DEFORM = ("shoulder.L", "shoulder.R", "hip.L", "hip.R")


def load_motion(path):
    with open(path) as f:
        mo = json.load(f)
    mo["world"] = [[Vector(p) for p in fr] for fr in mo["world"]]
    return mo


# ---------------------------------------------------------------- landmark targets
def _mid(P, *idx):
    v = Vector((0, 0, 0))
    for i in idx:
        v += P[i]
    return v / len(idx)


def targets(P):
    """Per-bone desired direction (unit-ish vectors, Blender axes) and twist hints for one frame."""
    hip_c, sh_c, ear_c = _mid(P, L_HIP, R_HIP), _mid(P, L_SH, R_SH), _mid(P, L_EAR, R_EAR)
    up = sh_c - hip_c
    hip_side = P[L_HIP] - P[R_HIP]
    sh_side = P[L_SH] - P[R_SH]
    d = {
        "hips": up, "spine": up, "chest": up,
        "neck": ear_c - sh_c, "head": ear_c - sh_c,
        "shoulder.L": P[L_SH] - sh_c, "shoulder.R": P[R_SH] - sh_c,
        "upper_arm.L": P[L_EL] - P[L_SH], "forearm.L": P[L_WR] - P[L_EL],
        "hand.L": _mid(P, L_PI, L_IN) - P[L_WR],
        "upper_arm.R": P[R_EL] - P[R_SH], "forearm.R": P[R_WR] - P[R_EL],
        "hand.R": _mid(P, R_PI, R_IN) - P[R_WR],
        "hip.L": P[L_HIP] - hip_c, "hip.R": P[R_HIP] - hip_c,
        "thigh.L": P[L_KN] - P[L_HIP], "shin.L": P[L_AN] - P[L_KN], "foot.L": P[L_TOE] - P[L_AN],
        "thigh.R": P[R_KN] - P[R_HIP], "shin.R": P[R_AN] - P[R_KN], "foot.R": P[R_TOE] - P[R_AN],
    }
    twist = {"hips": hip_side, "spine": hip_side.lerp(sh_side, 0.5), "chest": sh_side,
             "neck": (P[L_EAR] - P[R_EAR]).lerp(sh_side, 0.5), "head": P[L_EAR] - P[R_EAR]}
    return d, twist


def stance_pitch(mo, side="L"):
    """Foot slope (degrees below horizontal, ankle -> toe) when the performer stands flat: the median
    over the frames where that ankle is lowest. Used as the rest angle so 'flat' in the data is
    flat on our skeleton."""
    ank, toe = (27, 31) if side == "L" else (28, 32)
    W = mo["world"]
    z = sorted(range(len(W)), key=lambda i: W[i][ank].z)
    pick = z[:max(3, len(z) // 7)]
    ps = []
    for i in pick:
        v = W[i][toe] - W[i][ank]
        ps.append(math.degrees(math.atan2(-v.z, max(v.xy.length, 1e-6))))
    ps.sort()
    return ps[len(ps) // 2]


def rest_targets(L, pitch=26.6):
    """The same structure for the rest T-pose, built from bone lengths L (metres)."""
    up, X, F = Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, -1, 0))
    d = {"hips": up, "spine": up, "chest": up, "neck": up, "head": up,
         "shoulder.L": X, "upper_arm.L": X, "forearm.L": X, "hand.L": X,
         "shoulder.R": -X, "upper_arm.R": -X, "forearm.R": -X, "hand.R": -X,
         "hip.L": X, "hip.R": -X,
         "thigh.L": -up, "shin.L": -up, "foot.L": (F * math.cos(math.radians(pitch)) - up * math.sin(math.radians(pitch))),
         "thigh.R": -up, "shin.R": -up, "foot.R": (F * math.cos(math.radians(pitch)) - up * math.sin(math.radians(pitch)))}
    twist = {k: X for k in ("hips", "spine", "chest", "neck", "head")}
    return d, twist


def lengths_from(mo, scale=1.0):
    m = mo["lengths"]
    s = scale
    head = m["neck"] * 1.25
    return {
        "hips": m["torso"] * 0.30 * s, "spine": m["torso"] * 0.35 * s, "chest": m["torso"] * 0.35 * s,
        "neck": m["neck"] * 0.9 * s, "head": head * s,
        "shoulder.L": m["shoulder_width"] / 2 * s, "shoulder.R": m["shoulder_width"] / 2 * s,
        "upper_arm.L": m["upper_arm"] * s, "upper_arm.R": m["upper_arm"] * s,
        "forearm.L": m["forearm"] * s, "forearm.R": m["forearm"] * s,
        "hand.L": max(m["hand"] * 1.8, 0.08) * s, "hand.R": max(m["hand"] * 1.8, 0.08) * s,
        "hip.L": m["hip_width"] / 2 * s, "hip.R": m["hip_width"] / 2 * s,
        "thigh.L": m["thigh"] * s, "thigh.R": m["thigh"] * s,
        "shin.L": m["shin"] * s, "shin.R": m["shin"] * s,
        "foot.L": m["foot"] * s, "foot.R": m["foot"] * s,
    }


# ---------------------------------------------------------------- frames
def _frame(y, x_hint):
    """Orthonormal 3x3 with Y along y and X as close as possible to x_hint."""
    y = y.normalized()
    x = x_hint - y * x_hint.dot(y)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)) if abs(y.x) < 0.9 else Vector((0, 0, 1))
        x = x - y * x.dot(y)
    x.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def _swing(parent_rot, y):
    """Parallel-transport the parent's frame onto direction y (no twist about the bone)."""
    py = parent_rot.col[1].copy()
    q = py.rotation_difference(y.normalized())
    return q.to_matrix() @ parent_rot


# Hinge limbs: the bone's roll follows the bend plane of its child (elbow / knee), so the mesh's
# own crease bends where the joint actually bends. (child, torso bone giving "front", flex sign:
# elbows flex toward the front, knees toward the back.)
HINGE = {"upper_arm.L": ("forearm.L", "chest", 1.0), "upper_arm.R": ("forearm.R", "chest", 1.0),
         "thigh.L": ("shin.L", "hips", -1.0), "thigh.R": ("shin.R", "hips", -1.0)}
_SIN_BENT = math.sin(math.radians(30))


def _hinge_rot(y, child, front, transported):
    """Frame for a hinge limb: X = the joint's hinge axis. From the real bend when bent; from the
    anatomical bend direction (front/back) when nearly straight; the transported frame last."""
    y = y.normalized()
    xh = y.cross(child.normalized()) if child.length > 1e-9 else Vector()
    xa = y.cross(front)
    wh = min(1.0, xh.length / _SIN_BENT)
    wh = wh * wh * (3 - 2 * wh)
    x = Vector()
    if xh.length > 1e-6:
        x += xh.normalized() * wh
    if xa.length > 1e-6:
        x += xa.normalized() * (1 - wh) * xa.length
    x += transported.col[0] * 0.15
    if x.length < 1e-3:
        return transported
    return _frame(y, x)


def solve(dirs, twist, L, root_head, hinge=False):
    """Fixed-length FK: armature-space 4x4 for every bone, given directions and hints.
    hinge=True: upper arms and thighs take their roll from the elbow / knee bend (see HINGE)."""
    out = {}
    for name, parent, mode in BONES:
        y = dirs[name]
        if y.length < 1e-6:
            y = Vector((0, 0, 1))
        if parent is None:
            head = root_head.copy()
            rot = _frame(y, twist[name])
        else:
            pm = out[parent]
            head = pm.to_translation() + pm.col[1].to_3d().normalized() * L[parent]
            if name in ("hip.L", "hip.R"):
                head = pm.to_translation()  # hips head = pelvis centre
            rot = _frame(y, twist[name]) if mode == "twist" else _swing(pm.to_3x3(), y)
            lvl = twist.get(name) if name in ("foot.L", "foot.R") else None
            if isinstance(lvl, float) and lvl > 0:
                # planted foot: sole level side to side (no edge digging into the floor)
                xl = y.normalized().cross(Vector((0, 0, 1)))
                if xl.length > 1e-3:
                    xl.normalize()
                    xt = rot.col[0]
                    if xl.dot(xt) < 0:
                        xl.negate()
                    rot = _frame(y, xt.lerp(xl, float(lvl)))
            if hinge and name in HINGE:
                child, torso, sign = HINGE[name]
                front = out[torso].col[2].to_3d().normalized() * sign
                rot = _hinge_rot(y, dirs[child], front, rot)
        m = rot.to_4x4()
        m.translation = head
        out[name] = m
    return out


# ---------------------------------------------------------------- armature
def armature(mo, scale=1.0, name="Rig", show=False):
    """Build the T-pose armature sized from motion.json's measured lengths, feet on z=0."""
    L = lengths_from(mo, scale)
    try:
        pitch = (stance_pitch(mo, "L") + stance_pitch(mo, "R")) / 2
        pitch = max(5.0, min(45.0, pitch))
    except Exception:
        pitch = 26.6
    d, t = rest_targets(L, pitch)
    rest = solve(d, t, L, Vector((0, 0, 0)))
    # lift so the lowest foot point is on the floor
    low = min(min((m.to_translation() + m.col[1].to_3d() * L[n]).z, m.to_translation().z)
              for n, m in rest.items() if n.startswith(("foot", "shin")))
    lift = Vector((0, 0, -low))
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.display_type = "STICK"
    obj.show_in_front = True
    obj.hide_render = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for bname, parent, _ in BONES:
        eb = data.edit_bones.new(bname)
        m = rest[bname].copy()
        m.translation += lift
        eb.head = m.to_translation()
        eb.tail = eb.head + m.col[1].to_3d() * L[bname]
        eb.align_roll(m.col[2].to_3d())
        if parent:
            eb.parent = ebs[parent]
            eb.use_connect = False
        ebs[bname] = eb
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.hide_viewport = not show
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    obj["rig_lengths"] = json.dumps(L)
    obj["rig_foot_pitch"] = pitch
    obj["rig_lift"] = lift.z
    return obj


def armature_from_joints(J, name="Rig", show=False):
    """The same skeleton, fitted to a MESH instead of a performer: its rest pose is the mesh's own
    pose (an A-pose is fine), its bone lengths the mesh's own, so retarget() drives a skinned
    character without stretching it. J is character-3d's landmarks.json "joints" (metres, facing
    -Y, left = +X, feet on z=0): shoulder/elbow/wrist/hand_tip.L|R, hip/knee/ankle/toe.L|R,
    neck, head_top. retarget() keys rotations relative to each bone's own rest matrix, so the rest
    pose need not be a T-pose."""
    v = lambda key: Vector(J[key])
    hip_c = (v("hip.L") + v("hip.R")) / 2
    sh_c = (v("shoulder.L") + v("shoulder.R")) / 2
    torso = sh_c - hip_c
    pts = {"neck": (sh_c, v("neck")), "head": (v("neck"), v("head_top"))}
    for s in ("L", "R"):
        pts.update({
            f"shoulder.{s}": (sh_c, v(f"shoulder.{s}")),
            f"upper_arm.{s}": (v(f"shoulder.{s}"), v(f"elbow.{s}")),
            f"forearm.{s}": (v(f"elbow.{s}"), v(f"wrist.{s}")),
            f"hand.{s}": (v(f"wrist.{s}"), v(f"hand_tip.{s}")),
            f"hip.{s}": (hip_c, v(f"hip.{s}")),
            f"thigh.{s}": (v(f"hip.{s}"), v(f"knee.{s}")),
            f"shin.{s}": (v(f"knee.{s}"), v(f"ankle.{s}")),
            f"foot.{s}": (v(f"ankle.{s}"), v(f"toe.{s}")),
        })
    L = {"hips": torso.length * 0.30, "spine": torso.length * 0.35, "chest": torso.length * 0.35}
    d = {"hips": torso, "spine": torso, "chest": torso}
    for bname, (a, b) in pts.items():
        L[bname] = max((b - a).length, 1e-3)
        d[bname] = b - a
    twist = {k: Vector((1, 0, 0)) for k in ("hips", "spine", "chest", "neck", "head")}
    rest = solve(d, twist, L, hip_c)
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.display_type = "STICK"
    obj.show_in_front = True
    obj.hide_render = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for bname, parent, _ in BONES:
        eb = data.edit_bones.new(bname)
        m = rest[bname]
        eb.head = m.to_translation()
        eb.tail = eb.head + m.col[1].to_3d() * L[bname]
        eb.align_roll(m.col[2].to_3d())
        # clavicle / pelvis-side bones only carry the limbs; skinning to them drags the chest and
        # the hip flesh sideways (bodies.body leaves them out for the same reason)
        eb.use_deform = bname not in NON_DEFORM
        if parent:
            eb.parent = ebs[parent]
            eb.use_connect = False
        ebs[bname] = eb
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.hide_viewport = not show
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    fl = []
    for s in ("L", "R"):
        f = v(f"toe.{s}") - v(f"ankle.{s}")
        fl.append(math.degrees(math.atan2(-f.z, max(f.xy.length, 1e-6))))
    obj["rig_lengths"] = json.dumps(L)
    obj["rig_foot_pitch"] = max(5.0, min(45.0, sum(fl) / 2))
    obj["rig_lift"] = 0.0
    return obj


def symmetrize_joints(J):
    """Average each .L/.R landmark pair across x = 0 (a strap or bag skews detection; a lopsided
    skeleton shifts every frame of mirrored motion into the body)."""
    out = {k_: list(v) for k_, v in J.items()}
    for k_ in J:
        r = k_[:-2] + ".R"
        if not k_.endswith(".L") or r not in J:
            continue
        a, b = J[k_], J[r]
        x = (abs(a[0]) + abs(b[0])) / 2
        y, z = (a[1] + b[1]) / 2, (a[2] + b[2]) / 2
        out[k_] = [x if a[0] >= 0 else -x, y, z]
        out[r] = [-out[k_][0], y, z]
    return out


def measure_girth(body, arm, pure=0.6):
    """How thick the skinned character is around each bone, from its own mesh at rest (armature
    space). Torso bones get a polar profile (radius per 30-degree sector of the cross-section, so
    a satchel on one hip makes that side, and only that side, thicker); limbs and head a radius.
    Stored on arm["girth"] for retarget(clearance=...)."""
    import numpy as np
    names = {g.index: g.name for g in body.vertex_groups}
    toarm = arm.matrix_world.inverted() @ body.matrix_world
    per = {}
    for v in body.data.vertices:
        best, bw, tot = None, 0.0, 0.0
        for g in v.groups:
            tot += g.weight
            if g.weight > bw:
                best, bw = names.get(g.group), g.weight
        if best and tot > 0 and bw / tot >= pure:
            per.setdefault(best, []).append(toarm @ v.co)
    out = {}
    for b in arm.data.bones:
        pts = per.get(b.name)
        if not pts or len(pts) < 20:
            continue
        M = b.matrix_local
        R3, h = M.to_3x3(), M.to_translation()
        loc = np.array([tuple(R3.transposed() @ (p - h)) for p in pts])
        t = loc[:, 1] / max(b.length, 1e-6)
        if b.name in ("hips", "spine", "chest"):
            # polar profile: radius per 30-degree sector around the bone (bags, pouches and hems
            # bulge in one direction; an ellipse would cut their corners)
            ang = np.arctan2(loc[:, 2], loc[:, 0])
            rad = np.hypot(loc[:, 0], loc[:, 2])
            sec = ((ang + np.pi) / (2 * np.pi) * SECTORS).astype(int) % SECTORS
            prof = []
            for j in range(SECTORS):
                r_ = rad[sec == j]
                prof.append(float(np.percentile(r_, 90)) if len(r_) > 8 else None)
            fill = [v for v in prof if v is not None] or [0.1]
            prof = [v if v is not None else min(fill) for v in prof]
            out[b.name] = {"sect": prof}
        else:
            mid = (t > 0.15) & (t < 0.85)
            rad = np.hypot(loc[mid, 0], loc[mid, 2]) if mid.sum() > 10 else np.hypot(loc[:, 0], loc[:, 2])
            out[b.name] = {"r": float(np.percentile(rad, 80))}
    arm["girth"] = json.dumps(out)
    return out


def bone_matrix(arm, bone, at=0.0):
    """World matrix of a bone in REST pose, at a fraction along it (0 head .. 1 tail)."""
    b = arm.data.bones[bone]
    m = arm.matrix_world @ b.matrix_local
    m = m @ Matrix.Translation((0, b.length * at, 0))
    return m


def attach(obj, arm, bone):
    """Rigidly parent obj to a bone, keeping its current world placement (set at rest pose)."""
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    b = arm.data.bones[bone]
    tail = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    obj.matrix_parent_inverse = tail.inverted()
    obj.matrix_world = mw
    return obj


# ---------------------------------------------------------------- retarget
def two_bone_ik(H, K0, A, l1, l2):
    """Analytic two-bone IK: hip H, original knee K0 (sets the bend plane), ankle target A.
    Returns new (thigh, shin) directions with exact lengths l1, l2."""
    d = A - H
    dist = max(min(d.length, (l1 + l2) * 0.9999), abs(l1 - l2) + 1e-4)
    u = d.normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    p = (K0 - H) - u * (K0 - H).dot(u)
    if p.length < 1e-6:
        p = Vector((0, -1, 0)) - u * u.y * -1
    p.normalize()
    K = H + u * a + p * h
    return (K - H), (H + u * dist - K)


def _smooth(vals, sigma):
    if sigma <= 0:
        return vals
    r = int(3 * sigma + 0.5)
    k = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-r, r + 1)]
    s = sum(k)
    k = [x / s for x in k]
    n = len(vals)
    return [sum(k[j] * vals[min(n - 1, max(0, i + j - r))] for j in range(len(k))) for i in range(n)]


# ---------------------------------------------------------------- clearance (limb vs body)
ARM_SAMPLES = (("upper_arm", 0.5), ("upper_arm", 0.8), ("upper_arm", 1.0), ("forearm", 0.35),
               ("forearm", 0.7), ("forearm", 1.0), ("hand", 0.6))
LEG_SAMPLES = (("thigh", 0.45), ("thigh", 0.75), ("thigh", 1.0), ("shin", 0.35), ("shin", 0.7), ("shin", 1.0))
TORSO = ("hips", "spine", "chest")
# the hips obstacle reaches below the pelvis centre: belt pouches, satchels and coat hems hang there
TORSO_BELOW = {"hips": -0.12}


def _pt(pose, L, b, t):
    m = pose[b]
    return m.to_translation() + m.col[1].to_3d().normalized() * (L[b] * t)


def _closest_on_seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return a + ab * t


SECTORS = 12


def _profile_r(g, x, z):
    """Torso radius in the direction (x, z) of the bone's cross-section (interpolated sectors)."""
    prof = g["sect"]
    u = (math.atan2(z, x) + math.pi) / (2 * math.pi) * SECTORS - 0.5
    j = math.floor(u)
    f = u - j
    return prof[j % SECTORS] * (1 - f) + prof[(j + 1) % SECTORS] * f


def _torso_inside(pose, L, G, b, p, r):
    """(how far inside (m), outward direction) of sphere (p, r) vs torso bone b, or None."""
    g = G.get(b)
    if not g or "sect" not in g:
        return None
    M = pose[b]
    R3 = M.to_3x3()
    loc = R3.transposed() @ (p - M.to_translation())
    if loc.y < TORSO_BELOW.get(b, -0.02) or loc.y > L[b] + 0.02:
        return None
    rad = math.hypot(loc.x, loc.z)
    need = _profile_r(g, loc.x, loc.z) + r - rad
    if need <= 0:
        return None
    out = R3 @ (Vector((loc.x, 0, loc.z)) / rad if rad > 1e-6 else Vector((1, 0, 0)))
    return need, out


def _torso_push(pose, L, G, scale, p, r, side):
    """Smallest push that moves a sphere (p, r) out of the torso's measured cross-sections."""
    best = None
    for b in TORSO:
        hit = _torso_inside(pose, L, G, b, p, r)
        if not hit:
            continue
        need, out = hit
        need -= scale.get((b, side), 0.0)   # rest-pose allowance
        if need <= 0:
            continue
        d = out * need
        if best is None or d.length > best.length:
            best = d
    return best


def _cap_push(p, r, a, b, rc):
    c = _closest_on_seg(p, a, b)
    v = p - c
    dist = v.length
    need = r + rc - dist
    if need <= 0:
        return None
    return (v.normalized() if dist > 1e-6 else Vector((0, 0, 1))) * need


class _Clearance:
    """Keeps limbs out of the body: arms vs torso (elliptic, measured per side), head and thighs;
    leg vs leg. Works on bone directions like the IK: a penetrating limb is swung about its root
    joint (shoulder / hip) just far enough to clear, keeping its own bend. Obstacle sizes are
    calibrated on the rest pose so the mesh's own stance never counts as a collision."""

    def __init__(self, G, L, rest_pose, margin=0.005):
        self.G, self.L, self.m = G, L, margin
        self.r = {b: G.get(b, {}).get("r", 0.04) for b in L}
        self.scale = {}
        self.leg_k = 1.0
        # calibrate: at rest, every arm sample sits outside the torso (an allowance per torso bone
        # and side absorbs whatever the mesh's own stance overlaps) and the legs clear each other
        for s in ("L", "R"):
            for part, t in ARM_SAMPLES:
                b = f"{part}.{s}"
                p = _pt(rest_pose, L, b, t)
                for tb in TORSO:
                    hit = _torso_inside(rest_pose, L, G, tb, p, self.r[b])
                    if hit:
                        self.scale[(tb, s)] = max(self.scale.get((tb, s), 0.0), hit[0] + 0.005)
        gap = None
        for pa, ta in LEG_SAMPLES:
            for pb, tb_ in LEG_SAMPLES:
                d = (_pt(rest_pose, L, f"{pa}.L", ta) - _pt(rest_pose, L, f"{pb}.R", tb_)).length
                need = self.r[f"{pa}.L"] + self.r[f"{pb}.R"]
                gap = d / need if gap is None else min(gap, d / need)
        if gap is not None and gap < 1.0:
            self.leg_k = gap * 0.97
        self.hits = 0

    def arm_push(self, pose, s):
        """(sample point, push vector) of the deepest arm sample, or None."""
        L, worst = self.L, None
        other = "R" if s == "L" else "L"
        for part, t in ARM_SAMPLES:
            b = f"{part}.{s}"
            p, r = _pt(pose, L, b, t), self.r[b]
            cands = [_torso_push(pose, L, self.G, self.scale, p, r, s)]
            if part != "hand" and "head" in self.G:
                cands.append(_cap_push(p, r, _pt(pose, L, "neck", 0.3), _pt(pose, L, "head", 0.8), self.r["head"]))
            if part in ("forearm", "hand"):
                for ls in (s, other):
                    cands.append(_cap_push(p, r, _pt(pose, L, f"thigh.{ls}", 0.1), _pt(pose, L, f"thigh.{ls}", 1.0),
                                           self.r[f"thigh.{ls}"]))
            for d in cands:
                if d is not None and d.length > self.m and (worst is None or d.length > worst[1].length):
                    worst = (p, d)
        return worst

    def leg_push(self, pose):
        """(L sample, R sample, push for L) of the deepest leg-leg overlap, or None."""
        L, worst = self.L, None
        segs = {s: [(_pt(pose, L, f"{b}.{s}", 0.0), _pt(pose, L, f"{b}.{s}", 1.0), self.r[f"{b}.{s}"] * self.leg_k)
                    for b in ("thigh", "shin")] for s in ("L", "R")}
        for part, t in LEG_SAMPLES:
            p = _pt(pose, L, f"{part}.L", t)
            r = self.r[f"{part}.L"] * self.leg_k
            for a, b, rc in segs["R"]:
                d = _cap_push(p, r, a, b, rc)
                if d is not None and d.length > self.m and (worst is None or d.length > worst[1].length):
                    worst = (p, d)
        return worst

    def solve_frame(self, d, t, pose, hinge, iters=4):
        """Adjust directions d in place; returns (pose, {chain: quaternion applied})."""
        L = self.L
        applied = {}
        for _ in range(iters):
            changed = False
            for s in ("L", "R"):
                hit = self.arm_push(pose, s)
                if not hit:
                    continue
                p, push = hit
                S = pose[f"upper_arm.{s}"].to_translation()
                q = (p - S).rotation_difference(p + push * 1.1 - S)
                for b in (f"upper_arm.{s}", f"forearm.{s}", f"hand.{s}"):
                    d[b] = q @ d[b]
                applied[f"arm.{s}"] = q @ applied.get(f"arm.{s}", Quaternion())
                changed = True
            hit = self.leg_push(pose)
            if hit:
                p, push = hit
                for s, sgn in (("L", 0.55), ("R", -0.55)):
                    Hj = pose[f"thigh.{s}"].to_translation()
                    q = (p - Hj).rotation_difference(p + push * sgn - Hj)
                    for b in (f"thigh.{s}", f"shin.{s}", f"foot.{s}"):
                        d[b] = q @ d[b]
                    applied[f"leg.{s}"] = q @ applied.get(f"leg.{s}", Quaternion())
                changed = True
            if not changed:
                break
            self.hits += 1
            pose = solve(d, t, L, Vector((0, 0, 0)), hinge=hinge)
        return pose, applied


CHAINS = {"arm.L": ("upper_arm.L", "forearm.L", "hand.L"), "arm.R": ("upper_arm.R", "forearm.R", "hand.R"),
          "leg.L": ("thigh.L", "shin.L", "foot.L"), "leg.R": ("thigh.R", "shin.R", "foot.R")}


def _smooth_quats(qs, sigma):
    """Gaussian-smooth a quaternion track (sign-continuous, renormalised)."""
    qs = [q.copy() for q in qs]
    for i in range(1, len(qs)):
        if qs[i].dot(qs[i - 1]) < 0:
            qs[i].negate()
    comp = [_smooth([q[c] for q in qs], sigma) for c in range(4)]
    out = []
    for i in range(len(qs)):
        q = Quaternion((comp[0][i], comp[1][i], comp[2][i], comp[3][i]))
        q.normalize()
        out.append(q)
    return out


def _rest_pose(arm):
    """Bones' rest matrices in armature space, the same structure solve() returns."""
    return {b.name: b.matrix_local.copy() for b in arm.data.bones}


def _rest_correction(arm, L):
    """Per-bone rotation (about the bone) mapping solve(hinge=True)'s rest frames onto the
    armature's real rest frames, so a different roll convention never twists the mesh."""
    rp = _rest_pose(arm)
    d = {n: rp[n].col[1].to_3d() for n, _, _ in BONES}
    t = {n: rp[n].col[0].to_3d() for n, _, _ in BONES}
    # children of hinge limbs need their true rest direction for the bend
    solved = solve(d, t, L, rp["hips"].to_translation(), hinge=True)
    return {n: solved[n].to_3x3().inverted() @ rp[n].to_3x3() for n, _, _ in BONES}


def retarget(arm, mo, start=1, locomotion="footlock", ground="lock", heading=0.0, frames=None,
             set_scene=True, gap_fill=True, gains=None, foot_ik=True, twist=None, clearance=None,
             stride_scale=None, hand_targets=None, physics=False, toe_contacts=False, max_drop=None,
             floor_guard=False, foot_pitch=None, level_feet=False, quality=False):
    """Key the armature from motion.json. Returns per-frame root positions (world, after lift).

    heading rotates the whole performance about Z (degrees) so a sideways walk can face the camera.
    frames=(a, b) uses only that 1-based frame range of the capture.

    Clean-up passes (all off by default; quality=True turns them all on):
      twist="hinge"       upper arm / thigh roll follows the elbow / knee bend plane; the rest pose
                          is matched exactly. NOT in quality: on CMU runs it carried the capture's
                          hip rotation into the knees (leg-leg overlap 1% -> 21% of frames)
      clearance=girth     keep limbs out of the body (measure_girth(body, arm) or arm["girth"])
      stride_scale="auto" scale a recorded root path by target / performer leg length (short legs
                          take shorter strides instead of over-reaching), or a number
      toe_contacts        the toe phase of a step counts as a contact by the toe's own speed
      max_drop=0.08       cap the pelvis adjustment (metres)
      floor_guard         lift any swing foot that would dip through the floor (smoothed)
      level_feet          planted soles stay level side to side (a wide stance tilts the shin,
                          and a foot that inherits the tilt digs one edge into the floor)
      foot_pitch="match"  the performer's flat foot becomes the character's flat foot (CMU feet
                          are ~30 deg ankle->toe when flat; a mesh's are often ~17: copied raw,
                          every planted foot points its toe down and lifts the body off the floor)
      ground="local"      (root locomotion) floor = lowest foot within +-0.4 s, so every chained
                          clip lands on the floor and a run keeps its flight phase
      physics             quasi-static balance: keep the centre of mass over the planted feet
                          while the body is (nearly) still (physics.py)
      hand_targets={"L": fn(i) -> Vector | None}   arm IK: wrist to a world point on frame i (0-based)
    """
    L = json.loads(arm["rig_lengths"])
    if quality:
        foot_pitch = foot_pitch or "match"
        if ground == "lock" and locomotion == "root":
            ground = "local"
        toe_contacts = floor_guard = level_feet = True
        physics = True
        max_drop = 0.08 if max_drop is None else max_drop
        stride_scale = stride_scale or "auto"
        if clearance is None and arm.get("girth"):
            clearance = json.loads(arm["girth"])
    hinge = twist == "hinge"
    stats_ = {}
    world = mo["world"]
    a, b = frames if frames else (1, len(world))
    world = world[a - 1:b]
    n = len(world)
    R = Matrix.Rotation(math.radians(heading), 3, "Z")
    # 1) FK with the root at the origin
    targ = []
    for P in world:
        P = [R @ p for p in P]
        targ.append(targets(P))
    if gains:
        # Gait shaping: scale each bone's swing about its mean direction (e.g. thigh 1.2 = longer
        # stride, upper_arm 0.5 = calmer arms). Keys match bone names without side ("thigh").
        for key, g in gains.items():
            for side in ("", ".L", ".R"):
                name = key + side
                if name not in targ[0][0]:
                    continue
                mean = sum((d[name].normalized() for d, _ in targ), Vector()) / len(targ)
                mean.normalize()
                for d, _ in targ:
                    v = d[name].normalized()
                    q = mean.rotation_difference(v)
                    axis, ang = q.to_axis_angle()
                    d[name] = Quaternion(axis, ang * g) @ mean
    if foot_pitch == "match":
        rest_p = arm.get("rig_foot_pitch", 26.6)
        segs = [(s0 - a, s1 - a) for s0, s1, _ in mo.get("segments", [])] or [(0, n - 1)]
        fixes = []
        for s0, s1 in segs:
            s0, s1 = max(0, s0), min(n - 1, s1)
            if s1 - s0 < 5:
                continue
            sub = {"world": world[s0:s1 + 1]}
            for side in ("L", "R"):
                try:
                    dp = stance_pitch(sub, side) - rest_p
                except Exception:
                    continue
                fixes.append(round(dp, 1))
                up = Vector((0, 0, 1))
                for i in range(s0, s1 + 1):
                    v = targ[i][0][f"foot.{side}"]
                    h = Vector((v.x, v.y, 0))
                    if h.length < 1e-6 or v.length < 1e-9:
                        continue
                    pitch = math.asin(max(-1.0, min(1.0, -v.z / v.length))) - math.radians(dp)
                    pitch = max(math.radians(-80), min(math.radians(85), pitch))
                    targ[i][0][f"foot.{side}"] = (h.normalized() * math.cos(pitch) - up * math.sin(pitch)) * v.length
        stats_["foot_pitch_fix_deg"] = fixes
    poses = [solve(d, t, L, Vector((0, 0, 0)), hinge=hinge) for d, t in targ]

    # 1b) clearance: swing limbs out of the body, then ease the corrections over time
    if clearance:
        cl = _Clearance(clearance, L, solve_rest(arm, L, hinge))
        orig = [{k_: v.copy() for k_, v in d.items()} for d, _ in targ]
        tracks = {c: [Quaternion()] * n for c in CHAINS}
        for i, (d, t) in enumerate(targ):
            poses[i], ap = cl.solve_frame(d, t, poses[i], hinge)
            for c, q in ap.items():
                tracks[c][i] = q
        hit_frames = sum(1 for i in range(n) if any(tracks[c][i].angle > 1e-4 for c in CHAINS))
        for c, bones_ in CHAINS.items():
            if all(q.angle < 1e-4 for q in tracks[c]):
                continue
            # dilate then smooth: a correction starts a little early and fades a little late
            ang = [q.angle for q in tracks[c]]
            src = list(tracks[c])
            for i in range(n):
                j = max(range(max(0, i - 2), min(n, i + 3)), key=lambda j_: ang[j_])
                src[i] = tracks[c][j]
            sm_q = _smooth_quats(src, 2.0)
            for i in range(n):
                for bn in bones_:
                    targ[i][0][bn] = sm_q[i] @ orig[i][bn]
        for i, (d, t) in enumerate(targ):  # residual pass on the smoothed result
            poses[i] = solve(d, t, L, Vector((0, 0, 0)), hinge=hinge)
            poses[i], _ = cl.solve_frame(d, t, poses[i], hinge, iters=2)
        stats_["clearance_frames"] = hit_frames

    def foot_pts(pose, side):
        sh, ft = pose[f"shin.{side}"], pose[f"foot.{side}"]
        ankle = sh.to_translation() + sh.col[1].to_3d().normalized() * L[f"shin.{side}"]
        toe = ft.to_translation() + ft.col[1].to_3d().normalized() * L[f"foot.{side}"]
        return ankle, toe

    # 2) ground: lowest foot point per frame
    lows = []
    for pose in poses:
        pts = [p for s in ("L", "R") for p in foot_pts(pose, s)]
        lows.append(min(p.z for p in pts))
    if ground == "lock":
        z_off = _smooth([-z for z in lows], 1.0)
    else:
        med = sorted(lows)[len(lows) // 2]
        z_off = [-med] * n

    # 3) locomotion: integrate the planted foot's slide
    valid = mo.get("valid", [True] * len(mo["world"]))[a - 1:b]
    deltas = [Vector((0, 0))]
    stance = None
    for i in range(1, n):
        if locomotion != "footlock":
            deltas.append(Vector((0, 0)))
            continue
        # Planted foot = the one sliding BACKWARD relative to the hips (along the facing
        # direction): body-relative, so it works even though captured depth is noisy.
        # (Walking backwards would need locomotion="none" plus hand-keyed travel.)
        fwd = poses[i]["hips"].col[2].to_3d().xy
        fwd = fwd.normalized() if fwd.length > 1e-6 else Vector((0, -1))
        d = {}
        for s_ in ("L", "R"):
            c_ = sum(foot_pts(poses[i], s_), Vector()) / 2
            p_ = sum(foot_pts(poses[i - 1], s_), Vector()) / 2
            d[s_] = (c_ - p_).xy
        back = min(("L", "R"), key=lambda s_: d[s_].dot(fwd))
        if stance is None or d[back].dot(fwd) < d[stance].dot(fwd) - 0.004:  # hysteresis
            stance = back
        deltas.append(-d[stance])
    if locomotion == "footlock" and gap_fill:
        # Interpolated frames (subject not detected) have no real foot contact, so they'd stall
        # the travel: give them the mean velocity of nearby tracked frames instead.
        win = int(mo.get("fps", 24) * 2)
        for i in range(1, n):
            if valid[i] and valid[i - 1]:
                continue
            near = [deltas[j] for j in range(max(1, i - win), min(n, i + win))
                    if valid[j] and valid[j - 1]]
            if near:
                deltas[i] = sum(near, Vector((0, 0))) / len(near)
    xy = [Vector((0, 0))]
    for d in deltas[1:]:
        xy.append(xy[-1] + d)
    if locomotion == "root" and mo.get("root"):
        # copy the recorded root path one-to-one (mocap / BVH / world-grounded capture)
        r0 = mo["root"][a - 1]
        xy = [(R @ (r - r0)).xy for r in mo["root"][a - 1:b]]
        if stride_scale:
            k_s = _stride_ratio(L, mo) if stride_scale == "auto" else float(stride_scale)
            xy = [v * k_s for v in xy]
            stats_["stride_scale"] = round(k_s, 3)
    xs = _smooth([v.x for v in xy], 1.5)
    ys = _smooth([v.y for v in xy], 1.5)

    # 3b) vertical: a recorded root (BVH / mocap) keeps its natural hip bob; the floor is set so
    #     the lowest foot sits on z=0 in the typical frame
    if locomotion == "root" and mo.get("root") and ground != "free":
        rz = [(R @ r).z for r in mo["root"][a - 1:b]]
        if stride_scale:  # the hip bob scales with the legs too
            med = sorted(rz)[n // 2]
            rz = [med + (z - med) * stats_.get("stride_scale", 1.0) for z in rz]
        if ground == "local":
            # the floor is the lowest foot point within +-0.4 s (always contains a stance, even
            # in a run's flight phase), smoothed: chained clips from different performers each
            # land on the floor instead of sharing one median height
            g = [lows[i] + rz[i] for i in range(n)]
            w = max(1, int(round(0.4 * mo.get("fps", 30))))
            fl = [min(g[max(0, i - w):i + w + 1]) for i in range(n)]
            fl = _smooth(fl, 0.25 * mo.get("fps", 30))
            z_off = [rz[i] - fl[i] for i in range(n)]
        else:
            c0 = sorted(lows[i] + rz[i] for i in range(n))[n // 2]
            z_off = [rz[i] - c0 for i in range(n)]

    # 3c) foot contacts + two-bone IK: a planted foot stays exactly where it landed
    contacts = {"L": [False] * n, "R": [False] * n}
    if foot_ik and n > 4:
        fps_ = mo.get("fps", 24)
        offs = [Vector((xs[i], ys[i], z_off[i])) for i in range(n)]
        rb = arm.data.bones
        ank_h = {s_: (arm.matrix_world @ rb[f"shin.{s_}"].tail_local).z for s_ in ("L", "R")}
        toe_z = 0.0  # rest pose stands with the toe tip on the floor
        rest_pitch = math.radians(arm.get("rig_foot_pitch", 26.6))
        dirty = set()
        plan = {}
        run_log = []
        # Ground the performance once: shift the body so the performer's typical planted ankle height
        # equals our standing ankle height (where the sole is flat on z=0). Per-frame heights then
        # stay as recorded - forcing them made legs over-reach and lock straight.
        planted = []
        for s_ in ("L", "R"):
            A0 = [foot_pts(poses[i], s_)[0] + offs[i] for i in range(n)]
            sp0 = [(A0[max(i, 1)] - A0[max(i, 1) - 1]).xy.length * fps_ for i in range(n)]
            zlow = sorted(a_.z for a_ in A0)[max(0, n // 10)]
            planted += [A0[i].z - ank_h[s_] for i in range(n) if sp0[i] < 0.3 and A0[i].z < zlow + 0.015]
        if planted:
            dz = sorted(planted)[len(planted) // 2]
            for i in range(n):
                z_off[i] -= dz
                offs[i] = Vector((xs[i], ys[i], z_off[i]))
        for s_ in ("L", "R"):
            A = [foot_pts(poses[i], s_)[0] + offs[i] for i in range(n)]
            T = [foot_pts(poses[i], s_)[1] + offs[i] for i in range(n)]
            spd = [(A[max(i, 1)] - A[max(i, 1) - 1]).xy.length * fps_ for i in range(n)]
            if toe_contacts:
                # heel down and the ankle still, or the toe down and the toe still (push-off)
                tsp = [(T[max(i, 1)] - T[max(i, 1) - 1]).xy.length * fps_ for i in range(n)]
                c = [(A[i].z - ank_h[s_] < 0.05 and spd[i] < 0.6) or (T[i].z < 0.04 and tsp[i] < 0.5)
                     for i in range(n)]
            else:
                c = [min(A[i].z - ank_h[s_], T[i].z) < 0.05 and spd[i] < 0.6 for i in range(n)]
            # clean: fill 1-2 frame gaps, drop contacts shorter than 3 frames
            for i in range(1, n - 2):
                if c[i - 1] and not c[i] and (c[i + 1] or c[i + 2]):
                    c[i] = True
            runs, i = [], 0
            while i < n:
                if c[i]:
                    j = i
                    while j + 1 < n and c[j + 1]:
                        j += 1
                    if j - i + 1 >= 3:
                        runs.append((i, j))
                    i = j + 1
                else:
                    i += 1
            want_t, want_f = {}, {}
            for i0, i1 in runs:
                for i in range(i0, i1 + 1):
                    contacts[s_][i] = True
                if foot_ik == "detect":
                    continue
                # Heel-to-toe roll: from heel strike to heel-off the ankle (heel) is the pivot; after
                # heel-off the toe is, and the ankle rises and rolls over it. Pin whichever is down.
                zmin = min(A[i].z for i in range(i0, i1 + 1))
                heel = [A[i].z - zmin < 0.015 for i in range(i0, i1 + 1)]
                hs = [i0 + k_ for k_, h_ in enumerate(heel) if h_]
                last_heel = max(hs) if hs else i0 - 1
                heel_pin = (sum((A[i].xy for i in hs), Vector((0, 0))) / len(hs)) if hs else None
                ts = list(range(last_heel + 1, i1 + 1))
                # per-step height correction: this step's flat phase lands at standing height;
                # one constant offset for the whole step keeps its recorded shape (no forcing)
                base = sorted(A[i].z for i in (hs or range(i0, i1 + 1)))
                step_dz = ank_h[s_] - base[len(base) // 2]
                run_log.append([s_, i0, i1, len(hs), round(step_dz * 100, 1), round(base[0] * 100, 1), round(ank_h[s_] * 100, 1)])
                toe_pin = (sum((T[i].xy for i in ts), Vector((0, 0))) / len(ts)) if ts else None
                ramp = 4
                for i in range(max(0, i0 - ramp), min(n, i1 + ramp + 1)):
                    if i < i0:
                        w = (i - (i0 - ramp - 1)) / (ramp + 1)
                    elif i > i1:
                        w = ((i1 + ramp + 1) - i) / (ramp + 1)
                    else:
                        w = 1.0
                    w = w * w * (3 - 2 * w)  # smoothstep
                    use_toe = toe_pin is not None and (i > last_heel or heel_pin is None)
                    fd = (T[i] - A[i]).normalized()
                    horiz = Vector((fd.x, fd.y, 0)).normalized() if fd.xy.length > 1e-6 else Vector((0, -1, 0))
                    flat = horiz * math.cos(rest_pitch) - Vector((0, 0, 1)) * math.sin(rest_pitch)
                    if use_toe:
                        # toe phase: heel lifting, toe on the floor; the heel never dips below flat
                        if fd.z > flat.z:   # flatter than standing flat = heel through the floor
                            fd = flat
                        tt = T[i].copy()
                        tt.xy = T[i].xy.lerp(toe_pin, w)
                        tt.z = T[i].z + step_dz * w
                        tgt = tt - fd * L[f"foot.{s_}"]   # ankle sits behind the pinned toe
                    else:
                        # heel phase: foot flat on the floor, ankle at standing height
                        fd = fd.lerp(flat, w).normalized()
                        tgt = A[i].copy()
                        tgt.xy = A[i].xy.lerp(heel_pin, w)
                        tgt.z = A[i].z + step_dz * w
                    want_t[i], want_f[i] = tgt, fd
            # Smooth the pinned ankle targets and foot directions over time (the heel-to-toe
            # hand-off and the ramps would otherwise pop the knee); solved below, after the pelvis.
            idx = sorted(want_t)
            if idx:
                full_t = [want_t.get(i, A[i]) for i in range(n)]
                full_f = [want_f.get(i, (T[i] - A[i]).normalized()) for i in range(n)]
                sm = lambda vals, sig: [Vector(c) for c in zip(*[_smooth([v[q] for v in vals], sig) for q in range(3)])]
                full_t = sm(full_t, 1.6)
                full_f = [v.normalized() for v in sm(full_f, 1.6)]
                plan[s_] = (idx, full_t, full_f)
        # Balance (physics.py): while nearly still, slide the hips so the centre of mass stays over
        # the planted feet. The pins are world points, so the legs re-solve to the new hips.
        if physics and plan:
            import physics as phys
            shift = phys.balance_shift(poses, offs, contacts, L, fps_)
            if shift:
                for i in range(n):
                    xs[i] += shift[i].x
                    ys[i] += shift[i].y
                    offs[i] = Vector((xs[i], ys[i], z_off[i]))
                stats_["balance_shift_max_cm"] = round(max(v.length for v in shift) * 100, 1)
        # Pelvis adjustment (as engine foot-IK does): where a pinned foot is out of reach with a
        # little knee bend, lower the hips instead of locking the leg straight (which pops).
        min_bend = math.radians(4.0)
        drop = [0.0] * n
        for s_, (idx, full_t, _) in plan.items():
            l1, l2 = L[f"thigh.{s_}"], L[f"shin.{s_}"]
            reach = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(min_bend))
            for i in idx:
                H = poses[i][f"thigh.{s_}"].to_translation() + offs[i]
                dv = full_t[i] - H
                dxy2 = dv.x * dv.x + dv.y * dv.y
                if dv.length > reach and dxy2 < reach * reach:
                    drop[i] = max(drop[i], (-dv.z) - math.sqrt(reach * reach - dxy2))
        if max_drop is not None:
            drop = [min(d_, max_drop) for d_ in drop]
        if any(d_ > 0 for d_ in drop):
            # spread each dip over neighbouring frames, never less than needed
            sm_drop = _smooth(drop, 2.0)
            drop = [max(a_, b_) for a_, b_ in zip(drop, sm_drop)]
            drop = _smooth(drop, 1.0)
            for i in range(n):
                z_off[i] -= drop[i]
                offs[i] = Vector((xs[i], ys[i], z_off[i]))
        for s_, (idx, full_t, full_f) in plan.items():
            for i in idx:
                targ[i][0][f"foot.{s_}"] = full_f[i]
                H = poses[i][f"thigh.{s_}"].to_translation() + offs[i]
                K0 = poses[i][f"shin.{s_}"].to_translation() + offs[i]
                th, sh = two_bone_ik(H, K0, full_t[i], L[f"thigh.{s_}"], L[f"shin.{s_}"])
                targ[i][0][f"thigh.{s_}"] = th
                targ[i][0][f"shin.{s_}"] = sh
                dirty.add(i)
        arm["pelvis_drop_max_cm"] = round(max(drop) * 100, 2)
        arm["contact_runs"] = json.dumps(run_log)
        for i in dirty:
            poses[i] = solve(targ[i][0], targ[i][1], L, Vector((0, 0, 0)), hinge=hinge)
        if floor_guard or level_feet:
            # level soles while planted (weights eased in/out over 3 frames)
            for s_ in ("L", "R"):
                c_ = [1.0 if v else 0.0 for v in contacts[s_]]
                wl = _smooth([max(c_[max(0, i - 2):i + 3]) for i in range(n)], 1.2)
                for i in range(n):
                    if wl[i] > 0.01:
                        targ[i][1][f"foot.{s_}"] = wl[i]
                        dirty.add(i)
            for i in dirty:
                poses[i] = solve(targ[i][0], targ[i][1], L, Vector((0, 0, 0)), hinge=hinge)
        if floor_guard:
            # a swing foot (or one the pelvis drop lowered) never goes through the floor: the lift
            # each frame needs is spread and smoothed like the pelvis drop, then solved with IK
            lifted = 0
            for s_ in ("L", "R"):
                need = []
                for i in range(n):
                    A_, T_ = (p_ + offs[i] for p_ in foot_pts(poses[i], s_))
                    need.append(max(0.0, -min(A_.z - ank_h[s_], T_.z)))
                if max(need) < 0.002:
                    continue
                sm_n = _smooth(need, 2.0)
                need = _smooth([max(x, y) for x, y in zip(need, sm_n)], 1.0)
                for i in range(n):
                    if need[i] < 0.001:
                        continue
                    A_ = foot_pts(poses[i], s_)[0] + offs[i]
                    H = poses[i][f"thigh.{s_}"].to_translation() + offs[i]
                    K0 = poses[i][f"shin.{s_}"].to_translation() + offs[i]
                    th, sh = two_bone_ik(H, K0, A_ + Vector((0, 0, need[i])), L[f"thigh.{s_}"], L[f"shin.{s_}"])
                    targ[i][0][f"thigh.{s_}"], targ[i][0][f"shin.{s_}"] = th, sh
                    poses[i] = solve(targ[i][0], targ[i][1], L, Vector((0, 0, 0)), hinge=hinge)
                    lifted += 1
            stats_["floor_guard_frames"] = lifted
    if hand_targets:
        offs_ = [Vector((xs[i], ys[i], z_off[i])) for i in range(n)]
        for s_, fn in hand_targets.items():
            for i in range(n):
                tgt = fn(i)
                if tgt is None:
                    continue
                S = poses[i][f"upper_arm.{s_}"].to_translation() + offs_[i]
                E0 = poses[i][f"forearm.{s_}"].to_translation() + offs_[i]
                ua, fa = two_bone_ik(S, E0, tgt, L[f"upper_arm.{s_}"], L[f"forearm.{s_}"])
                targ[i][0][f"upper_arm.{s_}"], targ[i][0][f"forearm.{s_}"] = ua, fa
                poses[i] = solve(targ[i][0], targ[i][1], L, Vector((0, 0, 0)), hinge=hinge)
    arm["contacts"] = json.dumps({k_: [int(v) for v in vs] for k_, vs in contacts.items()})
    arm["retarget_stats"] = json.dumps(stats_)
    if hinge:
        C = _rest_correction(arm, L)
        for pose in poses:
            for name in pose:
                m = (pose[name].to_3x3() @ C[name]).to_4x4()
                m.translation = pose[name].to_translation()
                pose[name] = m

    # 4) key the bones
    sc = bpy.context.scene
    if set_scene:
        fps = mo.get("fps", 30)
        sc.render.fps = round(fps)
        sc.render.fps_base = round(fps) / fps
        sc.frame_start, sc.frame_end = start, start + n - 1
    rest_local = {bn.name: bn.matrix_local.copy() for bn in arm.data.bones}
    prev_q = {}
    roots = []
    for i, pose in enumerate(poses):
        f = start + i
        off = Vector((xs[i], ys[i], z_off[i] + 0))
        for name, parent, _ in BONES:
            desired = pose[name].copy()
            desired.translation += off  # pose space == armature space
            if parent is None:
                basis = rest_local[name].inverted() @ desired
            else:
                pd = pose[parent].copy()
                pd.translation += off
                rel = rest_local[parent].inverted() @ rest_local[name]
                basis = rel.inverted() @ pd.inverted() @ desired
            pb = arm.pose.bones[name]
            loc, q, _ = basis.decompose()
            if name in prev_q and prev_q[name].dot(q) < 0:
                q.negate()
            prev_q[name] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if parent is None:
                pb.location = loc
                pb.keyframe_insert("location", frame=f)
        roots.append(arm.matrix_world @ (pose["hips"].to_translation() + off))
    return roots


def _stride_ratio(L, mo):
    """Target leg length / performer leg length (thigh + shin)."""
    m = mo.get("lengths", {})
    perf = m.get("thigh", 0) + m.get("shin", 0)
    tgt = (L["thigh.L"] + L["shin.L"] + L["thigh.R"] + L["shin.R"]) / 2
    return max(0.4, min(1.6, tgt / perf)) if perf > 1e-3 else 1.0


def solve_rest(arm, L, hinge=False):
    """The rest pose re-solved the way retarget() solves frames (for calibration)."""
    rp = _rest_pose(arm)
    d = {n: rp[n].col[1].to_3d() for n, _, _ in BONES}
    t = {n: rp[n].col[0].to_3d() for n, _, _ in BONES}
    out = solve(d, t, L, Vector((0, 0, 0)), hinge=hinge)
    return out


def follow_camera(cam, arm, axes="XY", bone="hips"):
    """Camera keeps its offset from the hips along the given axes (a dolly/tracking shot)."""
    c = cam.constraints.new("COPY_LOCATION")
    c.target = arm
    c.subtarget = bone
    c.use_x, c.use_y, c.use_z = "X" in axes, "Y" in axes, "Z" in axes
    c.use_offset = True
    # use_offset adds the bone's position to the camera's own, so subtract the rest position once
    rest = (arm.matrix_world @ arm.data.bones[bone].head_local)
    cam.location = Vector((cam.location.x - (rest.x if c.use_x else 0),
                           cam.location.y - (rest.y if c.use_y else 0),
                           cam.location.z - (rest.z if c.use_z else 0)))
    return c


def stats(arm, mo, frames=None):
    """Quick numbers for the verify step: travel distance and foot penetration."""
    sc = bpy.context.scene
    L = json.loads(arm["rig_lengths"])
    arm.hide_viewport = False  # a hidden armature with no visible children isn't evaluated
    lows, hips = [], []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        pts = []
        for s in ("L", "R"):
            for bn in (f"shin.{s}", f"foot.{s}"):
                pb = arm.pose.bones[bn]
                pts.append((arm.matrix_world @ pb.tail).z)
        lows.append(min(pts))
        hips.append(arm.matrix_world @ arm.pose.bones["hips"].head)
    travel = (hips[-1] - hips[0]).length
    return {"min_foot_z": round(min(lows), 4), "max_foot_low_z": round(max(lows), 4),
            "travel_m": round(travel, 3), "frames": len(lows)}


def match_camera(cam, mo, roots, frame=1, lens=None, scale=1.0, src_offset=0):
    """Place a level camera so the character lands where the actor was in the reference frame:
    same on-screen height (nose to feet), same horizontal position, feet on the same image row.

    roots: the list retarget() returned. frame: 1-based frame of the retargeted range.
    src_offset: retarget(frames=(a, b)) start minus 1, so frame maps to the capture's frame.
    Pinhole maths with Blender's default horizontal sensor fit (landscape output).
    """
    sc = bpy.context.scene
    W = sc.render.resolution_x
    H = sc.render.resolution_y
    i = frame - 1
    im = mo["image"][src_offset + i]
    wl = mo["world"][src_offset + i]
    if lens:
        cam.data.lens = lens
    f_px = cam.data.lens / cam.data.sensor_width * W
    feet = [29, 30, 31, 32, 27, 28]
    v_top = im[0][1]
    v_feet = max(im[j][1] for j in feet)
    # actor's source frame aspect may differ from the render's: compare in units of image height
    h_px = (v_feet - v_top) * H
    real = (wl[0].z - min(wl[j].z for j in feet)) * scale
    if h_px <= 1 or real <= 0.05:
        raise ValueError("subject not measurable on that frame; pick another")
    D = f_px * real / h_px
    hips = roots[i]
    u_h = (im[23][0] + im[24][0]) / 2
    src_w, src_h = mo.get("width", W), mo.get("height", H)
    # map the source's horizontal position into the render frame's width (centre-anchored)
    u_r = 0.5 + (u_h - 0.5) * (src_w / src_h) / (W / H)
    Xc = hips.x - (u_r - 0.5) * W * D / f_px
    Zc = (v_feet - 0.5) * H * D / f_px
    cam.location = Vector((Xc, hips.y - D, Zc))
    cam.rotation_euler = (math.radians(90), 0, 0)
    return {"distance": round(D, 3), "height": round(Zc, 3), "lens": cam.data.lens}


# ---------------------------------------------------------------- BVH (the open interchange format)
# Any BVH skeleton (CMU, 100STYLE, Mixamo, SMPL/ExMR exports...) is read into the same per-frame
# landmark layout pose.py writes, so one retarget path serves captured video and mocap libraries.
# Joints are found by STRUCTURE, not exact names: naming conventions disagree (CMU "LeftShoulder"
# is a clavicle; 100STYLE "LeftShoulder" is the upper arm), but every humanoid has
# hand <- forearm <- upper arm and foot <- shin <- thigh.
import re as _re

VRM_NAMES = {  # our bone -> VRM 1.0 humanoid bone name, for exporters / other rigs
    "hips": "hips", "spine": "spine", "chest": "chest", "neck": "neck", "head": "head",
    "shoulder.L": "leftShoulder", "upper_arm.L": "leftUpperArm", "forearm.L": "leftLowerArm", "hand.L": "leftHand",
    "shoulder.R": "rightShoulder", "upper_arm.R": "rightUpperArm", "forearm.R": "rightLowerArm", "hand.R": "rightHand",
    "thigh.L": "leftUpperLeg", "shin.L": "leftLowerLeg", "foot.L": "leftFoot",
    "thigh.R": "rightUpperLeg", "shin.R": "rightLowerLeg", "foot.R": "rightFoot",
}


def _side(name):
    """'L' / 'R' / None from a bone name in any common convention: LeftArm, L_Ankle, LThumb,
    hand.L, upperarm_l, mixamorig:RightFoot, leftUpperLeg."""
    n = name.split(":")[-1]
    low = n.lower()
    for side, word in (("L", "left"), ("R", "right")):
        c = side.lower()
        if word in low or low.endswith((f".{c}", f"_{c}")) or _re.match(rf"^{c}[_.]", low) \
                or _re.match(rf"^{side}[A-Z]", n):
            return side
    return None


def _depth(b):
    d = 0
    while b.parent:
        d, b = d + 1, b.parent
    return d


def resolve_skeleton(arm_obj):
    """Map roles -> bone names on an imported BVH armature."""
    bones = arm_obj.data.bones
    roles = {}

    def pick(pattern, side):
        c = [b for b in bones if _re.search(pattern, b.name, _re.I) and _side(b.name) == side]
        return min(c, key=_depth) if c else None

    for s in ("L", "R"):
        hand = pick(r"hand|wrist", s)
        foot = pick(r"foot|ankle", s)
        if not hand or not foot:
            raise ValueError(f"BVH: can't find the {s} hand/foot in {[b.name for b in bones]}")
        fore = hand.parent
        upper = fore.parent
        shin = foot.parent
        thigh = shin.parent
        toe = foot.children[0] if foot.children else None
        roles.update({f"hand.{s}": hand.name, f"forearm.{s}": fore.name, f"upper_arm.{s}": upper.name,
                      f"foot.{s}": foot.name, f"shin.{s}": shin.name, f"thigh.{s}": thigh.name,
                      f"toe.{s}": toe.name if toe else None})
    head = min([b for b in bones if _re.search(r"head", b.name, _re.I) and not _side(b.name)] or
               [b for b in bones if _re.search(r"neck", b.name, _re.I)], key=_depth)
    roles["head"] = head.name
    roles["root"] = min(bones, key=_depth).name
    return roles


def load_bvh(path, fps=None, start=None, end=None, height=1.75, speed=1.0):
    """Import a BVH and sample it into motion.json's layout (in memory). Returns the mo dict.

    fps: output frame rate (default: the scene's). start/end: source seconds to keep.
    height: the performer is rescaled to this standing height (metres). speed: playback rate
    (cadence): 1.2 plays the clip 20% faster.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=str(path), global_scale=1.0, frame_start=1, use_fps_scale=False,
                            update_scene_fps=False, update_scene_duration=False, rotate_mode="NATIVE",
                            axis_forward="-Z", axis_up="Y")
    src = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    act = src.animation_data.action
    # BVH "Frame Time" is not kept by the importer; read it from the file
    with open(path, errors="ignore") as fh:
        m = _re.search(r"Frame Time:\s*([\d.eE+-]+)", fh.read())
    dt = float(m.group(1)) if m else 1 / 30
    mo = sample_armature(src, src_fps=1 / dt, fps=fps, start=start, end=end, height=height, speed=speed)
    mo["source"] = str(path)
    mo.pop("neck_base", None)
    # remove the imported armature + its action
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.data.actions.remove(act)
    return mo


def sample_armature(src, src_fps, fps=None, start=None, end=None, height=1.75, speed=1.0, scale="first"):
    """Sample any animated humanoid armature (BVH, glTF, FBX: Mixamo, Quaternius, VRM...) into
    motion.json's layout, from its active action. Joints are found by structure
    (resolve_skeleton), so any naming works. Returns the mo dict; the armature is left in place.

    src_fps: the action's frames per second. start/end: source seconds. height: the performer
    is rescaled to this standing height. scale="first" measures the height on the first frame
    (BVH clips start standing); "rest" measures it on the rest pose (clips that start crouched,
    seated or lying down).
    """
    sc = bpy.context.scene
    act = src.animation_data.action
    f0, f1 = act.frame_range
    dt = 1.0 / src_fps
    fps = fps or (sc.render.fps / sc.render.fps_base)
    roles = resolve_skeleton(src)
    pb = src.pose.bones
    W = src.matrix_world

    def pos(name, tail=False):
        b = pb[name]
        return W @ (b.tail if tail else b.head)

    def joints():
        P = [Vector((0, 0, 0))] * 33
        for s, (hip, knee, ank, toe, heel, sh, el, wr, hand) in {
                "L": (23, 25, 27, 31, 29, 11, 13, 15, (17, 19, 21)),
                "R": (24, 26, 28, 32, 30, 12, 14, 16, (18, 20, 22))}.items():
            P[hip] = pos(roles[f"thigh.{s}"])
            P[knee] = pos(roles[f"shin.{s}"])
            P[ank] = pos(roles[f"foot.{s}"])
            P[toe] = pos(roles[f"toe.{s}"], tail=True) if roles[f"toe.{s}"] else pos(roles[f"foot.{s}"], tail=True)
            fwd = (P[toe] - P[ank])
            P[heel] = P[ank] - fwd.normalized() * fwd.length * 0.25 + Vector((0, 0, -0.02 * fwd.length))
            P[sh] = pos(roles[f"upper_arm.{s}"])
            P[el] = pos(roles[f"forearm.{s}"])
            P[wr] = pos(roles[f"hand.{s}"])
            for j in hand:
                P[j] = pos(roles[f"hand.{s}"], tail=True)
        side = (P[11] - P[12])
        hc = (pos(roles["head"]) + pos(roles["head"], tail=True)) / 2
        P[7] = hc + side.normalized() * side.length * 0.2
        P[8] = hc - side.normalized() * side.length * 0.2
        P[0] = hc
        return P

    head_parent = pb[roles["head"]].parent  # the neck bone, when the rig has one

    def ear_height(P):
        hip_c = (P[23] + P[24]) / 2
        rel = [p - hip_c for p in P]
        low = min(rel[j].z for j in (27, 28, 29, 30, 31, 32))
        return (rel[7].z + rel[8].z) / 2 - low

    t0 = start or 0.0
    t1 = end if end is not None else (f1 - f0) * dt
    n = int((t1 - t0) * fps / speed) + 1
    frames, roots, necks = [], [], []
    for k in range(n):
        sf = f0 + (t0 + k * speed / fps) / dt
        sc.frame_set(int(sf), subframe=sf - int(sf))
        P = joints()
        hip_c = (P[23] + P[24]) / 2
        frames.append([p - hip_c for p in P])
        roots.append(hip_c.copy())
        necks.append((W @ head_parent.head - hip_c) if head_parent else None)
    # rescale to metres at the requested height (head-top ~ 1.08 x ear height above the feet)
    if scale == "rest":
        src.data.pose_position = "REST"
        bpy.context.view_layer.update()
        tall = ear_height(joints())
        src.data.pose_position = "POSE"
        bpy.context.view_layer.update()
    else:
        first = frames[0]
        low = min(first[j].z for j in (27, 28, 29, 30, 31, 32))
        tall = (first[7].z + first[8].z) / 2 - low
    k_s = height / (tall * 1.08) if tall > 1e-6 else 1.0
    world = [[p * k_s for p in fr] for fr in frames]
    roots = [r * k_s for r in roots]
    necks = [q * k_s if q is not None else None for q in necks]

    def med(vals):
        v = sorted(vals)
        return v[len(v) // 2]

    def seg(a, b):
        mid = lambda P, i: (P[i[0]] + P[i[1]]) / 2 if isinstance(i, tuple) else P[i]
        return med([(mid(P, a) - mid(P, b)).length for P in world])

    lengths = {"torso": seg((23, 24), (11, 12)), "shoulder_width": seg(11, 12), "hip_width": seg(23, 24),
               "neck": seg((11, 12), (7, 8)), "upper_arm": seg(11, 13), "forearm": seg(13, 15),
               "hand": seg(15, 17) / 1.8, "thigh": seg(23, 25), "shin": seg(25, 27), "foot": seg(27, 31),
               "heel": seg(27, 29)}
    # "neck_base": hip-relative base of the neck bone per frame (None if the rig has none). Not used
    # by retarget; clips.py uses it to aim the head on rigs whose shoulders sit off the neck line.
    return {"source": src.name, "fps": fps, "frames": n, "world": world, "root": roots,
            "valid": [True] * n, "lengths": lengths, "bvh_roles": roles, "neck_base": necks}


def export_bvh(arm, path, start=None, end=None, names="vrm"):
    """Write the keyed armature as a standard Y-up BVH (Blender's own exporter writes Z-up).
    names="vrm" uses VRM 1.0 humanoid joint names (leftUpperArm...), "rig" keeps ours.
    Channels: root Xposition Yposition Zposition, every joint Zrotation Xrotation Yrotation."""
    sc = bpy.context.scene
    start = start or sc.frame_start
    end = end or sc.frame_end
    C = Matrix.Rotation(math.radians(-90), 4, "X")   # Blender Z-up -> BVH Y-up
    Ci = C.inverted()
    extra = {"hip.L": "leftPelvis", "hip.R": "rightPelvis"}
    nm = (lambda b: VRM_NAMES.get(b, extra.get(b, b))) if names == "vrm" else (lambda b: b)
    bones = arm.data.bones
    order = [b for b, _, _ in BONES]
    lines = ["HIERARCHY"]

    def write(bname, depth):
        b = bones[bname]
        ind = "\t" * depth
        off = b.head_local if b.parent is None else b.head_local - b.parent.head_local
        off = (C @ off.to_4d()).to_3d()
        kind = "ROOT" if b.parent is None else "JOINT"
        lines.append(f"{ind}{kind} {nm(bname)}")
        lines.append(f"{ind}{{")
        lines.append(f"{ind}\tOFFSET {off.x:.6f} {off.y:.6f} {off.z:.6f}")
        if b.parent is None:
            lines.append(f"{ind}\tCHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
        else:
            lines.append(f"{ind}\tCHANNELS 3 Zrotation Xrotation Yrotation")
        kids = [c for c in order if bones[c].parent and bones[c].parent.name == bname]
        for c in kids:
            write(c, depth + 1)
        if not kids:
            tail = (C @ (b.tail_local - b.head_local).to_4d()).to_3d()
            lines.extend([f"{ind}\tEnd Site", f"{ind}\t{{",
                          f"{ind}\t\tOFFSET {tail.x:.6f} {tail.y:.6f} {tail.z:.6f}", f"{ind}\t}}"])
        lines.append(f"{ind}}}")

    write(order[0], 0)
    fps = sc.render.fps / sc.render.fps_base
    lines += ["MOTION", f"Frames: {end - start + 1}", f"Frame Time: {1.0 / fps:.6f}"]
    prev = {}
    for f in range(start, end + 1):
        sc.frame_set(f)
        row = []
        for bname in order:
            b, pb = bones[bname], arm.pose.bones[bname]
            if b.parent:
                pp = arm.pose.bones[b.parent.name]
                m = b.parent.matrix_local @ pp.matrix.inverted() @ pb.matrix @ b.matrix_local.inverted()
            else:
                m = pb.matrix @ b.matrix_local.inverted()
            t, ti = Matrix.Translation(b.head_local), Matrix.Translation(-b.head_local)
            m = ti @ m @ t
            my = C @ m @ Ci
            if b.parent is None:
                loc = (C @ (m.to_translation() + b.head_local).to_4d()).to_3d()
                row += [loc.x, loc.y, loc.z]
            e = my.to_euler("YXZ", prev.get(bname)) if bname in prev else my.to_euler("YXZ")
            prev[bname] = e
            row += [math.degrees(e.z), math.degrees(e.x), math.degrees(e.y)]
        lines.append(" ".join(f"{v:.6f}" for v in row))
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
