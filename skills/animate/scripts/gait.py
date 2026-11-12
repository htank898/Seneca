"""gait: standard walk (and run) animations for any character, when there's no reference video.
Runs inside Blender (it uses rig.load_bvh). With a reference video, use pose.py instead: that
copies the actual performance one-to-one; this is the fallback.

Libraries (open mocap, real performers):
  CMU Graphics Lab Motion Capture Database: ~2,600 clips, free for any use. Fetched one clip at a
      time on demand from a BVH mirror and cached in ~/.cache/seneca-adapt/cmu/.
  100STYLE (Ian Mason, CC BY 4.0, credit "The 100STYLE Dataset - Ian Mason"): 100 locomotion
      styles (e.g. Old, Proud, Sneaky, Robot, Zombie...), each walked forwards/backwards/sideways.
      One 1.5 GB archive, downloaded once:  node scripts/gait-fetch.mjs 100style

    import bkit as k, rig, gait
    mo, gains = gait.walk("cmu:02_01", seconds=8, cadence=1.0, stride=1.1, arm_swing=0.8)
    mo, gains = gait.walk("100style:Proud", seconds=8)
    arm = rig.armature(mo)
    rig.retarget(arm, mo, locomotion="footlock", gains=gains)

gait.search("sneak") lists CMU clips by description; gait.styles() lists 100STYLE styles.

Adjusting the gait (all 1.0 = as recorded):
  cadence    steps per second (playback rate of the cycle)
  stride     leg swing amplitude (thigh + shin); with footlock, travel speed follows
  arm_swing  upper arm + forearm swing amplitude
"""
import os
import re
import urllib.request
import zipfile

import rig
from mathutils import Vector

CACHE = os.path.expanduser("~/.cache/seneca-adapt")
CMU_RAW = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master"
STYLE_ZIP = os.path.join(CACHE, "100style", "100STYLE.zip")

# Hand-checked starting points (CMU trial ids)
PRESETS = {"walk": "cmu:02_01", "slow": "cmu:07_04", "brisk": "cmu:07_12", "stride": "cmu:08_05"}


def _get(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        tmp = dest + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, dest)
    return dest


