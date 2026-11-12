"""bodies: human bodies generated from rig.py's skeleton, for judging and showing motion.
Runs inside Blender. Part of ai-animate.

    import rig, bodies
    arm = rig.armature(mo)
    bodies.body(arm, build=1.0)     # smooth skinned human: flat-soled feet, soft knees/elbows/hips
    bodies.mannequin(arm)           # segmented capsules + ball joints, for debugging motion

Also the placement helpers other modules build on (ai-adapt's parts.py imports them):
  _L(arm, bone)        rest length of a bone
  _put(obj, arm, bone) place an object in a bone's frame and rigidly parent it
  joint(arm, bone)     a ball joint at a bone's head (at=0) or tail (at=1)

Bone-local axes (rest T-pose): Y along the bone (head -> tail); local Z is the character's FRONT
on torso, head, arms and legs; on torso/head local X is the character's LEFT.
"""
import math

import bkit as k
import rig
from mathutils import Euler, Matrix, Vector


def _L(arm, bone):
    return arm.data.bones[bone].length


def _put(obj, arm, bone, at=0.5, off=(0.0, 0.0), rot=(0, 0, 0), along=0.0):
    """Place obj (built around its own origin) in the bone's frame, then parent it."""
    local = obj.matrix_basis.copy()
    m = rig.bone_matrix(arm, bone, at) @ Matrix.Translation((off[0], along, off[1])) \
        @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()
    obj.matrix_world = m @ local
    rig.attach(obj, arm, bone)
    return obj


