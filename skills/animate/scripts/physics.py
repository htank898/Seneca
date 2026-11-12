"""physics: cheap physical plausibility for retargeted motion. Runs inside Blender (mathutils).

    com(pose, L)                         whole-body centre of mass (Winter's segment table)
    balance_shift(poses, offs, contacts, L, fps)
                                         per-frame hip XY shift that keeps the centre of mass over
                                         the support polygon while the body is (nearly) still

Static balance only applies to quasi-static moments (standing, aiming, drawing a bow, settling
after a stop). In a run or a walk the centre of mass is legitimately ahead of or between the
feet (dynamic balance), so frames whose hips move faster than V_STATIC are left alone, with a
ramp in between. Used by rig.retarget(physics=True); ground penetration is retarget's
floor_guard.
"""
import math

from mathutils import Vector

# Winter, "Biomechanics and Motor Control of Human Movement" (4th ed.), table 4.1:
# bone -> (mass fraction of the body, centre of mass as a fraction from the bone's head)
SEGMENTS = {
    "head": (0.081, 0.40), "chest": (0.216, 0.50), "spine": (0.139, 0.50), "hips": (0.142, 0.40),
    "upper_arm.L": (0.028, 0.436), "upper_arm.R": (0.028, 0.436),
    "forearm.L": (0.016, 0.430), "forearm.R": (0.016, 0.430),
    "hand.L": (0.006, 0.506), "hand.R": (0.006, 0.506),
    "thigh.L": (0.100, 0.433), "thigh.R": (0.100, 0.433),
    "shin.L": (0.0465, 0.433), "shin.R": (0.0465, 0.433),
    "foot.L": (0.0145, 0.50), "foot.R": (0.0145, 0.50),
}
V_STATIC, V_DYNAMIC = 0.35, 0.7      # m/s: full correction below, none above
MARGIN, MAX_SHIFT = 0.02, 0.06       # metres
FOOT_HALF_WIDTH, HEEL_BACK = 0.045, 0.07


def com(pose, L, off=Vector((0, 0, 0))):
    tot, acc = 0.0, Vector((0, 0, 0))
    for b, (m, f) in SEGMENTS.items():
        if b not in pose:
            continue
        M = pose[b]
        p = M.to_translation() + M.col[1].to_3d().normalized() * (L[b] * f)
        acc += p * m
        tot += m
    return acc / tot + off


def _hull(pts):
    """Convex hull (Andrew's monotone chain) of 2D Vectors, counter-clockwise."""
    pts = sorted(set((round(p.x, 5), round(p.y, 5)) for p in pts))
    if len(pts) < 3:
        return [Vector(p) for p in pts]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [Vector(p) for p in lo[:-1] + hi[:-1]]


def _outside(p, hull):
    """(distance outside the polygon, nearest point on it); distance <= 0 means inside."""
    if len(hull) < 3:
        if not hull:
            return 0.0, p
        if len(hull) == 1:
            return (p - hull[0]).length, hull[0]
    best, near, inside = None, p, True
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        e = b - a
        if n >= 3 and e.x * (p.y - a.y) - e.y * (p.x - a.x) < 0:
            inside = False
        t = max(0.0, min(1.0, (p - a).dot(e) / max(e.length_squared, 1e-12)))
        c = a + e * t
        d = (p - c).length
        if best is None or d < best:
            best, near = d, c
    return (-best if inside else best), near


def support(pose, L, off, sides):
    """Support polygon (2D) of the planted feet: heel, both sides of the ankle and of the toe."""
    pts = []
    for s in sides:
        sh, ft = pose[f"shin.{s}"], pose[f"foot.{s}"]
        A = sh.to_translation() + sh.col[1].to_3d().normalized() * L[f"shin.{s}"] + off
        T = ft.to_translation() + ft.col[1].to_3d().normalized() * L[f"foot.{s}"] + off
        f = (T - A).xy
        f = f.normalized() if f.length > 1e-6 else Vector((0, -1))
        side = Vector((-f.y, f.x)) * FOOT_HALF_WIDTH
        heel = A.xy - f * HEEL_BACK
        pts += [heel + side, heel - side, A.xy + side, A.xy - side, T.xy + side, T.xy - side]
    return _hull(pts)


def _smooth(vals, sigma):
    r = int(3 * sigma + 0.5)
    k = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-r, r + 1)]
    s = sum(k)
    n = len(vals)
    return [sum(k[j] / s * vals[min(n - 1, max(0, i + j - r))] for j in range(len(k))) for i in range(n)]


def balance_shift(poses, offs, contacts, L, fps):
    """Per-frame XY Vector to add to the hips (None when nothing needs moving)."""
    n = len(poses)
    if n < 3:
        return None
    sx, sy = [0.0] * n, [0.0] * n
    any_ = False
    for i in range(n):
        j = min(n - 1, i + 1)
        k = max(0, i - 1)
        v = (offs[j] - offs[k]).xy.length * fps / max(1, j - k)
        w = 1.0 if v <= V_STATIC else max(0.0, (V_DYNAMIC - v) / (V_DYNAMIC - V_STATIC))
        if w <= 0:
            continue
        sides = [s for s in ("L", "R") if contacts[s][i]]
        if not sides:
            continue
        hull = support(poses[i], L, offs[i], sides)
        c = com(poses[i], L, offs[i]).xy
        d, near = _outside(c, hull)
        if d <= MARGIN:
            continue
        # move the hips (and so the centre of mass) back toward the support polygon
        dirn = (near - c).normalized()
        amt = min(MAX_SHIFT, d - MARGIN) * w
        sx[i], sy[i] = dirn.x * amt, dirn.y * amt
        any_ = True
    if not any_:
        return None
    sx, sy = _smooth(sx, 3.0), _smooth(sy, 3.0)
    return [Vector((sx[i], sy[i])) for i in range(n)]
