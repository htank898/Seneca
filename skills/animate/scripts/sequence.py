"""sequence: chain motion clips (mo dicts) into one continuous performance. Runs inside Blender.

    import rig, gait, sequence
    run, _ = gait.walk("cmu:09_01", seconds=2.5, height=1.6)        # looped run cycle
    stop = rig.load_bvh(gait.fetch_cmu("104_56"), start=0.1, height=1.6)
    shoot = rig.load_bvh(gait.fetch_cmu("79_86"), start=0.1, height=1.6)
    mo = sequence.chain([run, stop, shoot], blend=[0.35, 0.6], trim_s=[(0, 0), (0.25, 0), (0, 0)])
    rig.retarget(arm, mo, locomotion="root")

Each clip is turned about Z so its first heading matches where the previous clip ended, and moved
so its root starts where the previous root stopped (ground height kept). The seam is a crossfade:
the incoming clip's first `blend` seconds are mixed with the outgoing clip's final pose (smoothstep
weights) on the hip-relative landmarks and on the root, so nothing pops.
"""
import math

from mathutils import Matrix, Quaternion, Vector

L_HIP, R_HIP = 23, 24
# Landmark tree for blending in bone space: (parent, child). Parent None = the hip centre.
# Children are rebuilt from their parent along a slerped direction, so no bone shortens mid-blend
# the way lerping positions does (a lerped elbow cuts the corner and the arm goes through the body).
TREE = [(None, 23), (None, 24), ("SH", 11), ("SH", 12), ("SH", 7), ("SH", 8), ("SH", 0),
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 9), (0, 10),
        (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
        (23, 25), (25, 27), (27, 29), (27, 31), (24, 26), (26, 28), (28, 30), (28, 32)]


def heading(P):
    """Facing direction (unit XY) from one frame's hip-relative landmarks: left hip is +X when
    the body faces -Y, so forward = (side.y, -side.x)."""
    side = (P[L_HIP] - P[R_HIP]).xy
    f = Vector((side.y, -side.x))
    return f.normalized() if f.length > 1e-6 else Vector((0, -1))


def _avg_heading(world, idx):
    acc = Vector((0, 0))
    for i in idx:
        acc += heading(world[i])
    return acc.normalized() if acc.length > 1e-6 else Vector((0, -1))


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _slerp_dir(a, b, t):
    if a.length < 1e-9 or b.length < 1e-9:
        return a.lerp(b, t)
    q = a.normalized().rotation_difference(b.normalized())
    return Quaternion().slerp(q, t) @ a.normalized()


def blend_pose(P, Q, t):
    """Blend two hip-relative landmark frames in bone space (directions slerped, lengths lerped)."""
    out = [None] * len(P)
    hc = ((P[L_HIP] + P[R_HIP]) / 2).lerp((Q[L_HIP] + Q[R_HIP]) / 2, t)
    shp, shq = (P[11] + P[12]) / 2, (Q[11] + Q[12]) / 2
    ref = {None: (hc, (P[L_HIP] + P[R_HIP]) / 2, (Q[L_HIP] + Q[R_HIP]) / 2)}
    # shoulder centre hangs off the hip centre
    sh = hc + _slerp_dir(shp - ref[None][1], shq - ref[None][2], t) * (
        (1 - t) * (shp - ref[None][1]).length + t * (shq - ref[None][2]).length)
    ref["SH"] = (sh, shp, shq)
    for par, c in TREE:
        if par in ref:
            base, pp, qq = ref[par]
        else:
            base, pp, qq = out[par], P[par], Q[par]
        u, v = P[c] - pp, Q[c] - qq
        ln = (1 - t) * u.length + t * v.length
        out[c] = base + _slerp_dir(u, v, t).normalized() * ln if ln > 1e-9 else base.copy()
    for i in range(len(out)):
        if out[i] is None:
            out[i] = P[i].lerp(Q[i], t)
    return out