# ---------------------------------------------------------------- primitives on bones
def joint(arm, bone, at=0.0, r=0.05, mat=None, segments=24, name=None):
    """Ball joint at the head (at=0) or tail (at=1) of a bone."""
    o = k.sphere(r, segments=segments, rings=segments // 2, mat=mat, name=name or f"joint_{bone}_{at}")
    return _put(o, arm, bone, at)


# ---------------------------------------------------------------- diagnostic / neutral body
def mannequin(arm, color="#c9c4bc", joint_color="#9a958d"):
    """A neutral, smooth, human-proportioned body (capsule limbs, pelvis, ribcage, head). Use it to
    judge MOTION on its own: if a walk looks wrong on the mannequin, the motion is the problem;
    if it looks right here but wrong on the character, the character design is."""
    skin = k.material(color, roughness=0.55, name="mannequin")
    jm = k.material(joint_color, roughness=0.5, name="mannequin_joint")
    o = []

    def limb(bone, r0, r1):
        L = _L(arm, bone)
        c = k.cone(r0, r1, L, rot=(-90, 0, 0), mat=skin, segments=32, name=f"mq_{bone}")
        k.shade_smooth(c)
        o.append(_put(c, arm, bone, 0.5))
        o.append(joint(arm, bone, 0.0, r0 * 1.02, jm, 24, name=f"mq_j_{bone}"))

    for s in ("L", "R"):
        limb(f"thigh.{s}", 0.075, 0.055)
        limb(f"shin.{s}", 0.052, 0.04)
        limb(f"upper_arm.{s}", 0.045, 0.038)
        limb(f"forearm.{s}", 0.036, 0.028)
        f = k.cube(1.0, scale=(0.09, _L(arm, f"foot.{s}") * 1.25, 0.06), mat=skin, bevel=0.15, name=f"mq_foot_{s}")
        o.append(_put(f, arm, f"foot.{s}", 0.5, (0, -0.01)))
        h = k.sphere(0.045, mat=skin, scale=(0.8, 1.4, 0.5), name=f"mq_hand_{s}")
        o.append(_put(h, arm, f"hand.{s}", 0.5))
    pel = k.sphere(0.16, mat=skin, scale=(1.05, 0.8, 0.75), name="mq_pelvis")
    o.append(_put(pel, arm, "hips", 0.25))
    belly = k.sphere(0.13, mat=skin, scale=(1.0, 1.3, 0.8), name="mq_belly")
    o.append(_put(belly, arm, "spine", 0.5))
    ribs = k.sphere(0.17, mat=skin, scale=(1.05, 1.25, 0.75), name="mq_ribs")
    o.append(_put(ribs, arm, "chest", 0.45))
    for s in ("L", "R"):
        sh = k.sphere(0.06, mat=skin, name=f"mq_delt_{s}")
        o.append(_put(sh, arm, f"shoulder.{s}", 1.0))
    nk = k.cylinder(0.05, _L(arm, "neck"), rot=(-90, 0, 0), mat=skin, segments=24, name="mq_neck")
    o.append(_put(nk, arm, "neck", 0.5))
    hd = k.sphere(0.11, mat=skin, scale=(0.85, 1.15, 1.0), name="mq_head")
    o.append(_put(hd, arm, "head", 0.45))
    nose = k.cone(0.02, 0.0, 0.04, rot=(90, 0, 0), mat=skin, segments=12, name="mq_nose")
    o.append(_put(nose, arm, "head", 0.4, (0, 0.11)))  # shows which way the head faces
    return o


# ---------------------------------------------------------------- a smooth, skinned human body
def body(arm, color="#cdbfb3", build=1.0, name="body", subdiv=2):
    """A continuous skinned human generated from the skeleton: a skin-modifier mesh with anatomical
    radii at each joint, weighted to the nearest bones with smooth falloff (so knees, elbows and
    hips bend softly), subdivided. build scales girth (0.85 slim .. 1.25 heavy).
    Fully generated in code: no external model, no weight painting."""
    import bpy
    import bmesh

    b = arm.data.bones
    W = arm.matrix_world
    head = lambda n: W @ b[n].head_local
    tail = lambda n: W @ b[n].tail_local
    g = build
    # (point, radius_x, radius_y)  - radii in metres, x across the body, y front/back
    P = {}
    P["pelvis"] = (head("hips"), 0.15 * g, 0.11 * g)
    P["waist"] = (tail("hips"), 0.135 * g, 0.095 * g)
    P["belly"] = (tail("spine"), 0.15 * g, 0.105 * g)
    P["chest"] = (head("chest").lerp(tail("chest"), 0.6), 0.17 * g, 0.12 * g)
    P["neck0"] = (tail("chest"), 0.065, 0.065)
    P["neck1"] = (tail("neck"), 0.05, 0.055)
    hh = b["head"]
    P["jaw"] = (head("head").lerp(tail("head"), 0.2), 0.07, 0.08)
    P["skull"] = (head("head").lerp(tail("head"), 0.5), 0.095, 0.11)
    P["crown"] = (head("head").lerp(tail("head"), 0.78), 0.07, 0.08)
    for s in ("L", "R"):
        P[f"hip{s}"] = (head(f"thigh.{s}"), 0.095 * g, 0.095 * g)
        P[f"thighm{s}"] = (head(f"thigh.{s}").lerp(tail(f"thigh.{s}"), 0.4), 0.082 * g, 0.082 * g)
        P[f"knee{s}"] = (head(f"shin.{s}"), 0.054 * g, 0.056 * g)
        P[f"calf{s}"] = (head(f"shin.{s}").lerp(tail(f"shin.{s}"), 0.3), 0.058 * g, 0.064 * g)
        P[f"ankle{s}"] = (tail(f"shin.{s}"), 0.034, 0.036)
        # Sole: midfoot/heel, ball and toe sit ON the ground plane in rest pose (the rest pose stands flat),
        # centres sunk 20% of their radius so subdivision's shrink lands the underside at z~0.
        a, t = tail(f"shin.{s}"), tail(f"foot.{s}")
        hf = Vector((t.x - a.x, t.y - a.y, 0.0))
        fl = hf.length
        hf.normalize()
        rh, rb, rt = 0.027, 0.033, 0.024
        # the heel is the back of the midfoot tube (a separate heel point makes a knob)
        P[f"mid{s}"] = (Vector((a.x, a.y, 0)) + hf * fl * 0.08 + Vector((0, 0, rb * 0.75)), rb, rb)
        P[f"ball{s}"] = (Vector((a.x, a.y, 0)) + hf * fl * 0.72 + Vector((0, 0, rb * 0.95)), rb, rb)
        P[f"toe{s}"] = (Vector((a.x, a.y, 0)) + hf * fl * 1.0 + Vector((0, 0, rt * 0.95)), rt, rt)
        P[f"delt{s}"] = (head(f"upper_arm.{s}"), 0.062 * g, 0.062 * g)
        P[f"bicep{s}"] = (head(f"upper_arm.{s}").lerp(tail(f"upper_arm.{s}"), 0.45), 0.05 * g, 0.05 * g)
        P[f"elbow{s}"] = (head(f"forearm.{s}"), 0.036 * g, 0.036 * g)
        P[f"fore{s}"] = (head(f"forearm.{s}").lerp(tail(f"forearm.{s}"), 0.35), 0.043 * g, 0.038 * g)
        P[f"wrist{s}"] = (tail(f"forearm.{s}"), 0.028, 0.022)
        P[f"hand{s}"] = (tail(f"hand.{s}"), 0.038, 0.014)
    E = [("pelvis", "waist"), ("waist", "belly"), ("belly", "chest"), ("chest", "neck0"),
         ("neck0", "neck1"), ("neck1", "jaw"), ("jaw", "skull"), ("skull", "crown")]
    for s in ("L", "R"):
        E += [("pelvis", f"hip{s}"), (f"hip{s}", f"thighm{s}"), (f"thighm{s}", f"knee{s}"),
              (f"knee{s}", f"calf{s}"), (f"calf{s}", f"ankle{s}"), (f"ankle{s}", f"mid{s}"),
              (f"mid{s}", f"ball{s}"), (f"ball{s}", f"toe{s}"),
              ("chest", f"delt{s}"), (f"delt{s}", f"bicep{s}"), (f"bicep{s}", f"elbow{s}"),
              (f"elbow{s}", f"fore{s}"), (f"fore{s}", f"wrist{s}"), (f"wrist{s}", f"hand{s}")]
    keys = list(P)
    me = bpy.data.meshes.new(name + "_skel")
    me.from_pydata([tuple(P[kk][0]) for kk in keys], [(keys.index(x), keys.index(y)) for x, y in E], [])
    skel = bpy.data.objects.new(name + "_skel", me)
    bpy.context.scene.collection.objects.link(skel)
    sk = skel.modifiers.new("skin", "SKIN")
    sk.use_smooth_shade = True
    sk.branch_smoothing = 0.6
    for i, kk in enumerate(keys):
        sv = me.skin_vertices[0].data[i]
        sv.radius = (P[kk][1], P[kk][2])
        sv.use_root = kk == "pelvis"
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(skel.evaluated_get(dg))
    bpy.data.objects.remove(skel, do_unlink=True)
    bpy.data.meshes.remove(me)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    # weights: each vertex -> nearest bone segments, Gaussian falloff, top 3, normalized
    deform = [n for n in ("hips", "spine", "chest", "neck", "head") ] + \
             [f"{p}.{s}" for s in ("L", "R") for p in ("upper_arm", "forearm", "hand", "thigh", "shin", "foot")]
    segs = {n: (head(n), tail(n)) for n in deform}
    groups = {n: obj.vertex_groups.new(name=n) for n in deform}

    def dist(p, a, c):
        ab = c - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        return (p - (a + ab * t)).length

    sigma = 0.045
    ank_z = {s: tail(f"shin.{s}").z for s in ("L", "R")}
    for v in mesh.vertices:
        p = obj.matrix_world @ v.co
        # everything below the ankle belongs to the foot alone (a rigid sole that stays flat)
        side = "L" if (p - tail("shin.L")).length < (p - tail("shin.R")).length else "R"
        if p.z < ank_z[side] - 0.012 and dist(p, *segs[f"foot.{side}"]) < 0.12:
            groups[f"foot.{side}"].add([v.index], 1.0, "REPLACE")
            continue
        ds = sorted(((dist(p, *segs[n]), n) for n in deform))[:3]
        d0 = ds[0][0]
        ws = [(math.exp(-((d - d0) / sigma) ** 2), n) for d, n in ds]
        tot = sum(w for w, _ in ws)
        for w, n in ws:
            if w / tot > 0.02:
                groups[n].add([v.index], w / tot, "REPLACE")
    obj.parent = arm
    am = obj.modifiers.new("armature", "ARMATURE")
    am.object = arm
    if subdiv:
        sd = obj.modifiers.new("subsurf", "SUBSURF")
        sd.levels = sd.render_levels = subdiv
    for poly in mesh.polygons:
        poly.use_smooth = True
    k.assign(obj, k.material(color, roughness=0.5, subsurface=0.08, name=name + "_mat"))
    return obj
