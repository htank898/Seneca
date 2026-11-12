"""parts: a kitbash library for building characters on rig.py's armature. Runs inside Blender.

Every part is modelled in its bone's local frame and rigidly parented to that bone, so a
character is just a list of parts: no weight painting, no deformation, no hallucination.

Bone-local axes (rest T-pose): Y runs along the bone (head -> tail). On torso, head, arms and
legs, local Z points to the character's FRONT; on the torso and head, local X is the
character's LEFT. `at` is the fraction along the bone (0 head .. 1 tail); `off=(x, z)` nudges
across it in metres.

    import bkit as k, rig, parts as p
    arm = rig.armature(mo)
    pal = p.palette(armor="#b8321f", accent="#e0a526", frame="#3b3d42", joint="#8d9096", eyes="#5df2ff")
    p.biomech(arm, pal)                 # the full preset: a masked biomechanical warrior
    # ...or build piece by piece:
    p.shell(arm, "shin.L", 0.06, 0.045, mat=pal["armor"])
    p.joint(arm, "shin.L", at=0, r=0.05, mat=pal["joint"])

Parts: joint, rod, shell, plate, piston, mask, crest, spikes, claws, boot, chest_core,
shoulder_pad, pelvis. All return the created object(s); all take name=.
"""
import math

import bkit as k
import rig  # ai-animate: the skeleton parts attach to
from bodies import _L, _put, joint  # ai-animate: shared placement helpers
from mathutils import Euler, Matrix, Vector


def palette(armor="#b8321f", accent="#e0a526", frame="#3b3d42", joint="#8d9096", eyes="#5df2ff",
            eye_strength=12.0):
    """Material set for a character. Hex values are sRGB (as in the concept art)."""
    return {
        "armor": k.material(armor, roughness=0.32, coat=0.6, name="armor"),
        "accent": k.material(accent, roughness=0.28, metallic=0.85, name="accent"),
        "frame": k.material(frame, roughness=0.45, metallic=0.6, name="frame"),
        "joint": k.material(joint, roughness=0.22, metallic=1.0, name="joint"),
        "eyes": k.material("#000000", emission=eyes, emission_strength=eye_strength, roughness=1.0,
                           name="eyes"),
        "hex": {"armor": armor, "accent": accent, "frame": frame, "joint": joint, "eyes": eyes},
    }




def rod(arm, bone, r=0.015, a=0.0, b=1.0, mat=None, segments=12, off=(0, 0), name=None):
    """Thin cylinder along the bone from a to b: inner frame, cables, axles."""
    L = _L(arm, bone)
    o = k.cylinder(r, (b - a) * L, rot=(-90, 0, 0), mat=mat, segments=segments, name=name or f"rod_{bone}")
    return _put(o, arm, bone, (a + b) / 2, off)


def shell(arm, bone, r0=0.06, r1=0.045, a=0.08, b=0.92, sides=8, mat=None, squash=(1.0, 1.0),
          off=(0.0, 0.0), bevel=0.006, twist=0.0, name=None):
    """Faceted tapered armour sleeve along a bone. squash=(x, z) flattens it (z = front/back)."""
    L = _L(arm, bone)
    o = k.cone(r0, r1, (b - a) * L, rot=(-90, 0, twist), scale=(squash[0], 1, squash[1]), mat=mat,
               segments=sides, bevel=bevel, name=name or f"shell_{bone}")
    # cone is built along +Z from -depth/2..+depth/2 with radius1 at the bottom; after rot it's along +Y
    return _put(o, arm, bone, (a + b) / 2, off)


def plate(arm, bone, size=(0.1, 0.1, 0.02), at=0.5, off=(0.0, 0.0), rot=(0, 0, 0), mat=None,
          bevel=0.005, name=None):
    """Bevelled box: armour plates, fins, panels. size=(x, along-bone, z)."""
    o = k.cube(1.0, scale=size, mat=mat, bevel=bevel, name=name or f"plate_{bone}")
    return _put(o, arm, bone, at, off, rot)


