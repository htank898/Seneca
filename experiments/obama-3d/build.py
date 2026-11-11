"""Photo + landmarks + masks -> a rigged 2.5D head, as arrays Blender can load.

Writes .cache/rig.npz (vertices for the basis and every shape key, faces, UVs, bone weights,
pivots) plus .cache/fg.png (photo with person alpha) and .cache/bg.png (person painted out).

Everything is in photo pixels until the last step: (u, v) image coords, h = height toward
the camera. MediaPipe's z gives the face; an ellipsoid skull gives hair and ears; a soft
cylinder gives the torso.

    python build.py            (needs numpy + Pillow)
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(HERE, ".cache")
L = json.load(open(os.path.join(C, "landmarks.json")))
W, H = L["width"], L["height"]
P = np.array(L["landmarks"]) * [W, H, W]          # u, v, z (z: smaller = nearer)
LU, LV, LH = P[:, 0], P[:, 1], -P[:, 2]            # LH: height toward camera
photo = np.asarray(Image.open(os.path.join(C, "photo.jpg")).convert("RGB")).astype(np.float32) / 255
masks = np.asarray(Image.open(os.path.join(C, "masks.png")).convert("RGB")).astype(np.float32) / 255
person = masks[..., 0]

STEP = 4                       # grid spacing in photo px
VMAX = 2100                    # nothing below this is in frame
CROP = (160, 0, 1760, 2000)    # what the camera sees (4:5)
D = 8000.0                     # camera distance in px
S = 1 / 1000                   # px -> Blender units

def sstep(a, b, x):
    k = np.clip((x - a) / (b - a), 0, 1)
    return k * k * (3 - 2 * k)

def curve(ids, u):
    """Piecewise-linear v(u) through the given landmarks (sorted by u), clamped at the ends."""
    ids = sorted(ids, key=lambda i: LU[i])
    return np.interp(u, LU[ids], LV[ids])

# ---------------------------------------------------------------- grid
gu, gv = np.meshgrid(np.arange(0, W + 1, STEP, dtype=np.float32), np.arange(0, VMAX + 1, STEP, dtype=np.float32))
GH, GW = gu.shape
pu, pv = np.clip(gu.astype(int), 0, W - 1), np.clip(gv.astype(int), 0, H - 1)

# Dilate the person mask so the mesh reaches past the soft alpha edge.
pm = person > 0.2
for _ in range(4):
    pm = pm | np.roll(pm, 3, 0) | np.roll(pm, -3, 0) | np.roll(pm, 3, 1) | np.roll(pm, -3, 1)
valid = pm[pv, pu]

# ---------------------------------------------------------------- depth
CX = 952.0
HEAD = dict(cy=436.0, rx=265.0, ry=380.0, rz=300.0)
def skull(u, v):
    q = ((u - CX) / HEAD["rx"]) ** 2 + ((v - HEAD["cy"]) / HEAD["ry"]) ** 2
    return HEAD["rz"] * np.sqrt(np.clip(1 - q, 0, None))

c0 = np.median(LH[:468] - skull(LU[:468], LV[:468]))      # skull centre-plane offset
resid = LH[:468] - (skull(LU[:468], LV[:468]) + c0)

# Spread the landmark residuals over the grid (normalised Gaussian splat), fading to 0 off the face.
sig = 28.0
num = np.zeros_like(gu); den = np.zeros_like(gu)
for u0, v0, r in zip(LU[:468], LV[:468], resid):
    x0, x1 = int((u0 - 3 * sig) // STEP), int((u0 + 3 * sig) // STEP) + 2
    y0, y1 = int((v0 - 3 * sig) // STEP), int((v0 + 3 * sig) // STEP) + 2
    x0, y0 = max(x0, 0), max(y0, 0)
    w = np.exp(-((gu[y0:y1, x0:x1] - u0) ** 2 + (gv[y0:y1, x0:x1] - v0) ** 2) / (2 * sig * sig))
    num[y0:y1, x0:x1] += w * r; den[y0:y1, x0:x1] += w
face_res = num / (den + 0.15)
h_head = skull(gu, gv) + c0 + face_res

h_body = c0 - 150 + 260 * np.sqrt(np.clip(1 - ((gu - 945) / 720) ** 2, 0, None))
JAWLINE = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323, 454]
jaw_v = curve(JAWLINE, gu)
outside = (gu < LU[234]) | (gu > LU[454])
jaw_v = np.where(outside, 640.0, jaw_v)
w_head = sstep(jaw_v + 120, jaw_v + 10, gv)                       # 1 above the jawline, 0 by the collar
h = w_head * h_head + (1 - w_head) * np.maximum(h_body, np.minimum(h_head, h_body + 80))

# ---------------------------------------------------------------- faces (with the mouth cut open)
UP_IN = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
LO_IN = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
seam = 0.2 * curve(UP_IN, gu) + 0.8 * curve(LO_IN, gu)          # bottom edge of the upper teeth
in_mouth = (gu > LU[78] + 2) & (gu < LU[308] - 2)

idx = -np.ones((GH, GW), np.int64)
idx[valid] = np.arange(valid.sum())
U, V, Hh = list(gu[valid]), list(gv[valid]), list(h[valid])
side = [0] * len(U)                     # -1: seam vertex on the upper lip, +1: on the jaw

# The mouth is split along the seam: each column gets two coincident seam vertices, one riding
# with the upper face and one with the jaw. Column strips near the seam are zipper-triangulated
# so the mesh is closed at rest and opens cleanly when the jaw drops.
cols = [j for j in range(GW) if in_mouth[0, j]]
sv = {}
for j in cols:
    s = seam[0, j]; r = int(s // STEP)
    hs = h[r, j] + (s - gv[r, j]) / STEP * (h[r + 1, j] - h[r, j])
    for sd in (-1, 1):
        U.append(gu[0, j]); V.append(s); Hh.append(hs); side.append(sd)
    sv[j] = (len(U) - 2, len(U) - 1)
band = np.zeros((GH - 1, GW - 1), bool)
tris = []
def zipper(Lc, Rc):
    i = k = 0
    while i < len(Lc) - 1 or k < len(Rc) - 1:
        if k == len(Rc) - 1 or (i < len(Lc) - 1 and V[Lc[i + 1]] <= V[Rc[k + 1]]):
            tris.append((Lc[i], Lc[i + 1], Rc[k])); i += 1
        else:
            tris.append((Lc[i], Rc[k + 1], Rc[k])); k += 1
for j in cols:
    if j + 1 not in sv:
        continue
    s0, s1 = seam[0, j], seam[0, j + 1]
    r0, r1 = int((min(s0, s1) - 12) // STEP), int((max(s0, s1) + 12) // STEP) + 1
    band[r0:r1, j] = True
    def column(jj, s, upper):
        rows = [r for r in range(r0, r1 + 1) if (gv[r, jj] < s) == upper]
        up, lo = sv[jj]
        return [idx[r, jj] for r in rows] + [up] if upper else [lo] + [idx[r, jj] for r in rows]
    zipper(column(j, s0, True), column(j + 1, s1, True))
    zipper(column(j, s0, False), column(j + 1, s1, False))

a, b, c_, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
ok = (a >= 0) & (b >= 0) & (c_ >= 0) & (d >= 0)
quads = np.stack([a, b, c_, d], -1)[ok & ~band]
U, V, Hh, side = map(np.array, (U, V, Hh, side))

# ---------------------------------------------------------------- shape keys (offsets in u, v, h)
keys = {}

def blink(upper, lower, brow):
    y_u, y_l, y_b = curve(upper, U), curve(lower, U), curve(brow, U)
    x0, x1 = LU[upper].min(), LU[upper].max()
    m = 0.35 * (x1 - x0)
    lat = sstep(x0 - m, x0, U) * sstep(x1 + m, x1, U)
    y_c = y_l - 0.3 * (y_l - y_u)
    Lb = 0.6 * (LV[lower].max() - LV[upper].min()) + 6
    dv = np.zeros_like(U); dh = np.zeros_like(U)
    lid = (V >= y_b) & (V < y_u)
    dv[lid] = ((y_c - y_u) * (V - y_b) / np.maximum(y_u - y_b, 1))[lid]
    opening = (V >= y_u) & (V <= y_l)
    dv[opening] = (y_c - V)[opening]; dh[opening] = 4
    below = (V > y_l) & (V < y_l + Lb)
    dv[below] = ((y_c - y_l) * (1 - (V - y_l) / Lb))[below]
    return np.zeros_like(U), dv * lat, dh * lat

keys["blinkA"] = blink([33, 246, 161, 160, 159, 158, 157, 173, 133], [33, 7, 163, 144, 145, 153, 154, 155, 133], [46, 53, 52, 65, 55])
keys["blinkB"] = blink([263, 466, 388, 387, 386, 385, 384, 398, 362], [263, 249, 390, 373, 374, 380, 381, 382, 362], [276, 283, 282, 295, 285])

def brows():
    dv = np.zeros_like(U)
    for ids in ([70, 63, 105, 66, 107], [300, 293, 334, 296, 336]):
        bx, by = LU[ids].mean(), LV[ids].mean()
        sy = np.where(V < by, 110.0, 32.0)                         # forehead follows, lids barely do
        dv += -16 * np.exp(-(((U - bx) / 85) ** 2 + ((V - by) / sy) ** 2))
    return np.zeros_like(U), dv, np.zeros_like(U)
keys["browUp"] = brows()

def smile_relax():
    du = np.zeros_like(U); dv = np.zeros_like(U)
    for i, s in ((61, 1), (291, -1)):
        g = np.exp(-(((U - LU[i]) / 42) ** 2 + ((V - LV[i]) / 38) ** 2))
        du += s * 20 * g; dv += 9 * g
    return du, dv, np.zeros_like(U)
keys["smileRelax"] = smile_relax()

# Jaw: rotate the lower face about the jaw hinge (in the v/h plane), weighted.
JP = np.array([LV[234], c0 - 20.0])                               # hinge: ear level, behind the face
seam_v = 0.2 * curve(UP_IN, U) + 0.8 * curve(LO_IN, U)
seam_ext = np.where((U > LU[78]) & (U < LU[308]), seam_v, np.interp(U, [LU[61], LU[291]], [LV[61], LV[291]]))
mouth_x = (U > LU[78] + 2) & (U < LU[308] - 2)
w_jaw = np.where(mouth_x, (V >= seam_ext).astype(float), sstep(seam_ext - 10, seam_ext + 30, V))
w_jaw = np.where(side == -1, 0.0, np.where(side == 1, 1.0, w_jaw))
lat = sstep(230, 120, np.abs(U - CX))
jl = curve(JAWLINE, U)
w_jaw = w_jaw * lat * (1 - 0.6 * sstep(jl, jl + 110, V)) * (V < jl + 160)
th = np.radians(11) * w_jaw
dd, df = V - JP[0], Hh - JP[1]
keys["jawOpen"] = (np.zeros_like(U), dd * np.cos(th) + df * np.sin(th) - dd, -dd * np.sin(th) + df * np.cos(th) - df)

wb = np.clip((VMAX - V) / (VMAX - 900), 0, 1)
keys["breath"] = ((U - CX) * 0.004 * wb, -6 * wb, np.zeros_like(U))

# ---------------------------------------------------------------- to Blender space
ucen, vcen = (CROP[0] + CROP[2]) / 2, (CROP[1] + CROP[3]) / 2
def world(u, v, hh):
    k = (D - hh) / D * S                                          # slide along the camera ray
    return np.stack([(u - ucen) * k, -hh * S, (vcen - v) * k], -1).astype(np.float32)

out = {"basis": world(U, V, Hh), "quads": quads.astype(np.int32), "tris": np.array(tris, np.int32),
       "uv": np.stack([U / W, 1 - V / H], -1).astype(np.float32),
       "w_head": np.concatenate([w_head[valid], np.ones(len(U) - valid.sum())]).astype(np.float32)}
for name, (du, dv, dh) in keys.items():
    out["key_" + name] = world(U + du, V + dv, Hh + dh)
out["head_pivot"] = world(np.array([CX]), np.array([590.0]), np.array([c0 - 40]))[0]
mouth_h = float(np.median(LH[[13, 14, 78, 308]]))
out["cavity"] = np.array([*world(np.array([CX]), np.array([650.0]), np.array([mouth_h - 70]))[0],
                          120 * S, 80 * S], np.float32)
out["camera"] = np.array([D * S, (CROP[3] - CROP[1]) * S], np.float32)
out["bg_scale"] = np.array([(D + 900) / D], np.float32)
out["photo_size"] = np.array([W, H, ucen, vcen], np.float32)
np.savez_compressed(os.path.join(C, "rig.npz"), **out)

# ---------------------------------------------------------------- textures
alpha = np.clip((person - 0.12) / 0.75, 0, 1)
Image.fromarray((np.dstack([photo, alpha]) * 255).astype(np.uint8), "RGBA").save(os.path.join(C, "fg.png"))

# Paint the person out of the background (push-pull fill), so head turns reveal plausible wall.
hole = person > 0.15
for _ in range(6):
    hole = hole | np.roll(hole, 4, 0) | np.roll(hole, -4, 0) | np.roll(hole, 4, 1) | np.roll(hole, -4, 1)
def resize(img, shape):
    return np.dstack([np.asarray(Image.fromarray(img[..., i]).resize((shape[1], shape[0]), Image.BILINEAR))
                      for i in range(img.shape[2])])

def pushpull(img, w):
    """Fill w == 0 pixels from coarser levels; bilinear upsampling keeps it smooth."""
    if min(w.shape) <= 2:
        return np.broadcast_to((img * w[..., None]).sum((0, 1)) / max(w.sum(), 1e-6), img.shape).copy()
    h2, w2 = -(-w.shape[0] // 2) * 2, -(-w.shape[1] // 2) * 2
    pi = np.pad(img * w[..., None], ((0, h2 - w.shape[0]), (0, w2 - w.shape[1]), (0, 0)))
    pw = np.pad(w, ((0, h2 - w.shape[0]), (0, w2 - w.shape[1])))
    si = pi.reshape(h2 // 2, 2, w2 // 2, 2, 3).sum((1, 3)); sw = pw.reshape(h2 // 2, 2, w2 // 2, 2).sum((1, 3))
    coarse = pushpull(si / np.maximum(sw, 1e-6)[..., None], np.clip(sw, 0, 1))
    up = resize(coarse.astype(np.float32), w.shape)
    k = w[..., None]
    return k * img + (1 - k) * up

fill = pushpull(photo, (~hole).astype(np.float32))
Image.fromarray((np.clip(fill, 0, 1) * 255).astype(np.uint8)).save(os.path.join(C, "bg.png"))

print(f"verts {len(U)}  quads {len(quads)}  tris {len(tris)}  c0 {c0:.1f}  face depth {h[valid].min():.0f}..{h[valid].max():.0f}")