def trim(mo, start=0.0, end=0.0):
    """Drop `start` seconds from the head and `end` seconds from the tail."""
    fps = mo["fps"]
    a = int(round(start * fps))
    b = len(mo["world"]) - int(round(end * fps))
    out = dict(mo)
    out["world"] = mo["world"][a:b]
    out["root"] = mo["root"][a:b]
    out["valid"] = [True] * (b - a)
    out["frames"] = b - a
    return out


FEET = (27, 28, 29, 30, 31, 32)


def ground(mo):
    """Put this clip's floor at z=0. Captures from different sessions (CMU subjects) sit on
    different floor heights, and retarget() grounds a whole chain with one floor, so an
    ungrounded clip would sink into the ground or float. The floor is the 5th percentile of the
    lowest foot point per frame (robust to the odd tracking spike)."""
    lows = sorted(r.z + min(P[j].z for j in FEET) for P, r in zip(mo["world"], mo["root"]))
    floor = lows[max(0, int(len(lows) * 0.05))]
    out = dict(mo)
    out["root"] = [Vector((r.x, r.y, r.z - floor)) for r in mo["root"]]
    return out


def chain(mos, blend=0.4, trim_s=None):
    """Join clips end to end. blend: seconds (one value or one per seam). trim_s: optional
    [(start_s, end_s), ...] per clip. Returns one mo dict (fps of the first clip) plus
    mo["segments"] = [(first_frame, last_frame, index), ...] (1-based) for each clip."""
    if trim_s:
        mos = [trim(m, *t) for m, t in zip(mos, trim_s)]
    mos = [ground(m) for m in mos]
    fps = mos[0]["fps"]
    blends = blend if isinstance(blend, (list, tuple)) else [blend] * (len(mos) - 1)
    world = [list(fr) for fr in mos[0]["world"]]
    root = [r.copy() for r in mos[0]["root"]]
    segments = [(1, len(world), 0)]
    for k, mo in enumerate(mos[1:], start=1):
        W, R = mo["world"], mo["root"]
        nb = max(1, int(round(blends[k - 1] * fps)))
        # rotate the incoming clip so its opening heading matches the outgoing clip's closing one
        h_out = _avg_heading(world, range(max(0, len(world) - 5), len(world)))
        h_in = _avg_heading(W, range(0, min(5, len(W))))
        ang = math.atan2(h_out.y, h_out.x) - math.atan2(h_in.y, h_in.x)
        Rz = Matrix.Rotation(ang, 3, "Z")
        r0 = R[0]
        last_root = root[-1]
        last_pose = world[-1]
        W2 = [[Rz @ p for p in fr] for fr in W]
        R2 = []
        for r in R:
            q = Rz @ (r - r0)
            R2.append(Vector((last_root.x + q.x, last_root.y + q.y, r.z)))
        # crossfade the opening frames from the held outgoing pose (in bone space), and blend the
        # root's VELOCITY from the outgoing clip's into the incoming one's, so the hips neither
        # jerk nor stall at the seam
        v_out = (root[-1] - root[-2]).xy if len(root) > 1 else Vector((0, 0))
        R_orig = [r.copy() for r in R2]
        pos = last_root.xy.copy()
        nbe = min(nb, len(W2))
        for i in range(nbe):
            t = _smooth((i + 1) / (nb + 1))
            W2[i] = blend_pose(last_pose, W2[i], t)
            j = max(i, 1)
            v_in = (R_orig[j] - R_orig[j - 1]).xy if len(R_orig) > 1 else Vector((0, 0))
            pos = pos + v_out.lerp(v_in, t)
            R2[i] = Vector((pos.x, pos.y, last_root.z + (R2[i].z - last_root.z) * t))
        if nbe:
            shift = R2[nbe - 1].xy - R_orig[nbe - 1].xy
            for i in range(nbe, len(R2)):
                R2[i] = Vector((R_orig[i].x + shift.x, R_orig[i].y + shift.y, R_orig[i].z))
        segments.append((len(world) + 1, len(world) + len(W2), k))
        world += W2
        root += R2
    out = dict(mos[0])
    n = len(world)
    out.update(world=world, root=root, frames=n, valid=[True] * n, fps=fps, segments=segments)
    out.pop("cycle", None)
    return out
