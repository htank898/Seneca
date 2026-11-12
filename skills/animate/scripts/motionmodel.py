"""motionmodel: a statistical model of an action learned from many performances: the mean
motion plus its main ways of varying (PCA), so you can animate the average of everyone and then
generate endless new, plausible variations that copy no one. Runs inside Blender (numpy + rig).

    import rig, gait, motionmodel as mm
    insts = mm.gait_cycles_from_bvh([gait.fetch_cmu(t) for t in trials])   # many walkers -> cycles
    model = mm.fit(insts)                    # mean + components + between/within-person spread
    mo = mm.generate(model, seconds=10)                        # the average person, slight per-step wobble
    who = mm.person(model, seed=7)                             # a new individual nobody recorded
    mo = mm.generate(model, seconds=10, person_z=who, wobble=1.0, seed=3)  # their walk, every step a bit different
    arm = rig.armature(mo); rig.retarget(arm, mo, locomotion="root")

How it works
  1. Instances: each performance is cut at matching events. A gait cycle runs from one left heel
     strike to the next; a pitch would run from first movement to ball release.
  2. Time normalization: every instance is resampled to N phase samples (0..1), so "40% through the
     stride" lines up across people. Cyclic instances are made seamless (end == start).
  3. Size/heading normalization: each instance is rotated to travel along +Y. The body is stored
     as unit bone DIRECTIONS (so tall and short people average cleanly) and the root as bob / sway /
     forward speed in leg lengths, plus the instance duration.
  4. Model: mean vector + principal components (SVD), keeping the components that explain
     `keep` of the variance. A new instance = mean + sum(z_k * sigma_k * component_k) with z_k drawn
     from a normal distribution (clipped at +-2.5 sigma) and scaled by `variety`.
  5. Generation: a different instance per repetition; consecutive instances are blended across
     each cycle (at phase p the pose is lerp(A(p), B(p), smoothstep(p))), so there is no seam.

The same fit()/sample() work for one-shot actions (a pitch, a jump): pass instances with
cyclic=False and cut them at consistent events. (Pure linear time normalization; aligning sub-events
with dynamic time warping is the next refinement for actions with variable internal timing.)
"""
import json
import math

import numpy as np
from mathutils import Vector

import rig

N = 60  # phase samples per instance

# body segments as (parent point, child point); 33=pelvis centre, 34=shoulder centre, 35=ear centre
H, S, E = 33, 34, 35
SEGS = [(H, 23), (23, 25), (25, 27), (27, 31), (H, 24), (24, 26), (26, 28), (28, 32), (H, S),
        (S, 11), (11, 13), (13, 15), (15, 19), (S, 12), (12, 14), (14, 16), (16, 20), (S, E), (E, 7)]
SEG_NAMES = ["hipL", "thighL", "shinL", "footL", "hipR", "thighR", "shinR", "footR", "torso",
             "shL", "uarmL", "farmL", "handL", "shR", "uarmR", "farmR", "handR", "neck", "earL"]
NS = len(SEGS)


def _ext(P):
    return list(P) + [(P[23] + P[24]) / 2, (P[11] + P[12]) / 2, (P[7] + P[8]) / 2]


def _resample(seq, a, b, n=N):
    """Linear resample of frames a..b (inclusive of b's position as phase 1) to n samples [0,1)."""
    out = []
    for k in range(n):
        x = a + (b - a) * k / n
        i = int(math.floor(x))
        t = x - i
        out.append((i, min(i + 1, len(seq) - 1), t))
    return out