def piston(arm, bone, r=0.012, off=(0.0, -0.03), a=0.15, b=0.85, mat_outer=None, mat_inner=None, name=None):
    """Two nested rods: a hydraulic look behind a limb (off z<0 = behind)."""
    outer = rod(arm, bone, r * 1.6, a, (a + b) / 2 + 0.05, mat_outer, off=off, name=(name or f"piston_{bone}") + "_o")
    inner = rod(arm, bone, r, (a + b) / 2 - 0.05, b, mat_inner, off=off, name=(name or f"piston_{bone}") + "_i")
    return outer, inner


# ---------------------------------------------------------------- character pieces
def mask(arm, mat, eye_mat, w=0.17, h=0.2, d=0.07, at=0.45, style="hau", brow=None, name="mask"):
    """A faceplate on the head bone with glowing eye slits. style: hau (broad, flat brow),
    kaukau (tall, narrow), pakari (wide jaw), kanohi-free shapes are fine too: it's just plates."""
    head = "head"
    parts = []
    Lh = _L(arm, head)
    # skull core behind the mask
    parts.append(_put(k.sphere(w * 0.52, mat=brow or mat, segments=24, rings=12, scale=(1, 1.15, 1.05),
                               name=f"{name}_skull"), arm, head, at, (0, -d * 0.6)))
    shapes = {
        "hau": dict(sx=1.0, sy=1.0, jaw=0.55, brow_w=1.15, slit=(0.045, 0.018), tilt=8),
        "kaukau": dict(sx=0.8, sy=1.2, jaw=0.45, brow_w=0.9, slit=(0.03, 0.03), tilt=4),
        "pakari": dict(sx=1.15, sy=0.95, jaw=0.8, brow_w=1.25, slit=(0.05, 0.014), tilt=12),
    }
    s = shapes.get(style, shapes["hau"])
    # face plate
    parts.append(plate(arm, head, (w * s["sx"], h * s["sy"] * 0.62, d * 0.35), at=at + 0.04,
                       off=(0, d * 0.55), rot=(-s["tilt"], 0, 0), mat=mat, bevel=0.012, name=f"{name}_face"))
    # brow ridge
    parts.append(plate(arm, head, (w * s["brow_w"], h * 0.13, d * 0.5), at=at + 0.3,
                       off=(0, d * 0.7), rot=(-18, 0, 0), mat=mat, bevel=0.01, name=f"{name}_brow"))
    # jaw / mouth guard
    parts.append(plate(arm, head, (w * s["jaw"], h * 0.22, d * 0.45), at=at - 0.28,
                       off=(0, d * 0.62), rot=(10, 0, 0), mat=mat, bevel=0.01, name=f"{name}_jaw"))
    # eyes: emissive slits standing just proud of the face plate
    ex, ey = s["slit"]
    for side in (-1, 1):
        parts.append(plate(arm, head, (ex, ey, 0.012), at=at + 0.18, off=(side * w * 0.24, d * 0.76),
                           rot=(-s["tilt"], 0, side * -12), mat=eye_mat, bevel=0.003, name=f"{name}_eye{side}"))
    # cheek fins
    for side in (-1, 1):
        parts.append(plate(arm, head, (0.012, h * 0.45, d * 0.9), at=at, off=(side * w * 0.55, d * 0.25),
                           rot=(0, 0, side * 10), mat=mat, bevel=0.004, name=f"{name}_cheek{side}"))
    return parts


def crest(arm, mat, n=3, height=0.09, depth=0.12, bone="head", name="crest"):
    """Fins along the top/back of the head, getting shorter toward the back."""
    out = []
    for i in range(n):
        f = 1 - i / max(n, 1) * 0.5
        out.append(plate(arm, bone, (0.012, height * f, depth * f), at=0.95 - i * 0.06,
                         off=(0, -0.02 - i * 0.045), rot=(25 + i * 12, 0, 0), mat=mat, bevel=0.003,
                         name=f"{name}{i}"))
    return out


