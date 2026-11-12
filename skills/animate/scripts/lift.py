"""lift: rebuild the 3D skeleton from the 2D keypoints, so the motion is what the camera saw.

MediaPipe's 2D keypoints are accurate; its 3D "world" landmarks guess depth and drift. This
module keeps every bone's on-screen direction exactly as tracked and recovers only the missing
depth from the bone's known length (Taylor 2000, "Reconstruction of articulated objects from
point correspondences in a single uncalibrated image"):

    on-screen length l (px) = s * sqrt(L^2 - dz^2)   ->   dz = +-sqrt(L^2 - (l/s)^2)

s (pixels per metre) is solved per frame from the bones that are least foreshortened, then
smoothed. The sign of dz (toward / away from the camera) is the one thing 2D can't tell, so it
comes from MediaPipe's 3D estimate, or from the previous frame when that estimate is ambiguous.

Pure numpy. Used by pose.py; the output keeps motion.json's format (Blender axes, metres,
hip-centred) so rig.py needs no changes.
"""
import numpy as np

HIP_C, SH_C, EAR_C = 33, 34, 35  # virtual centres appended after MediaPipe's 33

# Girdles are solved as rigid bars through their centre (left and right always on opposite sides
# in depth); everything else is a bone hanging off its parent. Tree order from the pelvis.
PAIRS = {HIP_C: (23, 24), SH_C: (11, 12), EAR_C: (7, 8)}
OPS = [
    ("pair", HIP_C), ("edge", HIP_C, SH_C), ("pair", SH_C), ("edge", SH_C, EAR_C), ("pair", EAR_C),
    ("edge", EAR_C, 0),
    ("edge", 23, 25), ("edge", 25, 27), ("edge", 27, 29), ("edge", 27, 31),
    ("edge", 24, 26), ("edge", 26, 28), ("edge", 28, 30), ("edge", 28, 32),
    ("edge", 11, 13), ("edge", 13, 15), ("edge", 15, 17), ("edge", 15, 19), ("edge", 15, 21),
    ("edge", 12, 14), ("edge", 14, 16), ("edge", 16, 18), ("edge", 16, 20), ("edge", 16, 22),
]
EDGES = [(o[1], o[2]) for o in OPS if o[0] == "edge"] + [(PAIRS[o[1]][1], PAIRS[o[1]][0]) for o in OPS if o[0] == "pair"]
# Bones long and rigid enough to measure scale from (at least one is usually side-on)
SCALE_EDGES = [(HIP_C, SH_C), (23, 25), (25, 27), (24, 26), (26, 28), (11, 13), (12, 14), (13, 15), (14, 16)]
MIRROR = {23: 24, 25: 26, 27: 28, 29: 30, 31: 32, 11: 12, 13: 14, 15: 16, 17: 18, 19: 20, 21: 22, 7: 8}
MIRROR.update({v: k for k, v in list(MIRROR.items())})


# Segment lengths as fractions of standing height H (Drillis & Contini 1966, as tabulated in
# Winter, "Biomechanics and Motor Control of Human Movement"), adjusted to where MediaPipe puts its
# keypoints (joint centres, not bony landmarks). Used instead of MediaPipe's 3D lengths, whose
# proportions are unreliable (e.g. upper arm reported at half the thigh; anatomically ~3/4).
ANTHRO = {
    (HIP_C, SH_C): 0.288, (SH_C, EAR_C): 0.100, (EAR_C, 0): 0.060,
    (23, 24): 0.110, (11, 12): 0.210, (7, 8): 0.085,
    (23, 25): 0.245, (25, 27): 0.246, (27, 29): 0.040, (27, 31): 0.120,
    (24, 26): 0.245, (26, 28): 0.246, (28, 30): 0.040, (28, 32): 0.120,
    (11, 13): 0.186, (13, 15): 0.146, (15, 17): 0.050, (15, 19): 0.055, (15, 21): 0.045,
    (12, 14): 0.186, (14, 16): 0.146, (16, 18): 0.050, (16, 20): 0.055, (16, 22): 0.045,
}


def _extend(a):
    """Append pelvis, shoulder and ear centres as points 33, 34, 35."""
    return np.concatenate([a, a[:, [23, 24]].mean(1, keepdims=True), a[:, [11, 12]].mean(1, keepdims=True),
                           a[:, [7, 8]].mean(1, keepdims=True)], 1)


def _smooth1d(x, sigma):
    if sigma <= 0:
        return x
    r = int(3 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, r, mode="edge"), k, mode="valid")


def bone_lengths(world_ext, valid, vis_ext=None, min_vis=0.5):
    """Median 3D length per edge, symmetric left/right. Measured only on frames where both ends
    are actually visible, and each left/right pair takes the better-seen side (a far-side limb
    hidden behind the body can be hallucinated at absurd lengths)."""
    n = world_ext.shape[0]
    L, seen = {}, {}
    for p, c in EDGES:
        lens = np.linalg.norm(world_ext[:, c] - world_ext[:, p], axis=1)
        if (p, c) in [(PAIRS[k][1], PAIRS[k][0]) for k in PAIRS]:
            p, c = c, p  # stored as (left, right) for girdles
        ok = np.asarray(valid, bool).copy()
        if vis_ext is not None:
            ok &= np.minimum(vis_ext[:, c], vis_ext[:, p]) >= min_vis
        seen[(p, c)] = int(ok.sum())
        pool = lens[ok] if ok.sum() >= 5 else lens[np.asarray(valid, bool)]
        L[(p, c)] = float(np.median(pool))
    for (p, c) in list(L):
        m = (MIRROR.get(p, p), MIRROR.get(c, c))
        if m in L and m != (p, c):
            best = (p, c) if seen[(p, c)] >= seen[m] else m
            L[(p, c)] = L[m] = L[best]
    return L


