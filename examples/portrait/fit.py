"""Approximate a photo with N translucent rotated ellipses (primitive-style hill climbing).
Output: JSON of shapes that the HTML page renders as CSS divs. No pixel data leaves this script."""
import json, sys, time
import numpy as np
from PIL import Image

src, out, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
W, H = 192, 240
ALPHA = 0.5
rng = np.random.default_rng(7)

img = Image.open(src).convert("RGB").crop((120, 0, 840, 900)).resize((W, H), Image.LANCZOS)
T = np.asarray(img, dtype=np.float32) / 255.0

# Weight the face more heavily so detail goes where recognition lives.
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
face = ((xx - 92) / 46) ** 2 + ((yy - 58) / 56) ** 2
Wt = 1.0 + 4.0 * np.exp(-np.clip(face - 1, 0, None) * 2.5) * (face < 1) + 1.5 * np.exp(-face) * (face >= 1)

bg = (T * Wt[..., None]).sum((0, 1)) / Wt.sum()
C = np.ones_like(T) * bg

def mask(s):
    cx, cy, rx, ry, ang = s
    r = max(rx, ry) + 1
    x0, x1 = int(max(0, cx - r)), int(min(W, cx + r + 1))
    y0, y1 = int(max(0, cy - r)), int(min(H, cy + r + 1))
    if x1 <= x0 or y1 <= y0:
        return None
    dx = xx[y0:y1, x0:x1] - cx + 0.5 * 0
    dy = yy[y0:y1, x0:x1] - cy
    c, sn = np.cos(ang), np.sin(ang)
    u = (dx * c + dy * sn) / rx
    v = (-dx * sn + dy * c) / ry
    m = (u * u + v * v) <= 1.0
    if not m.any():
        return None
    return (y0, y1, x0, x1), m

def evaluate(s):
    mk = mask(s)
    if mk is None:
        return 0.0, None, None
    (y0, y1, x0, x1), m = mk
    t = T[y0:y1, x0:x1][m]
    c = C[y0:y1, x0:x1][m]
    w = Wt[y0:y1, x0:x1][m][:, None]
    col = np.clip(((t - c * (1 - ALPHA)) / ALPHA * w).sum(0) / w.sum(), 0, 1)
    new = c * (1 - ALPHA) + col * ALPHA
    delta = float((w * ((new - t) ** 2 - (c - t) ** 2)).sum())
    return delta, col, mk

def random_shape(errmap):
    p = errmap.ravel() / errmap.sum()
    i = rng.choice(errmap.size, p=p)
    cy, cx = divmod(i, W)
    big = max(2.0, 60 * (1 - progress) ** 2)
    return [cx + rng.random(), cy + rng.random(), rng.uniform(1, big), rng.uniform(1, big), rng.uniform(0, np.pi)]

def mutate(s):
    s = list(s)
    k = rng.integers(3)
    if k == 0:
        s[0] = np.clip(s[0] + rng.normal(0, 3), 0, W); s[1] = np.clip(s[1] + rng.normal(0, 3), 0, H)
    elif k == 1:
        s[2] = max(0.8, s[2] + rng.normal(0, 2.5)); s[3] = max(0.8, s[3] + rng.normal(0, 2.5))
    else:
        s[4] = s[4] + rng.normal(0, 0.35)
    return s

shapes = []
t0 = time.time()
for n in range(N):
    progress = n / N
    errmap = (Wt * ((C - T) ** 2).sum(2)) + 1e-6
    best, bd = None, 0.0
    for _ in range(120):
        s = random_shape(errmap)
        d, _, _ = evaluate(s)
        if d < bd:
            best, bd = s, d
    if best is None:
        continue
    fails = 0
    while fails < 100:
        s = mutate(best)
        d, _, _ = evaluate(s)
        if d < bd:
            best, bd, fails = s, d, 0
        else:
            fails += 1
    d, col, ((y0, y1, x0, x1), m) = evaluate(best)
    reg = C[y0:y1, x0:x1]
    reg[m] = reg[m] * (1 - ALPHA) + col * ALPHA
    cx, cy, rx, ry, ang = best
    shapes.append([round(cx, 2), round(cy, 2), round(rx, 2), round(ry, 2), round(float(np.degrees(ang)) % 180, 1),
                   *[int(round(v * 255)) for v in col]])
    if n % 100 == 0:
        rmse = float(np.sqrt(((C - T) ** 2).mean()))
        print(f"{n} shapes  rmse={rmse:.4f}  {time.time()-t0:.0f}s", flush=True)

json.dump({"w": W, "h": H, "alpha": ALPHA, "bg": [int(round(v * 255)) for v in bg], "shapes": shapes},
          open(out, "w"), separators=(",", ":"))
Image.fromarray((C * 255).astype(np.uint8)).resize((W * 3, H * 3), Image.NEAREST).save(out.replace(".json", "_preview.png"))
print("done", len(shapes), f"{time.time()-t0:.0f}s")