def spikes(arm, bone, n=3, length=0.06, r=0.014, mat=None, side="back", a=0.2, b=0.9, name=None):
    """Cone spikes along a bone, pointing back (side='back'), out (x) or forward."""
    out = []
    dirs = {"back": (0, 0, -1), "front": (0, 0, 1), "left": (1, 0, 0), "right": (-1, 0, 0)}
    dx, _, dz = dirs[side]
    rot = {"back": (180, 0, 0), "front": (0, 0, 0), "left": (0, 90, 0), "right": (0, -90, 0)}[side]
    for i in range(n):
        t = a + (b - a) * (i / max(n - 1, 1))
        o = k.cone(r, 0.0, length, rot=rot, mat=mat, segments=8, name=f"{name or 'spike_' + bone}{i}")
        out.append(_put(o, arm, bone, t, (dx * (r * 2.5), dz * (r * 2.5 + length / 2))))
    return out


def claws(arm, side="L", n=3, length=0.08, r=0.012, mat=None, spread=22, name=None):
    """Fingers as tapered prongs off the hand bone."""
    bone = f"hand.{side}"
    out = []
    for i in range(n):
        ang = (i - (n - 1) / 2) * spread
        o = k.cone(r, r * 0.25, length, rot=(-90, 0, 0), mat=mat, segments=6,
                   name=f"{name or 'claw_' + side}{i}")
        out.append(_put(o, arm, bone, 1.0, (0, 0), rot=(0, 0, 0), along=length / 2 - 0.01))
        # fan the prongs: rotate around the hand's local Z after parenting
        o.rotation_euler.rotate_axis("Z", math.radians(ang))
    # thumb
    o = k.cone(r * 1.1, r * 0.3, length * 0.75, rot=(-90, 0, 0), mat=mat, segments=6,
               name=f"{name or 'claw_' + side}_thumb")
    out.append(_put(o, arm, bone, 0.55, (0, r * 2.6), rot=(-40, 0, 0), along=0.0))
    return out


def boot(arm, side="L", mat=None, sole=None, w=0.09, h=0.05, name=None):
    """Armoured foot: a wedge along the foot bone plus a heel block."""
    bone = f"foot.{side}"
    L = _L(arm, bone)
    a = plate(arm, bone, (w, L * 1.15, h), at=0.5, off=(0, -h * 0.15), mat=mat, bevel=0.012,
              name=f"{name or 'boot_' + side}")
    b = plate(arm, f"shin.{side}", (w * 0.9, 0.06, w * 0.9), at=1.0, off=(0, -w * 0.15), mat=sole or mat,
              bevel=0.01, name=f"{name or 'boot_' + side}_heel")
    return a, b


def chest_core(arm, mat, accent=None, w=0.34, d=0.2, name="chest"):
    """Torso armour: chest plate, ab plates and a back frame."""
    out = [
        plate(arm, "chest", (w, _L(arm, "chest") * 1.15, d * 0.5), at=0.55, off=(0, d * 0.28), rot=(-6, 0, 0),
              mat=mat, bevel=0.02, name=f"{name}_plate"),
        plate(arm, "chest", (w * 0.85, _L(arm, "chest") * 1.1, d * 0.5), at=0.5, off=(0, -d * 0.2),
              mat=accent or mat, bevel=0.015, name=f"{name}_back"),
        plate(arm, "spine", (w * 0.6, _L(arm, "spine") * 0.8, d * 0.45), at=0.5, off=(0, d * 0.18),
              mat=mat, bevel=0.015, name=f"{name}_abs"),
    ]
    # visible spine column (the "inner frame" look)
    out.append(rod(arm, "spine", 0.03, 0.0, 1.0, accent, off=(0, -d * 0.1), name=f"{name}_column"))
    return out


