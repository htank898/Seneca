"""clips: ready-made animation clips (Quaternius CC0, your own Mixamo downloads, any glTF/FBX with
actions), chained into one performance. Runs inside Blender.

Two ways to use a clip:

  1. On any Seneca body or character (the usual route): a clip becomes a motion.json-style mo dict,
     so everything in rig.py applies: rig.armature, bodies.body, rig.retarget(quality=True), checks.

        import bkit as k, rig, bodies, clips
        mo  = clips.sequence(["Walk_Loop:2.6", "Idle_Talking_Loop", "Punch_Jab", "Idle_Loop"])
        arm = rig.armature(mo)
        bodies.body(arm)
        rig.retarget(arm, mo, locomotion="root", quality=True)

  2. On the pack's own mannequin, no retarget (fastest; the clip plays exactly as authored):

        arm, mesh = clips.native(["Walk_Loop:2.6", "Idle_Talking_Loop", "Dance_Loop:3"])

A shot item is a clip name, "Name:seconds", "Name*loops", or a dict
{"clip": name, "seconds"|"loops": ..., "speed": 1.0, "travel": "auto"|False|metres_per_second}.

Setup: node scripts/clips-fetch.mjs quaternius   (once, ~25 MB). Mixamo FBX files you downloaded
yourself: a folder in $SENECA_CLIPS (colon-separated), or catalog(extra=[folder]).

Travel: in-place locomotion loops (Walk_Loop, Jog_Fwd_Loop, Mixamo "In Place" clips) are detected
from their planted feet sliding backwards, and the root is carried forward at exactly that speed,
so the feet stay planted. Root-motion clips (*_RM, Mixamo without "In Place") keep their own path.
"""
import json
import os
import re
import statistics
from pathlib import Path

import bpy
from mathutils import Vector

import rig

CACHE = Path.home() / ".cache" / "seneca-adapt" / "clips"
# The Quaternius zips hold the same clips in several engine flavours; use one file per pack.
QUATERNIUS = [
    "quaternius/ual1/Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb",
    "quaternius/ual2/Universal Animation Library 2 [Standard]/Unreal-Godot/UAL2_Standard.glb",
]
# auto travel only for clips that are about getting somewhere (a swimmer or a dancer has no
# planted feet to measure, and a false reading would slide them across the floor)
LOCOMOTION = re.compile(r"walk|jog|run|sprint|crawl|crouch_?fwd|fwd|forward|strafe|carry|push|march|limp", re.I)
SKIP = re.compile(r"T-?Pose|A_TPose|Pistol_Aim_(Down|Up|Neutral)$", re.I)
_LOADED = {}  # path -> {"arm": armature, "fps": import fps, "objs": [...]} for this Blender session


# ---------------------------------------------------------------- catalog
def _files(extra=None):
    out = [CACHE / p for p in QUATERNIUS if (CACHE / p).exists()]
    folders = [d for d in os.environ.get("SENECA_CLIPS", "").split(":") if d] + list(extra or [])
    for d in folders:
        out += sorted(p for p in Path(d).expanduser().rglob("*") if p.suffix.lower() in (".glb", ".gltf", ".fbx"))
    if not out:
        raise FileNotFoundError("no clips installed: run  node scripts/clips-fetch.mjs quaternius  "
                                "(and/or put Mixamo FBX files in a folder listed in $SENECA_CLIPS)")
    return out


def _import(path):
    """Import a clip file once per Blender session; hide it. Returns the cached entry."""
    path = str(path)
    if path in _LOADED:
        return _LOADED[path]
    sc = bpy.context.scene
    before, acts_before = set(bpy.data.objects), set(bpy.data.actions)
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in objs if o.type == "ARMATURE")
    acts = [a for a in bpy.data.actions if a not in acts_before]
    if arm.rotation_mode != "XYZ":
        arm.rotation_mode = "XYZ"
    for o in objs:
        o.hide_render = True
        if o is not arm:   # a viewport-disabled armature is not evaluated, so its clips won't play
            o.hide_viewport = True
    if arm.animation_data:
        arm.animation_data.action = None
    entry = {"arm": arm, "objs": objs, "actions": acts, "fps": sc.render.fps / sc.render.fps_base,
             "path": path}
    _LOADED[path] = entry
    return entry