# ---------------------------------------------------------------- instances
def instance(mo, a, b, cyclic=True, events=None):
    """One performance segment (frames a..b of a rig-style mo with world + root) -> feature dict.
    events: [(frame, phase), ...] inside (a, b) to align on, e.g. the other foot's heel strike at 0.5;
    time is warped piecewise-linearly so every instance hits its events at the same phase."""
    fps = mo["fps"]
    W, R = mo["world"], mo["root"]
    chord = (R[b] - R[a]).xy
    ang = math.atan2(chord.x, chord.y) if chord.length > 1e-6 else 0.0  # rotate travel onto +Y
    c, s = math.cos(ang), math.sin(ang)
    rot = lambda v: Vector((c * v.x - s * v.y, s * v.x + c * v.y, v.z))
    legs = [((P[23] - P[25]).length + (P[25] - P[27]).length + (P[24] - P[26]).length + (P[26] - P[28]).length) / 2
            for P in W[a:b + 1]]
    leg = float(np.median(legs))
    duration = (b - a) / fps

    def pose_at(x):
        i = min(int(math.floor(x)), len(W) - 2)
        t = x - i
        P = [p.lerp(q, t) for p, q in zip(_ext(W[i]), _ext(W[i + 1]))]
        r = rot(R[i].lerp(R[i + 1], t) - R[a])
        d = np.array([np.array(rot(P[q] - P[p]).normalized()) for p, q in SEGS])
        return d, np.array([r.x, r.z, r.y]) / leg

    knots = [(a, 0.0)] + sorted(events or []) + [(b, 1.0)]

    def warp(ph):
        for (f0, p0), (f1, p1) in zip(knots, knots[1:]):
            if ph <= p1:
                return f0 + (f1 - f0) * ((ph - p0) / max(p1 - p0, 1e-9))
        return b

    xs = [warp(k / N) for k in range(N + 1)]                   # N samples + the closing sample at b
    D, Rr = zip(*[pose_at(x) for x in xs])
    D, Rr = np.stack(D), np.stack(Rr)
    root = np.zeros((N, 3))                                    # lateral, vertical (legs), fwd speed (legs/s)
    root[:, 0] = Rr[:N, 0]
    root[:, 1] = Rr[:N, 1]
    root[:, 2] = (Rr[1:, 2] - Rr[:N, 2]) * N / duration
    dirs = D[:N].copy()
    if cyclic:
        # seamless: spread the end-vs-start residual across the cycle so phase 1 == phase 0
        ramp = (np.arange(N) / N)[:, None]
        dirs -= (D[N] - D[0])[None] * ramp[:, :, None]
        root[:, 0] -= (Rr[N, 0] - Rr[0, 0]) * ramp[:, 0]
        root[:, 1] -= (Rr[N, 1] - Rr[0, 1]) * ramp[:, 0]
    root[:, 0] -= root[:, 0].mean()
    root[:, 1] -= root[:, 1].mean()
    return {"dirs": dirs, "root": root, "duration": duration, "leg": leg, "cyclic": cyclic}


def _extrema(mo, side, sign):
    """Frames where a foot is furthest forward (sign=+1, heel strike) or back (sign=-1, toe-off)."""
    import gait
    fwd = gait._forward(mo)
    ank = 27 if side == "L" else 28
    reach = [sign * (fr[ank].xy).dot(fwd) for fr in mo["world"]]
    win = max(2, int(mo["fps"] * 0.15))
    n = len(reach)
    return [i for i in range(win, n - win) if reach[i] == max(reach[i - win:i + win + 1]) and reach[i] > 0]