def shoulder_pad(arm, side="L", mat=None, size=0.11, name=None):
    bone = f"upper_arm.{side}"
    return plate(arm, bone, (size * 0.9, size * 1.1, size * 1.05), at=0.08, off=(0.0, 0.0),
                 rot=(0, 0, 0), mat=mat, bevel=0.025, name=name or f"pad_{side}")


def pelvis(arm, mat, w=0.28, name="pelvis"):
    return plate(arm, "hips", (w, _L(arm, "hips") * 0.9, 0.16), at=0.35, mat=mat, bevel=0.02, name=name)


# ---------------------------------------------------------------- preset
def biomech(arm, pal, bulk=1.0, style="hau", crest_fins=3, back_spikes=3, seed=1):
    """A complete masked biomechanical warrior: armoured shells over a visible metal frame,
    ball joints, pistons, a faceplate with glowing eyes. bulk scales armour thickness.
    Use it as the starting point and then change what the concept art asks for."""
    A, C, F, J, E = pal["armor"], pal["accent"], pal["frame"], pal["joint"], pal["eyes"]
    b = bulk
    objs = []
    objs += [pelvis(arm, F, 0.26 * b)]
    objs += chest_core(arm, A, C, 0.32 * b, 0.2 * b)
    objs += [rod(arm, "neck", 0.025, 0, 1, F, name="neck_rod"), joint(arm, "neck", 0, 0.04, J)]
    objs += mask(arm, A, E, style=style, brow=F)
    if crest_fins:
        objs += crest(arm, C, crest_fins)
    if back_spikes:
        objs += spikes(arm, "chest", back_spikes, 0.07, 0.016, C, "back", 0.3, 0.9)
    for s in ("L", "R"):
        # arms
        objs += [joint(arm, f"upper_arm.{s}", 0, 0.05 * b, J), shoulder_pad(arm, s, A, 0.12 * b)]
        objs += [rod(arm, f"upper_arm.{s}", 0.018, 0, 1, F)]
        objs += [shell(arm, f"upper_arm.{s}", 0.045 * b, 0.038 * b, 0.25, 0.85, 6, C)]
        objs += [joint(arm, f"forearm.{s}", 0, 0.04 * b, J)]
        objs += [shell(arm, f"forearm.{s}", 0.05 * b, 0.04 * b, 0.12, 0.95, 6, A, squash=(1, 0.85))]
        objs += [joint(arm, f"hand.{s}", 0, 0.03 * b, J)]
        objs += [plate(arm, f"hand.{s}", (0.07, 0.05, 0.03), at=0.3, mat=F, name=f"palm_{s}")]
        objs += claws(arm, s, 3, 0.07, 0.011, C)
        # legs
        objs += [joint(arm, f"thigh.{s}", 0, 0.055 * b, J)]
        objs += [rod(arm, f"thigh.{s}", 0.022, 0, 1, F)]
        objs += [shell(arm, f"thigh.{s}", 0.065 * b, 0.05 * b, 0.12, 0.8, 6, C, squash=(1, 0.9))]
        objs += [joint(arm, f"shin.{s}", 0, 0.05 * b, J)]
        objs += [plate(arm, f"shin.{s}", (0.07 * b, 0.07, 0.04), at=0.02, off=(0, 0.045 * b), rot=(-10, 0, 0),
                       mat=A, name=f"kneecap_{s}")]
        objs += [shell(arm, f"shin.{s}", 0.065 * b, 0.045 * b, 0.12, 0.9, 6, A, squash=(1, 0.95))]
        objs += list(piston(arm, f"shin.{s}", 0.01, (0, -0.05 * b), 0.1, 0.9, F, J))
        objs += [joint(arm, f"foot.{s}", 0, 0.035 * b, J)]
        objs += list(boot(arm, s, A, F, 0.085 * b, 0.05))
    return objs