def catalog(extra=None, refresh=False):
    """{clip name: {"file", "seconds", "loop", "root_motion"}} for every installed clip.
    Cached in ~/.cache/seneca-adapt/clips/catalog.json (keyed by file path and mtime)."""
    idx_path = CACHE / "catalog.json"
    idx = {} if refresh or not idx_path.exists() else json.loads(idx_path.read_text())
    out, dirty = {}, False
    for f in _files(extra):
        key = f"{f}|{int(f.stat().st_mtime)}"
        if key not in idx:
            e = _import(f)
            single = len(e["actions"]) == 1  # Mixamo: one clip per file, action named "mixamo.com"
            idx[key] = {(f.stem if single else a.name): {
                "seconds": round((a.frame_range[1] - a.frame_range[0]) / e["fps"], 3),
                "action": a.name} for a in e["actions"]}
            dirty = True
        for name, meta in idx[key].items():
            if SKIP.search(name):
                continue
            out[name] = {"file": str(f), "action": meta["action"], "seconds": meta["seconds"],
                         "loop": bool(re.search(r"loop|in place|idle", name, re.I)),
                         "root_motion": bool(re.search(r"_RM$", name))}
    if dirty:
        CACHE.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(json.dumps(idx, indent=1))
    return out


def find(*words, extra=None):
    """Clip names containing every word (case-insensitive), e.g. find("walk"), find("sit", "idle")."""
    cat = catalog(extra)
    return sorted(n for n in cat if all(w.lower() in n.lower() for w in words))


# ---------------------------------------------------------------- one clip -> mo
def _parse(item):
    if isinstance(item, dict):
        return dict(item)
    m = re.match(r"^(.*?)(?::([\d.]+)|\*(\d+))?$", item)
    d = {"clip": m.group(1)}
    if m.group(2):
        d["seconds"] = float(m.group(2))
    if m.group(3):
        d["loops"] = int(m.group(3))
    return d


def _use(arm, act):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    if act is not None and len(act.slots):
        ad.action_slot = act.slots[0]


def _planted_velocity(mo):
    """Horizontal velocity (m/s) of the feet while they are on the ground, in world space: the
    ankles' frame-to-frame velocity averaged with weights that fall off as an ankle rises above its
    lowest point (1 cm scale), which is the travel speed that minimises planted-foot sliding. Runs
    touch down for only 2-3 frames at 24 fps, so a hard contact threshold or a median is too coarse;
    the toe tip is a bad probe (it pivots in place while the heel lifts)."""
    import math
    fps = mo["fps"]
    num, den = Vector((0, 0, 0)), 0.0
    for ank in (27, 28):
        A = [mo["root"][i] + mo["world"][i][ank] for i in range(mo["frames"])]
        az = min(p.z for p in A)
        for i in range(len(A) - 1):
            dz = (A[i].z + A[i + 1].z) / 2 - az
            if dz < 0.03:
                w = math.exp(-dz / 0.01)
                v = (A[i + 1] - A[i]) * fps
                num += Vector((v.x, v.y, 0)) * w
                den += w
    return num / den if den > 2.0 else Vector((0, 0, 0))


def foot_slide(mo):
    """Median ground speed (m/s) of planted ankles after travel: ~0 when the root matches the feet."""
    fps, out = mo["fps"], []
    for ank in (27, 28):
        A = [mo["root"][i] + mo["world"][i][ank] for i in range(mo["frames"])]
        az = min(p.z for p in A)
        out += [((A[i + 1] - A[i]) * fps).to_2d().length for i in range(len(A) - 1)
                if A[i].z < az + 0.01 and A[i + 1].z < az + 0.01]
    return statistics.median(out) if out else 0.0


FOOT = 0.12  # ankle-to-toe-tip / standing height (CMU performers measure 0.12)


def _fix_head(P, neck):
    """rig.targets aims neck and head from the shoulders' midpoint to the ears. Game rigs often put
    the shoulder joints well behind the neck (Quaternius: 6.5 cm), which tilts the head ~30 deg
    forward on the retargeted body. Shift the ears and nose so that line runs from the real neck
    base instead."""
    if neck is None:
        return P
    P = list(P)
    d = (P[11] + P[12]) / 2 - neck
    for j in (0, 7, 8):
        P[j] = P[j] + d
    return P


def _fix_feet(P, height):
    """Game rigs' toe bones often run past the real toe tip and below the sole (Quaternius: an
    0.34 m foot on a 1.75 m body), which gives a retargeted body clown feet. Keep the toe's
    direction, set a human length, and rebuild the heel the way rig.sample_armature does."""
    P = list(P)
    for ank, toe, heel in ((27, 31, 29), (28, 32, 30)):
        v = P[toe] - P[ank]
        if v.length < 1e-6:
            continue
        L = FOOT * height
        P[toe] = P[ank] + v.normalized() * L
        P[heel] = P[ank] - v.normalized() * L * 0.25 + Vector((0, 0, -0.02 * L))
    return P