def gait_cycles_from_bvh(paths, fps=60, min_straight=0.95, verbose=True):
    """Every clean straight gait cycle in every BVH (left heel strike -> next left heel strike),
    time-aligned on all four gait events: R toe-off, R heel strike, L toe-off (each warped to its
    median phase across the whole library), so peaks line up before averaging."""
    cand = []
    for p in paths:
        try:
            mo = rig.load_bvh(p, fps=fps)
        except Exception as e:  # odd skeletons / broken files: skip, report
            if verbose:
                print(f"[model] skip {p}: {e}", flush=True)
            continue
        ls, rs = _extrema(mo, "L", 1), _extrema(mo, "R", 1)
        lo, ro = _extrema(mo, "L", -1), _extrema(mo, "R", -1)
        durs = [(b - a) / fps for a, b in zip(ls, ls[1:])]
        med_d = sorted(durs)[len(durs) // 2] if durs else 0
        got = 0
        for a, b in zip(ls, ls[1:]):
            dur = (b - a) / fps
            if not (0.7 <= dur <= 1.8) or abs(dur - med_d) > 0.2 * med_d:  # misdetected half/double cycles
                continue
            path = sum(((mo["root"][t + 1] - mo["root"][t]).xy.length for t in range(a, b)), 0.0)
            chord = (mo["root"][b] - mo["root"][a]).xy.length
            if path < 1e-6 or chord / path < min_straight or chord < 0.3:
                continue
            ev = {}
            for key, frames, lo_, hi_ in (("R_off", ro, 0.0, 0.35), ("R_on", rs, 0.3, 0.7), ("L_off", lo, 0.45, 0.85)):
                hit = [f for f in frames if a + lo_ * (b - a) < f < a + hi_ * (b - a)]
                if hit:
                    ev[key] = hit[0]
            if len(ev) < 3 or not (ev["R_off"] < ev["R_on"] < ev["L_off"]):
                continue
            cand.append((mo, a, b, ev, str(p).split("/")[-1]))
            got += 1
        if verbose:
            print(f"[model] {str(p).split('/')[-1]}: {got} cycle(s)", flush=True)
    if not cand:
        return []
    # target phase of each event = its median across the library
    target = {k: float(np.median([(c[3][k] - c[1]) / (c[2] - c[1]) for c in cand])) for k in ("R_off", "R_on", "L_off")}
    insts = []
    for mo, a, b, ev, src in cand:
        inst = instance(mo, a, b, events=[(ev[k], target[k]) for k in ("R_off", "R_on", "L_off")])
        inst.update(source=src, subject=src.split("_")[0], event_phases=target)
        insts.append(inst)
    return insts


# ---------------------------------------------------------------- model
def _vec(inst):
    return np.concatenate([inst["dirs"].ravel(), inst["root"].ravel() * 0.5, [inst["duration"]]])


def _unvec(v):
    d = v[:N * NS * 3].reshape(N, NS, 3)
    r = v[N * NS * 3:N * NS * 3 + N * 3].reshape(N, 3) / 0.5
    return d, r, float(v[-1])


def fit(insts, keep=0.95):
    """Mean + principal components, plus how much each component varies BETWEEN people (identity)
    and WITHIN a person from one repetition to the next (when instances carry a 'subject')."""
    X = np.stack([_vec(i) for i in insts])
    mean = X.mean(0)
    Xc = X - mean
    U, Sv, Vt = np.linalg.svd(Xc, full_matrices=False)
    var = Sv ** 2 / max(len(X) - 1, 1)
    frac = np.cumsum(var) / var.sum()
    k = int(np.searchsorted(frac, keep) + 1)
    comps = Vt[:k]
    Z = Xc @ comps.T                                    # every instance in component coordinates
    subj = [i.get("subject", str(n)) for n, i in enumerate(insts)]
    groups = {}
    for z, sname in zip(Z, subj):
        groups.setdefault(sname, []).append(z)
    means = {g: np.mean(v, 0) for g, v in groups.items()}
    between = np.std(np.stack(list(means.values())), 0) if len(means) > 1 else np.sqrt(var[:k])
    # step-to-step wobble: spread of cycles around their own RECORDING's mean (a person's separate
    # trials can be deliberately different speeds, which is identity/intent, not wobble)
    clips = {}
    for z, inst in zip(Z, insts):
        clips.setdefault(inst.get("source", "?"), []).append(z)
    resid = [z - np.mean(v, 0) for v in clips.values() if len(v) > 1 for z in v]
    within = np.std(np.stack(resid), 0) if resid else np.sqrt(var[:k]) * 0.2
    return {"mean": mean, "components": comps, "sigma": np.sqrt(var[:k]), "explained": frac[:k],
            "between": between, "within": within, "n": len(X), "subjects": len(groups),
            "sources": sorted({i.get("source", "?") for i in insts}),
            "leg": float(np.median([i["leg"] for i in insts])), "cyclic": insts[0]["cyclic"]}


def save(model, path):
    out = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in model.items()}
    with open(path, "w") as fh:
        json.dump(out, fh)


def load(path):
    with open(path) as fh:
        m = json.load(fh)
    for k in ("mean", "components", "sigma", "explained", "between", "within"):
        m[k] = np.array(m[k])
    return m


def sample(model, rng, variety=1.0):
    z = np.clip(rng.standard_normal(len(model["sigma"])), -2.5, 2.5) * variety
    return model["mean"] + (z * model["sigma"]) @ model["components"]


def describe(model):
    """What each of the first components changes, measured (for naming them)."""
    out = []
    for k in range(min(5, len(model["sigma"]))):
        hi = _unvec(model["mean"] + 2 * model["sigma"][k] * model["components"][k])
        lo = _unvec(model["mean"] - 2 * model["sigma"][k] * model["components"][k])
        def stats(u):
            d, r, dur = u
            th = d[:, SEG_NAMES.index("thighL")]
            sh = d[:, SEG_NAMES.index("shinL")]
            knee = np.degrees(np.arccos(np.clip((th * sh).sum(1) / (np.linalg.norm(th, axis=1) * np.linalg.norm(sh, axis=1)), -1, 1)))
            arm = d[:, SEG_NAMES.index("uarmL")]
            swing = np.degrees(np.ptp(np.arctan2(arm[:, 1], -arm[:, 2])))
            return {"cycle_s": round(dur, 2), "speed_legs_s": round(float(r[:, 2].mean()), 2),
                    "knee_max": round(float(knee.max())), "arm_swing": round(float(swing)),
                    "bob": round(float(np.ptp(r[:, 1])), 3)}
        out.append({"component": k + 1, "variance_share": round(float(model["explained"][k] - (model["explained"][k - 1] if k else 0)), 3),
                    "-2sd": stats(lo), "+2sd": stats(hi)})
    return out


# ---------------------------------------------------------------- generation
LEN_KEYS = {"hipL": "hip_width", "hipR": "hip_width", "thighL": "thigh", "thighR": "thigh", "shinL": "shin",
            "shinR": "shin", "footL": "foot", "footR": "foot", "torso": "torso", "shL": "shoulder_width",
            "shR": "shoulder_width", "uarmL": "upper_arm", "uarmR": "upper_arm", "farmL": "forearm",
            "farmR": "forearm", "handL": "hand", "handR": "hand", "neck": "neck", "earL": "shoulder_width"}
