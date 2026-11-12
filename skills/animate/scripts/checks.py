"""checks: measure an animation instead of eyeballing it. Runs inside Blender.

    import checks
    r = checks.report(body, arm, mo=mo, props=[bow])   # prints "[checks] {...}" and returns the dict

What it measures
    penetration   skinned mesh vs itself, region by region (each arm vs the torso, leg vs leg, hands
                  vs legs) and props vs the body. A vertex is "inside" when its nearest point on the
                  other region's surface faces away from it (signed distance through the face
                  normal). Generated meshes are open shells where that test is noisy, so it is
                  relative to the REST pose: only vertices that are clear at rest and end up more
                  than `thresh` inside count, and a frame counts when at least `min_verts` do.
                  Joint blend zones are skipped (only vertices >= 0.8 weighted to one region).
    floor         lowest mesh point per frame; sole height while a foot is planted (contacts)
    jitter        knee/elbow angular acceleration (deg/frame^2, 95th pct) on the rig, and on the
                  source landmarks when mo is given: the rig should not be jerkier than the data
"""
import json
import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REGIONS = {
    "torso": ("hips", "spine", "chest"),
    "arm.L": ("upper_arm.L", "forearm.L", "hand.L"),
    "arm.R": ("upper_arm.R", "forearm.R", "hand.R"),
    "leg.L": ("thigh.L", "shin.L", "foot.L"),
    "leg.R": ("thigh.R", "shin.R", "foot.R"),
    "hand.L": ("hand.L", "forearm.L"),
    "hand.R": ("hand.R", "forearm.R"),
    "head": ("neck", "head"),
}
PAIRS = [("arm.L", "torso"), ("arm.R", "torso"), ("leg.L", "leg.R"), ("leg.R", "leg.L"),
         ("hand.L", "leg.L"), ("hand.R", "leg.R"), ("hand.L", "leg.R"), ("hand.R", "leg.L"),
         ("arm.L", "head"), ("arm.R", "head")]


def log(*a):
    print("[checks]", *a, flush=True)


# body-part radii (fraction of height), the same capsules character-3d skins with
CAPSULE_R = {"hips": 0.085, "spine": 0.085, "chest": 0.09, "neck": 0.035, "head": 0.065,
             "upper_arm": 0.032, "forearm": 0.028, "hand": 0.025,
             "thigh": 0.05, "shin": 0.038, "foot": 0.035}


def _regions_geo(body, arm, margin=0.02):
    """Region per vertex from GEOMETRY at rest, independent of the skin weights (so two skinning
    methods are graded on the same regions): the body-part capsule (bone segment + radius) the
    vertex is nearest to. Vertices within `margin` of a second region are joint zones and skipped."""
    bones = [b for b in arm.data.bones if b.name.split(".")[0] in CAPSULE_R]
    M = arm.matrix_world
    A_ = np.array([tuple(M @ b.head_local) for b in bones])
    B_ = np.array([tuple(M @ b.tail_local) for b in bones])
    H = float(max(A_[:, 2].max(), B_[:, 2].max()) - min(A_[:, 2].min(), B_[:, 2].min(), 0.0))
    R_ = np.array([CAPSULE_R[b.name.split(".")[0]] * H for b in bones])
    n = len(body.data.vertices)
    co = np.empty(n * 3)
    body.data.vertices.foreach_get("co", co)
    V = co.reshape(-1, 3) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    AB = B_ - A_
    D = np.empty((n, len(bones)))
    for j in range(len(bones)):
        t = np.clip(((V - A_[j]) @ AB[j]) / max(float(AB[j] @ AB[j]), 1e-12), 0, 1)
        D[:, j] = np.linalg.norm(V - (A_[j] + t[:, None] * AB[j]), axis=1) - R_[j]
    reg_of_bone = {}
    for j, b in enumerate(bones):
        reg_of_bone[j] = [r for r, bs in REGIONS.items() if b.name in bs]
    order = np.argsort(D, axis=1)
    best = order[:, 0]
    out = {r: [] for r in REGIONS}
    for r in REGIONS:
        js = [j for j in range(len(bones)) if r in reg_of_bone[j]]
        if not js:
            out[r] = np.array([], dtype=int)
            continue
        inr = np.isin(best, js)
        # nearest bone OUTSIDE this region must be clearly farther
        Dm = D.copy()
        Dm[:, js] = np.inf
        clear = Dm.min(1) - D[np.arange(n), best] > margin
        out[r] = np.flatnonzero(inr & clear)
    return out