def clip(name, seconds=None, loops=None, speed=1.0, travel="auto", height=1.75, fps=None, extra=None):
    """One clip as a mo dict at the scene's fps. seconds/loops: how long to play it (a loop clip
    repeats seamlessly; a one-shot holds nothing and just plays once). speed: playback rate.
    travel: "auto" carries in-place locomotion forward at its own foot speed; False keeps it in
    place; a number sets metres per second along the detected direction."""
    cat = catalog(extra)
    if name not in cat:
        near = find(*re.split(r"[_\s]+", name.lower())[:1], extra=extra)
        raise KeyError(f"no clip {name!r}. Similar: {near[:12]}")
    meta = cat[name]
    e = _import(meta["file"])
    src, act = e["arm"], bpy.data.actions[meta["action"]]
    _use(src, act)
    nla_was = src.animation_data.use_nla
    src.animation_data.use_nla = False  # sample the clip alone, not native()'s NLA stack
    sc = bpy.context.scene
    fps = fps or (sc.render.fps / sc.render.fps_base)
    T = meta["seconds"] / speed  # one pass, output seconds
    # one full pass, including the closing frame, so a loop's per-cycle drift can be measured
    base = rig.sample_armature(src, src_fps=e["fps"], fps=fps, height=height, speed=speed, scale="rest")
    _use(src, None)
    src.animation_data.use_nla = nla_was
    want = seconds if seconds is not None else (T * loops if loops else T)
    n_out = max(2, int(round(want * fps)) + 1)
    W = [_fix_head(fr, nk) for fr, nk in zip(base["world"], base["neck_base"])]
    R = base["root"]
    if meta["loop"] and len(W) > 2:
        W, R = W[:-1], R[:-1]          # drop the closing frame (== the first) before tiling
        drift = base["root"][-1] - base["root"][0]
        drift.z = 0
        cyc = len(W)
        world = [W[i % cyc] for i in range(n_out)]
        root = [R[i % cyc] + drift * (i // cyc) for i in range(n_out)]
    else:
        n_out = min(n_out, len(W))     # a one-shot plays once; ask for more and it just ends
        world, root = W[:n_out], R[:n_out]
    world = [_fix_feet(fr, height) for fr in world]
    neck_len = statistics.median((((fr[7] + fr[8]) / 2) - ((fr[11] + fr[12]) / 2)).length for fr in world)
    lengths = dict(base["lengths"], foot=FOOT * height, heel=0.25 * FOOT * height, neck=neck_len)
    mo = dict(base, frames=n_out, world=world, root=[r.copy() for r in root], lengths=lengths,
              valid=[True] * n_out, source=f"clip:{name}", clip=name)
    mo["travel"], mo["travel_dir"] = 0.0, (0.0, 0.0, 0.0)
    if travel and not meta["root_motion"] and (travel != "auto" or LOCOMOTION.search(name)):
        v = _planted_velocity(mo)
        if travel == "auto":
            travel = v.length if v.length > 0.25 else 0.0
        if travel and v.length > 1e-6:
            step = -v.normalized() * travel / fps
            mo["root"] = [r + step * i for i, r in enumerate(mo["root"])]
            mo["travel"] = round(travel, 3)
            mo["travel_dir"] = tuple(-v.normalized())
    mo["slide"] = round(foot_slide(mo), 3)
    return mo


# ---------------------------------------------------------------- many clips -> one mo
def sequence(items, blend=0.3, height=1.75, fps=None, extra=None):
    """Chain clips into one mo dict through sequence.chain: each clip is turned to the previous
    one's heading, its root continues from where the previous one stopped, and the seam is a
    bone-space crossfade of `blend` seconds (one value, or one per seam)."""
    import sequence as seq
    sc = bpy.context.scene
    fps = fps or (sc.render.fps / sc.render.fps_base)
    parts = []
    for it in items:
        d = _parse(it)
        parts.append(clip(d.pop("clip"), height=height, fps=fps, extra=extra, **d))
    mo = seq.chain(parts, blend=blend)
    mo["spans"] = [(parts[i]["clip"], a, b) for a, b, i in mo["segments"]]  # 1-based frames
    mo["source"] = "clips:" + ",".join(p["clip"] for p in parts)
    for k in ("clip", "travel", "travel_dir", "slide", "neck_base"):
        mo.pop(k, None)
    print("[seq] " + json.dumps({"clips": [p["clip"] for p in parts], "frames": mo["frames"],
                                 "seconds": round(mo["frames"] / fps, 2),
                                 "travel_m_s": {p["clip"]: p["travel"] for p in parts if p["travel"]}}),
          flush=True)
    for p in parts:
        if p["travel"] and p["slide"] > 0.3:
            print(f"[seq] warning: {p['clip']} planted feet still slide {p['slide']} m/s at "
                  f"travel {p['travel']} m/s. Runs played in place don't encode their flight "
                  "distance; set travel= by eye, or use a root-motion (_RM) clip.", flush=True)
    return mo


# ---------------------------------------------------------------- native: the pack's own mannequin
def native(items, blend=0.3, start=1, extra=None):
    """Play clips on the pack's own rigged mannequin with NLA cross-fades: no retarget, the motion
    is exactly as authored. All clips must come from one file (Quaternius UAL1 or UAL2). Sets the
    scene frame range. Returns (armature, mesh)."""
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    cat = catalog(extra)
    ds = [_parse(it) for it in items]
    files = {cat[d["clip"]]["file"] for d in ds}
    if len(files) != 1:
        raise ValueError(f"native() needs clips from one file; these come from {sorted(files)}. "
                         "Use sequence() + rig.retarget to mix packs.")
    e = _import(files.pop())
    arm = e["arm"]
    mesh = next((o for o in e["objs"] if o.type == "MESH" and len(o.data.vertices) > 1000), None)
    for o in (arm, mesh):
        if o:
            o.hide_render = o.hide_viewport = False
    for o in e["objs"]:  # helper geometry (Quaternius ships a tiny Icosphere)
        if o.type == "MESH" and o is not mesh:
            o.hide_render = o.hide_viewport = True
    measured = {}
    for d in ds:
        meta = cat[d["clip"]]
        if d.get("travel", "auto") == "auto" and not meta["root_motion"]:
            m = clip(d["clip"], loops=1, speed=d.get("speed", 1.0), fps=fps, extra=extra)
            measured[d["clip"]] = (m["travel"], Vector(m["travel_dir"]))
    _use(arm, None)
    ad = arm.animation_data
    ad.use_nla = True
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    B = max(1, int(round(blend * fps)))
    ratio = fps / e["fps"]
    cursor, keys, last = float(start), [], None
    for i, d in enumerate(ds):
        meta, act = cat[d["clip"]], bpy.data.actions[cat[d["clip"]]["action"]]
        L = act.frame_range[1] - act.frame_range[0]
        speed = d.get("speed", 1.0)
        reps = 1.0
        if meta["loop"]:
            want = d.get("seconds", L / e["fps"] / speed * d.get("loops", 1))
            reps = max(0.01, want * e["fps"] * speed / L)
        tr = ad.nla_tracks.new()
        tr.name = d["clip"]
        st = tr.strips.new(d["clip"], int(cursor), act)
        if len(act.slots):
            st.action_slot = act.slots[0]
        st.scale = ratio / speed
        st.repeat = reps
        st.extrapolation = "HOLD_FORWARD" if i == len(ds) - 1 else "NOTHING"
        st.blend_in = B if i else 0
        travel, direction = d.get("travel", "auto"), Vector((0, -1, 0))
        if travel and not meta["root_motion"]:
            if travel == "auto":
                travel, direction = measured.get(d["clip"], (0.0, direction))
            if travel:
                keys.append((st.frame_start, st.frame_end - B / 2, travel, d["clip"], direction))
        cursor = st.frame_end - B
        last = st
    sc.frame_start, sc.frame_end = int(start), int(last.frame_end)
    # carry in-place locomotion forward along its measured direction at its measured speed
    if keys:
        from bpy_extras import anim_utils
        pos = arm.location.copy()
        arm.keyframe_insert("location", frame=start)
        for f0, f1, v, _, fwd in keys:
            arm.location = pos
            arm.keyframe_insert("location", frame=f0)
            pos = pos + fwd * v * (f1 - f0) / fps
            arm.location = pos
            arm.keyframe_insert("location", frame=f1)
        for fc in anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot).fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    print("[seq] " + json.dumps({"native": [d["clip"] for d in ds], "frames": [int(start), int(last.frame_end)],
                                 "blend_frames": B, "travel_m_s": {k[3]: k[2] for k in keys}}), flush=True)
    return arm, mesh
