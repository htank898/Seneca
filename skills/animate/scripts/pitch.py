"""pitch: baseball pitching from the windup, as a one-shot statistical motion (see motionmodel.py),
plus the ball. Runs inside Blender.

    import rig, pitch
    insts = pitch.instances_from_bvh([path_124_01, path_124_02])     # or from captured video mo's
    model = motionmodel.fit(insts)
    mo, ev = pitch.generate(model, seed=3)          # one new pitch + its event frames (release...)
    arm = rig.armature(mo); rig.retarget(arm, mo, locomotion="root")
    ball = pitch.ball(arm, ev, speed=38.0)           # held in the hand until release, then flies

Events (detected per performance, then every instance is time-warped to the library's median phase):
  start     windup begins (body leaves the set position)
  lift      peak height of the lead (glove-side) leg
  plant     lead foot lands
  release   throwing hand reaches peak speed (ball leaves the hand)
  end       follow-through, release + 0.6 s
Left-handed performances are mirrored to right-handed, so they share one model.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

import bkit as k
import motionmodel as mm
import rig

PAIRS = [(11, 12), (13, 14), (15, 16), (17, 18), (19, 20), (21, 22), (23, 24), (25, 26), (27, 28),
         (29, 30), (31, 32), (1, 4), (2, 5), (3, 6), (7, 8), (9, 10)]
RUBBER_TO_PLATE = 18.44  # m (60 ft 6 in)


def mirror(mo):
    """Left-handed -> right-handed: reflect across the sagittal plane and swap left/right joints."""
    sw = list(range(33))
    for a, b in PAIRS:
        sw[a], sw[b] = b, a
    world = [[Vector((-fr[sw[j]].x, fr[sw[j]].y, fr[sw[j]].z)) for j in range(33)] for fr in mo["world"]]
    root = [Vector((-r.x, r.y, r.z)) for r in mo["root"]]
    out = dict(mo)
    out.update(world=world, root=root)
    return out


def events(mo, skip=4):
    """Detect the pitch events in a rig-style mo (world + root). Returns dict of frame indices + side."""
    W, R, fps = mo["world"], mo["root"], mo["fps"]
    n = len(W)
    pos = lambda i, j: W[i][j] + R[i]
    sp = lambda i, j: (pos(min(i + 1, n - 1), j) - pos(i, j)).length * fps
    rng_ = range(skip, n - 1)
    throw = "R" if max(sp(i, 16) for i in rng_) >= max(sp(i, 15) for i in rng_) else "L"
    wj = 16 if throw == "R" else 15
    lead_ank = 27 if throw == "R" else 28
    release = max(rng_, key=lambda i: sp(i, wj))
    floor = min(pos(i, lead_ank).z for i in rng_)
    lift = max(range(skip, release), key=lambda i: pos(i, lead_ank).z)
    plant = next((i for i in range(lift, release) if pos(i, lead_ank).z < floor + 0.06 and sp(i, lead_ank) < 1.5),
                 max(lift + 1, release - int(0.15 * fps)))
    # windup start: scanning back from the leg lift, the last moment the body was still (set position)
    still = lambda i: max(sp(i, 15), sp(i, 16), sp(i, lead_ank), (R[min(i + 1, n - 1)] - R[i]).length * fps) < 0.35
    start = skip
    run = 0
    for i in range(lift, skip, -1):
        run = run + 1 if still(i) else 0
        if run >= int(0.2 * fps):
            start = i + run - 1
            break
    end = min(n - 1, release + int(0.6 * fps))
    return {"throw": throw, "start": start, "lift": lift, "plant": plant, "release": release, "end": end}


KEYS = ("lift", "plant", "release")


def instances_from_mos(mos, verbose=True):
    """Pitch instances from rig-style mo dicts (BVH-loaded or video-captured with a root path)."""
    cands = []
    for mo in mos:
        ev = events(mo)
        if ev["throw"] == "L":
            mo = mirror(mo)
            ev = events(mo)
        a, b = ev["start"], ev["end"]
        if not (a < ev["lift"] < ev["plant"] < ev["release"] < b):
            if verbose:
                print(f"[model] skip {mo.get('source', '?')}: events out of order {ev}", flush=True)
            continue
        cands.append((mo, ev))
        if verbose:
            fps = mo["fps"]
            print("[model] %s: start->lift %.2fs, lift->plant %.2fs, plant->release %.2fs (throws %s)" % (
                str(mo.get("source", "?")).split("/")[-1], (ev["lift"] - a) / fps, (ev["plant"] - ev["lift"]) / fps,
                (ev["release"] - ev["plant"]) / fps, ev["throw"]), flush=True)
    target = {kk: float(np.median([(ev[kk] - ev["start"]) / (ev["end"] - ev["start"]) for _, ev in cands])) for kk in KEYS}
    insts = []
    for mo, ev in cands:
        inst = mm.instance(mo, ev["start"], ev["end"], cyclic=False, events=[(ev[kk], target[kk]) for kk in KEYS])
        src = str(mo.get("source", "?")).split("/")[-1]
        inst.update(source=src, subject=src.split("_")[0], event_phases=target)
        insts.append(inst)
    return insts


def instances_from_bvh(paths, fps=60, verbose=True):
    return instances_from_mos([rig.load_bvh(p, fps=fps) for p in paths], verbose)


def generate(model, fps=60, person_z=None, wobble=0.5, seed=1, lengths=None, hold_before=0.6, hold_after=0.8,
             tempo=None):
    """One pitch. tempo: optional {"plant->release": seconds, ...} to retime a segment (e.g. pro arm speed).
    Returns (mo, event frames in the output timeline)."""
    rng = np.random.default_rng(seed + 1000)
    base = np.zeros(len(model["sigma"])) if person_z is None else np.asarray(person_z)
    z = base + np.clip(rng.standard_normal(len(base)), -2.5, 2.5) * model["within"] * wobble
    dirs, rt, dur = mm._unvec(model["mean"] + z @ model["components"])
    ph = model["event_phases"]
    # piecewise timing: phase knots -> seconds (optionally retimed per segment)
    knots = [0.0, ph["lift"], ph["plant"], ph["release"], 1.0]
    secs = [kk * dur for kk in knots]
    seg_names = ["start->lift", "lift->plant", "plant->release", "release->end"]
    lens_ = [secs[i + 1] - secs[i] for i in range(4)]
    for i, nm in enumerate(seg_names):
        if tempo and nm in tempo:
            lens_[i] = tempo[nm]
    t_knots = [0.0]
    for L_ in lens_:
        t_knots.append(t_knots[-1] + L_)
    total = t_knots[-1]

    def phase_at(t):
        for i in range(4):
            if t <= t_knots[i + 1] or i == 3:
                u = (t - t_knots[i]) / max(t_knots[i + 1] - t_knots[i], 1e-9)
                return knots[i] + (knots[i + 1] - knots[i]) * min(max(u, 0.0), 1.0)

    lengths = dict(mm.DEFAULT_LENGTHS, **(lengths or {}))
    leg = lengths["thigh"] + lengths["shin"]
    n_body = int(round(total * fps)) + 1
    pre, post = int(hold_before * fps), int(hold_after * fps)
    world, root = [], []
    y = 0.0
    prev_ph = 0.0
    for f in range(n_body):
        p = phase_at(f / fps)
        x = p * (mm.N - 1)
        i0 = int(x)
        i1 = min(i0 + 1, mm.N - 1)
        t = x - i0
        d = dirs[i0] * (1 - t) + dirs[i1] * t
        r = rt[i0] * (1 - t) + rt[i1] * t
        # forward travel: instance speed is per second of ORIGINAL time; integrate over phase instead
        y += r[2] * leg * (p - prev_ph) * dur
        prev_ph = p
        world.append(mm._decode_pose(d, lengths))
        root.append(Vector((r[0] * leg, y, leg + r[1] * leg)))
    world = [world[0]] * pre + world + [world[-1]] * post
    root = [root[0]] * pre + root + [root[-1]] * post
    n = len(world)
    ev = {nm: pre + int(round(t_knots[i] * fps)) for i, nm in enumerate(("start", "lift", "plant", "release", "end"))}
    return ({"source": "pitch-model", "fps": fps, "frames": n, "world": world, "root": root,
             "valid": [True] * n, "lengths": lengths}, ev)


def ball(arm, ev, speed=38.0, target=None, radius=0.0373, side="R", spin=True):
    """A baseball held in the throwing hand until ev['release'], then a ballistic flight toward
    target (default: home plate, 18.44 m in front of the release point at knee-to-chest height)."""
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    mat = k.material("#f4f1ea", roughness=0.45, name="baseball")
    seam = k.material("#c0262d", roughness=0.5, name="seams")
    b = k.sphere(radius, mat=mat, segments=24, rings=12, name="baseball")
    ring = k.torus(radius * 0.98, radius * 0.06, mat=seam, name="seam")
    ring.parent = b
    arm.hide_viewport = False
    hand = f"hand.{side}"

    def hand_pt(f):
        sc.frame_set(f)
        pb = arm.pose.bones[hand]
        h, t = arm.matrix_world @ pb.head, arm.matrix_world @ pb.tail
        return h + (t - h) * 1.15  # in the fingers, just past the hand bone's tip

    rel = ev["release"]
    p_rel = hand_pt(rel)
    fwd = Vector((0, 1, 0))
    tgt = target or Vector((p_rel.x * 0.3, p_rel.y + RUBBER_TO_PLATE - 1.5, 0.75))
    flight = (tgt - p_rel).length / speed
    g = Vector((0, 0, -9.81))
    v0 = (tgt - p_rel - 0.5 * g * flight * flight) / flight
    for f in range(sc.frame_start, sc.frame_end + 1):
        if f <= rel:
            b.location = hand_pt(f)
        else:
            t = (f - rel) / fps
            b.location = p_rel + v0 * t + 0.5 * g * t * t
            if spin:
                b.rotation_euler.x = -t * 2 * math.pi * 30  # ~1800 rpm backspin
        b.keyframe_insert("location", frame=f)
        b.keyframe_insert("rotation_euler", frame=f)
    for fc in (b.animation_data.action.fcurves if hasattr(b.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    arm.hide_viewport = True
    return b, {"release_point": tuple(round(c, 3) for c in p_rel), "flight_s": round(flight, 3),
               "speed_m_s": speed, "target": tuple(round(c, 2) for c in tgt)}


def field(mound_at=Vector((0, 0, 0))):
    """Mound, rubber, home plate, dirt and grass."""
    grass = k.material("#4f7a3a", roughness=0.9, name="grass")
    dirt = k.material("#a8754a", roughness=0.95, name="dirt")
    white = k.material("#f2f2ee", roughness=0.6, name="white")
    k.plane(200, mat=grass, name="grass")
    m = k.cylinder(2.74, 0.25, loc=(mound_at.x, mound_at.y + 0.3, -0.115), mat=dirt, segments=64, name="mound")  # top flush with the feet
    m.scale = (1, 1, 1)
    k.cube(1.0, loc=(mound_at.x, mound_at.y, 0.13), scale=(0.61, 0.15, 0.02), mat=white, name="rubber")
    k.cylinder(4.0, 0.02, loc=(mound_at.x, mound_at.y + RUBBER_TO_PLATE, 0.0), mat=dirt, segments=48, name="home_dirt")
    k.mesh([(0, 0.43, 0), (0.215, 0.215, 0), (0.215, 0, 0), (-0.215, 0, 0), (-0.215, 0.215, 0)], [(0, 1, 2, 3, 4)],
           loc=(mound_at.x, mound_at.y + RUBBER_TO_PLATE + 0.3, 0.025), rot=(0, 0, 180), mat=white, name="plate")