def cmu_index():
    path = _get(f"{CMU_RAW}/cmu-mocap-index-text.txt", os.path.join(CACHE, "cmu", "index.txt"))
    out = {}
    with open(path, errors="ignore") as fh:
        for line in fh:
            m = re.match(r"^\s*(\d+_\d+)\s+(.+?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def search(term):
    """CMU clips whose description contains term, e.g. search('sneak')."""
    t = term.lower()
    return {k: v for k, v in cmu_index().items() if t in v.lower()}


def fetch_cmu(trial):
    subj = trial.split("_")[0]
    return _get(f"{CMU_RAW}/data/{int(subj):03d}/{trial}.bvh", os.path.join(CACHE, "cmu", f"{trial}.bvh"))


def styles():
    if not os.path.exists(STYLE_ZIP):
        raise FileNotFoundError("100STYLE not downloaded: node scripts/gait-fetch.mjs 100style")
    with zipfile.ZipFile(STYLE_ZIP) as z:
        names = {os.path.basename(n).rsplit("_", 1)[0] for n in z.namelist()
                 if n.lower().endswith(".bvh") and "__MACOSX" not in n}
    return sorted(names)


def fetch_100style(style, movement="FW"):
    """movement: FW walk forwards, BW walk backwards, FR/BR run forwards/backwards, SW/SR walk/run
    sideways, ID idle, TR1-3 transitions. 60 fps source."""
    want = f"{style}_{movement}.bvh".lower()
    dest = os.path.join(CACHE, "100style", "bvh", f"{style}_{movement}.bvh")
    if os.path.exists(dest):
        return dest
    if not os.path.exists(STYLE_ZIP):
        raise FileNotFoundError("100STYLE not downloaded: node scripts/gait-fetch.mjs 100style")
    with zipfile.ZipFile(STYLE_ZIP) as z:
        hit = [n for n in z.namelist() if os.path.basename(n).lower() == want and "__MACOSX" not in n]
        if not hit:
            raise KeyError(f"{want} not in 100STYLE (see gait.styles())")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with z.open(hit[0]) as src, open(dest, "wb") as dst:
            dst.write(src.read())
    return dest


def resolve(source):
    """'cmu:02_01' | '100style:Proud' | '100style:Proud/BW' | preset name | a .bvh path."""
    source = PRESETS.get(source, source)
    if source.startswith("cmu:"):
        return fetch_cmu(source[4:])
    if source.startswith("100style:"):
        style, _, mv = source[9:].partition("/")
        return fetch_100style(style, mv or "FW")
    return source


# ---------------------------------------------------------------- cycles
def _forward(mo):
    r = mo["root"]
    d = (r[-1] - r[0]).xy
    return d.normalized() if d.length > 1e-6 else Vector((0, 1))


def cycles(mo, side="L"):
    """Frame indices where the given foot is furthest forward (heel strike), i.e. cycle bounds."""
    fwd = _forward(mo)
    ank = 27 if side == "L" else 28
    reach = [(fr[ank].xy).dot(fwd) for fr in mo["world"]]
    n = len(reach)
    win = max(2, int(mo["fps"] * 0.15))
    peaks = [i for i in range(win, n - win)
             if reach[i] == max(reach[i - win:i + win + 1]) and reach[i] > 0]
    return peaks


def loop(mo, seconds, crossfade=0):
    """Cut one clean cycle (the middle one) and repeat it for `seconds`, carrying the root forward."""
    peaks = cycles(mo)
    if len(peaks) < 2:
        return mo  # too short to find a cycle: use as is
    # Pick the STRAIGHTEST full cycle (libraries like 100STYLE walk loops around a capture volume,
    # so an arbitrary cycle can sit on a turn): straightness = chord / path length of the root.
    fps = mo["fps"]
    best, a, b = -1.0, peaks[0], peaks[1]
    for i0 in range(len(peaks) - 1):
        for i1 in range(i0 + 1, min(i0 + 3, len(peaks))):
            p0, p1 = peaks[i0], peaks[i1]
            if not (0.6 * fps <= p1 - p0 <= 2.2 * fps):
                continue
            path = sum(((mo["root"][t + 1] - mo["root"][t]).xy.length for t in range(p0, p1)), 0.0)
            chord = (mo["root"][p1] - mo["root"][p0]).xy.length
            score = chord / path if path > 1e-6 else 0.0
            if score > best + 1e-3:
                best, a, b = score, p0, p1
    W, R = mo["world"][a:b], mo["root"][a:b]
    step = mo["root"][b] - mo["root"][a]
    step.z = 0
    # Seamless loop: a recorded step is never exactly periodic, so the pose at b differs from the
    # pose at a and the repeat would snap once per cycle. Spread that residual linearly across the
    # cycle (cyclic offset correction) so frame len(W) continues smoothly into frame 0.
    m = len(W)
    resid = [mo["world"][b][j] - mo["world"][a][j] for j in range(len(W[0]))]
    rz = mo["root"][b].z - mo["root"][a].z
    W = [[p - resid[j] * (t / m) for j, p in enumerate(fr)] for t, fr in enumerate(W)]
    R = [r - Vector((0, 0, rz * (t / m))) for t, r in enumerate(R)]
    n = int(seconds * mo["fps"])
    world, root = [], []
    for i in range(n):
        k, j = divmod(i, len(W))
        fr = W[j]
        # crossfade the seam so the last frames of a cycle blend into the first of the next
        if j < crossfade and (k > 0):
            t = (j + 1) / (crossfade + 1)
            prev = W[len(W) - crossfade + j]
            fr = [p.lerp(q, t) for p, q in zip(prev, fr)]
        world.append(fr)
        root.append(R[j] - R[0] + step * k)
    out = dict(mo)
    out.update(world=world, root=root, frames=n, valid=[True] * n, cycle=(a, b), straightness=round(best, 3))
    return out


def walk(source="walk", seconds=8.0, cadence=1.0, stride=1.0, arm_swing=1.0, fps=None, height=1.75):
    """A looping walk from the library, ready for rig.retarget(..., gains=gains)."""
    path = resolve(source)
    mo = rig.load_bvh(path, fps=fps, height=height, speed=cadence)
    mo = loop(mo, seconds)
    gains = {}
    if stride != 1.0:
        gains.update(thigh=stride, shin=stride)
    if arm_swing != 1.0:
        gains.update(upper_arm=arm_swing, forearm=arm_swing)
    return mo, gains