def _regions(body, pure=0.8):
    """Vertex index arrays per region: the vertex's weight to the region's bones >= pure."""
    names = {g.index: g.name for g in body.vertex_groups}
    n = len(body.data.vertices)
    W = {r: np.zeros(n) for r in REGIONS}
    tot = np.zeros(n)
    for v in body.data.vertices:
        for g in v.groups:
            bn = names.get(g.group)
            tot[v.index] += g.weight
            for r, bones in REGIONS.items():
                if bn in bones:
                    W[r][v.index] += g.weight
    tot = np.maximum(tot, 1e-9)
    return {r: np.flatnonzero(W[r] / tot >= pure) for r in REGIONS}


def _eval_coords(obj, dg):
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return co, polys


def _faces_of(polys, verts):
    vs = set(verts.tolist())
    return [p for p in polys if all(i in vs for i in p)]


def _inside(tree, pts, max_depth):
    """Signed-distance test: depth (m) for each point found inside the tree's surface, else 0."""
    out = np.zeros(len(pts))
    for i, p in enumerate(pts):
        hit = tree.find_nearest(Vector(p), max_depth)
        if hit[0] is None:
            continue
        loc, nrm, _, dist = hit
        if (Vector(p) - loc).dot(nrm) < 0:
            out[i] = dist
    return out


def penetration(body, arm, frames=None, step=2, sub=3, max_depth=0.06, thresh=0.01, min_verts=15, props=()):
    """Per pair: % of frames with >= min_verts newly inside by > thresh, mean count of such
    vertices, worst depth (95th percentile of those vertices, cm) and the frame it happens.
    `sub` tests every sub-th vertex of the moving region (speed), `step` every step-th frame."""
    sc = bpy.context.scene
    f0, f1 = frames or (sc.frame_start, sc.frame_end)
    reg = _regions_geo(body, arm)
    # rest-pose baseline: anything already inside at rest is mesh design (or test noise), not motion
    arm.data.pose_position = "REST"
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    co, polys = _eval_coords(body, dg)
    arm.data.pose_position = "POSE"
    faces = {r: _faces_of(polys, v) for r, v in reg.items()}
    base = {}
    for a, b in PAIRS:
        if not len(reg[a]) or not faces[b]:
            continue
        t = BVHTree.FromPolygons(co.tolist(), faces[b], all_triangles=False, epsilon=0.0)
        ids = reg[a][::sub]
        base[(a, b)] = ids[_inside(t, co[ids], max_depth) <= 0.0]
    res = {f"{a}>{b}": {"frames": 0, "verts": 0, "worst_cm": 0.0, "at": None} for a, b in base}
    for p in props:
        res[f"{p.name}>body"] = {"frames": 0, "verts": 0, "worst_cm": 0.0, "at": None}

    def tally(r, d, f):
        deep = d[d > thresh]
        r["verts"] += len(deep)
        if len(deep) >= min_verts:
            r["frames"] += 1
            w = float(np.percentile(deep, 95))
            if w * 100 > r["worst_cm"]:
                r["worst_cm"], r["at"] = round(w * 100, 1), f
    tested = 0
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        co, _ = _eval_coords(body, dg)
        tested += 1
        trees = {}
        for (a, b), ids in base.items():
            if b not in trees:
                trees[b] = BVHTree.FromPolygons(co.tolist(), faces[b], all_triangles=False, epsilon=0.0)
            tally(res[f"{a}>{b}"], _inside(trees[b], co[ids], max_depth), f)
        if props:
            whole = BVHTree.FromPolygons(co.tolist(), polys, all_triangles=False, epsilon=0.0)
            for p in props:
                if p.hide_render:
                    continue
                pc, _ = _eval_coords(p, dg)
                if not len(pc):
                    continue
                tally(res[f"{p.name}>body"], _inside(whole, pc, max_depth), f)
    for r in res.values():
        r["pct"] = round(100 * r["frames"] / max(1, tested), 1)
        r["verts"] = round(r["verts"] / max(1, tested), 1)
    return res