DEFAULT_LENGTHS = {"torso": 0.50, "shoulder_width": 0.36, "hip_width": 0.19, "neck": 0.20, "upper_arm": 0.31,
                   "forearm": 0.25, "hand": 0.09, "thigh": 0.43, "shin": 0.43, "foot": 0.21, "heel": 0.05}


def _decode_pose(dirs, lengths):
    """Bone directions -> 33 landmarks (hip-centred), chained with the target body's lengths."""
    P = {H: Vector((0, 0, 0))}
    for m, (p, q) in enumerate(SEGS):
        v = Vector(dirs[m]).normalized()
        key = LEN_KEYS[SEG_NAMES[m]]
        L = lengths[key] * (0.5 if key in ("hip_width", "shoulder_width") else 1.0)
        if SEG_NAMES[m] == "earL":
            L = 0.075
        P[q] = P[p] + v * L
    out = [Vector((0, 0, 0))] * 33
    for i in range(33):
        if i in P:
            out[i] = P[i].copy()
    out[8] = P[E] - (P[7] - P[E])
    out[0] = P[E].copy()
    out[17], out[21] = out[19], out[19]
    out[18], out[22] = out[20], out[20]
    out[29] = out[27] + Vector((0, 0, -0.02))
    out[30] = out[28] + Vector((0, 0, -0.02))
    return out


def person(model, seed=1, variety=1.0):
    """A new individual: a fixed offset in component space drawn from the between-people spread."""
    rng = np.random.default_rng(seed)
    return np.clip(rng.standard_normal(len(model["between"])), -2.5, 2.5) * model["between"] * variety


STRIDE_CV = 0.025  # healthy adults vary stride time ~2-3% step to step (gait-variability literature)


def auto_wobble(model, cv=STRIDE_CV):
    """Scale for the within-person spread so generated stride times vary by `cv` (coefficient of
    variation). Short mocap takes include speeding up / slowing down, which inflates the raw
    within-recording spread; calibrating to measured human stride variability keeps it lifelike."""
    dur_axis = model["components"][:, -1]
    sd = float(np.sqrt(np.sum((model["within"] * dur_axis) ** 2)))
    mean_d = float(model["mean"][-1])
    return min(1.0, cv * mean_d / sd) if sd > 1e-9 else 1.0


def generate(model, seconds=10.0, fps=24, person_z=None, wobble=None, seed=1, lengths=None):
    """A continuous performance by one individual (person_z; None = the average person). Every
    repetition deviates a little from that person, by the measured within-person spread x wobble;
    consecutive repetitions are blended so there is no seam. Returns a rig-style mo."""
    rng = np.random.default_rng(seed + 1000)
    if wobble is None:
        wobble = auto_wobble(model)
    lengths = dict(DEFAULT_LENGTHS, **(lengths or {}))
    leg = lengths["thigh"] + lengths["shin"]
    base = np.zeros(len(model["sigma"])) if person_z is None else np.asarray(person_z)
    n_frames = int(seconds * fps)
    count = int(seconds / 0.6) + 3

    def draw():
        z = base + np.clip(rng.standard_normal(len(base)), -2.5, 2.5) * model["within"] * wobble
        return _unvec(model["mean"] + z @ model["components"])

    insts = [draw() for _ in range(count)]
    world, root, chosen = [], [], []
    k, phase = 0, 0.0
    y = 0.0
    for f in range(n_frames):
        A, B = insts[k], insts[min(k + 1, len(insts) - 1)]
        w = phase * phase * (3 - 2 * phase)  # smoothstep: blend A -> B across the cycle
        x = phase * N
        i0, t = int(x) % N, x - int(x)
        i1 = (i0 + 1) % N

        def at(arr):
            return arr[i0] * (1 - t) + arr[i1] * t

        dirs = at(A[0]) * (1 - w) + at(B[0]) * w
        rt = at(A[1]) * (1 - w) + at(B[1]) * w
        dur = A[2] * (1 - w) + B[2] * w
        world.append(_decode_pose(dirs, lengths))
        y += rt[2] * leg / fps
        root.append(Vector((rt[0] * leg, y, leg + rt[1] * leg)))
        phase += 1.0 / (dur * fps)
        if phase >= 1.0:
            phase -= 1.0
            chosen.append(round(A[2], 3))
            k += 1
    return {"source": "motionmodel", "fps": fps, "frames": n_frames, "world": world, "root": root,
            "valid": [True] * n_frames, "lengths": lengths, "cycle_durations": chosen,
            "wobble": wobble, "seed": seed}