def lift(image, world, valid, width, height, sigma_scale=2.0, ambiguous=0.25, min_vis=0.5, occl_vis=0.15,
         height_m=1.75):
    """image: (n,33,3) normalized u,v,vis (smoothed, gaps filled). world: (n,33,3) MediaPipe in
    Blender axes (x right, y away, z up). Returns (world_lifted (n,33,3), scale (n,), stats)."""
    n = image.shape[0]
    px = image[..., :2] * np.array([width, height])          # pixels, v down
    px = _extend(px)
    wb = _extend(world)
    vis = _extend(image[..., 2:3])[..., 0]
    vis[:, HIP_C] = np.minimum(image[:, 23, 2], image[:, 24, 2])
    vis[:, SH_C] = np.minimum(image[:, 11, 2], image[:, 12, 2])
    vis[:, EAR_C] = np.maximum(image[:, 7, 2], image[:, 8, 2])
    # Bone lengths: anthropometric proportions of height_m, then lengthened per person where the
    # footage proves a bone is longer (a bone's on-screen length never exceeds its true length).
    L = {e: f * height_m for e, f in ANTHRO.items()}
    okv = np.asarray(valid, bool)
    for _ in range(2):
        # 1) scale: pixels per metre, from the least-foreshortened long bones
        ratios = np.stack([np.linalg.norm(px[:, c] - px[:, p], axis=1) / max(L[(p, c)], 1e-3)
                           for p, c in SCALE_EDGES], 1)
        s = _smooth1d(np.percentile(ratios, 90, axis=1), sigma_scale)
        for (p, c) in list(L):
            seen = okv & (np.minimum(vis[:, c], vis[:, p]) >= min_vis)
            if seen.sum() < 10:
                continue
            obs = np.percentile(np.linalg.norm(px[seen, c] - px[seen, p], axis=1) / s[seen], 95)
            L[(p, c)] = max(L[(p, c)], float(obs))
        for (p, c) in list(L):  # keep left/right symmetric
            m = (MIRROR.get(p, p), MIRROR.get(c, c))
            if m in L and m != (p, c):
                L[(p, c)] = L[m] = max(L[(p, c)], L[m])

    # 2) per-bone depth from the length constraint; sign from the 3D estimate / previous frame
    out = np.zeros((n, 36, 3))
    signs = {}
    clamped = occluded = 0

    def solve(i, p, c, Lb, key):
        """3D offset from point p to point c: on-screen direction kept, depth from length."""
        nonlocal clamped, occluded
        if vis[i, c] < occl_vis:
            v = wb[i, c] - wb[i, p]
            nv = np.linalg.norm(v)
            occluded += 1
            return v / nv * Lb if nv > 1e-6 else np.array([0.0, 0.0, -Lb])
        d2 = (px[i, c] - px[i, p]) / s[i]                       # metres on screen: (right, down)
        rem = Lb * Lb - float(d2 @ d2)
        if rem < 0:  # looks longer than it can be: keep direction, flat to the camera, true length
            clamped += 1
            d2 = d2 / max(np.sqrt(float(d2 @ d2)), 1e-9) * Lb
            rem = 0.0
        hint = wb[i, c, 1] - wb[i, p, 1]                         # MediaPipe: + = farther away
        if abs(hint) > ambiguous * Lb or key not in signs:
            signs[key] = 1.0 if hint >= 0 else -1.0
        return np.array([d2[0], signs[key] * np.sqrt(rem), -d2[1]])

    for i in range(n):
        for op in OPS:
            if op[0] == "edge":
                _, p, c = op
                out[i, c] = out[i, p] + solve(i, p, c, L[(p, c)], (p, c))
            else:  # girdle: right -> left bar centred on the parent point
                ctr = op[1]
                lft, rgt = PAIRS[ctr]
                full = solve(i, rgt, lft, L[(lft, rgt)], ("pair", ctr))
                out[i, lft] = out[i, ctr] + full / 2
                out[i, rgt] = out[i, ctr] - full / 2
    lifted = out[:, :33]
    stats = {"scale_px_per_m_median": round(float(np.median(s)), 1),
             "lengths_m": {f"{p}-{c}": round(v, 3) for (p, c), v in L.items()},
             "clamped_bone_frames": int(clamped), "occluded_bone_frames": int(occluded),
             "bone_frames": n * len(EDGES)}
    return lifted, s, stats


def reprojection_error(world, image, width, height, valid, joints=(11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)):
    """How well a 3D skeleton explains the 2D keypoints: per frame, best scale+offset orthographic
    fit of (x, -z) to the pixels, error in % of torso length. Lower is better."""
    j = list(joints)
    errs = []
    for i in np.where(valid)[0]:
        P = np.stack([world[i, j, 0], -world[i, j, 2]], 1)
        Q = image[i, j, :2] * np.array([width, height])
        Pc, Qc = P - P.mean(0), Q - Q.mean(0)
        k = float((Pc * Qc).sum() / max((Pc * Pc).sum(), 1e-9))
        r = np.linalg.norm(k * Pc - Qc, axis=1).mean()
        torso = np.linalg.norm(Q[[0, 1]].mean(0) - Q[[6, 7]].mean(0))
        errs.append(r / max(torso, 1e-6) * 100)
    return float(np.mean(errs)) if errs else float("nan")