def floor(body, arm, frames=None, step=1):
    """Lowest mesh point per frame (cm below 0 = through the floor) and the sole height on frames
    where retarget() marked a contact (should be ~0)."""
    sc = bpy.context.scene
    f0, f1 = frames or (sc.frame_start, sc.frame_end)
    reg = _regions_geo(body, arm, margin=0.0)
    feet = {s: reg[f"leg.{s}"] for s in ("L", "R")}
    contacts = json.loads(arm.get("contacts", "{}") or "{}")
    lows, sole_err = [], []
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f)
        co, _ = _eval_coords(body, bpy.context.evaluated_depsgraph_get())
        lows.append(float(co[:, 2].min()))
        i = f - sc.frame_start
        for s, ids in feet.items():
            c = contacts.get(s)
            if c and 0 <= i < len(c) and c[i]:
                sole_err.append(float(co[ids, 2].min()))
    lows = np.array(lows)
    out = {"min_z_cm": round(float(lows.min()) * 100, 1),
           "frames_below_1cm": int((lows < -0.01).sum())}
    if sole_err:
        e = np.array(sole_err)
        out["sole_mm_median"] = round(float(np.median(e)) * 1000, 1)        # + floating, - sunk
        out["sole_abs_mm_median"] = round(float(np.median(np.abs(e))) * 1000, 1)
        out["sole_abs_mm_p95"] = round(float(np.percentile(np.abs(e), 95)) * 1000, 1)
    return out


def _angles_rig(arm, f0, f1):
    sc = bpy.context.scene
    pairs = {"knee.L": ("thigh.L", "shin.L"), "knee.R": ("thigh.R", "shin.R"),
             "elbow.L": ("upper_arm.L", "forearm.L"), "elbow.R": ("upper_arm.R", "forearm.R")}
    out = {k: [] for k in pairs}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for k, (a, b) in pairs.items():
            va = arm.pose.bones[a].vector.normalized()
            vb = arm.pose.bones[b].vector.normalized()
            out[k].append(math.degrees(va.angle(vb, 0.0)))
    return out


def _angles_mo(mo):
    W = mo["world"]
    idx = {"knee.L": (23, 25, 27), "knee.R": (24, 26, 28), "elbow.L": (11, 13, 15), "elbow.R": (12, 14, 16)}
    out = {}
    for k, (a, b, c) in idx.items():
        v = []
        for P in W:
            u, w = Vector(P[b]) - Vector(P[a]), Vector(P[c]) - Vector(P[b])
            v.append(math.degrees(u.angle(w, 0.0)) if u.length > 1e-6 and w.length > 1e-6 else 0.0)
        out[k] = v
    return out


def _acc95(series):
    x = np.asarray(series, float)
    if len(x) < 5:
        return 0.0
    return round(float(np.percentile(np.abs(np.diff(x, 2)), 95)), 2)


def jitter(arm, mo=None, frames=None):
    sc = bpy.context.scene
    f0, f1 = frames or (sc.frame_start, sc.frame_end)
    rig = {k: _acc95(v) for k, v in _angles_rig(arm, f0, f1).items()}
    out = {"rig": rig}
    if mo is not None:
        out["src"] = {k: _acc95(v) for k, v in _angles_mo(mo).items()}
    return out


def report(body, arm, mo=None, props=(), frames=None, step=2, label=""):
    arm.hide_viewport = False
    r = {"penetration": penetration(body, arm, frames, step=step, props=props),
         "floor": floor(body, arm, frames),
         "jitter": jitter(arm, mo, frames)}
    pen = r["penetration"]
    r["summary"] = {
        "pen_frames_pct_max": max((v["pct"] for v in pen.values()), default=0.0),
        "pen_worst_cm": max((v["worst_cm"] for v in pen.values()), default=0.0),
    }
    print(f"[checks]{(' ' + label) if label else ''} {json.dumps(r)}", flush=True)
    return r
