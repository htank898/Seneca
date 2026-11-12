"""prep: cut each character view out of its background and frame it for TRELLIS.2.

    python prep.py --out <dir>/views --front front.png [--back back.png] [--left l.png] [--right r.png]

Runs in the engine venv (setup.sh). For each view it writes <name>.png: 1024x1024 RGBA, the
character cropped to its alpha bounds with a small margin, centred, feet at the same height in
every view. Background removal is BiRefNet (MIT), or the image's own alpha when it already has a
real one (a generator that exports transparent PNGs). Also writes views.json with each view's
silhouette bounds, which rig_character.py uses to line the side/back views up with the mesh.

Prints a pose check for the front view: AI meshes rig cleanly only from a neutral A- or T-pose
with the arms clear of the torso and the legs apart.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

BIREFNET = "ZhengPeng7/BiRefNet"
BIREFNET_REV = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"
SIZE = 1024
MARGIN = 0.06

_model = None


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def remove_bg(img):
    """RGB(A) PIL -> RGBA PIL with BiRefNet's matte as alpha."""
    global _model
    import torch
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation
    if _model is None:
        _model = AutoModelForImageSegmentation.from_pretrained(
            BIREFNET, revision=BIREFNET_REV, trust_remote_code=True).float().eval().to(_device())  # weights ship fp16
    tf = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    rgb = img.convert("RGB")
    x = tf(rgb).unsqueeze(0).to(_device())
    with torch.no_grad():
        pred = _model(x)[-1].sigmoid().float().cpu()[0, 0]
    mask = Image.fromarray((pred.numpy() * 255).astype(np.uint8)).resize(rgb.size, Image.LANCZOS)
    out = rgb.copy()
    out.putalpha(mask)
    return out


def has_real_alpha(img):
    if img.mode != "RGBA":
        return False
    a = np.asarray(img)[..., 3]
    return (a < 250).mean() > 0.05  # >5% transparent: a genuine cut-out, not an opaque RGBA


def frame(rgba):
    """Crop to alpha bounds, pad to a square with MARGIN, resize to SIZE. Returns (img, bounds)."""
    a = np.asarray(rgba)[..., 3]
    ys, xs = np.nonzero(a > 127)
    if len(xs) == 0:
        raise ValueError("background removal left nothing; is the character on a plain backdrop?")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = rgba.crop((x0, y0, x1, y1))
    w, h = crop.size
    side = int(max(w, h) * (1 + 2 * MARGIN))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    # centre horizontally; feet on a common baseline (bottom margin) so views line up
    ox = (side - w) // 2
    oy = side - h - int(max(w, h) * MARGIN)
    canvas.paste(crop, (ox, oy))
    s = SIZE / side
    bounds = {"x0": ox * s, "x1": (ox + w) * s, "y0": oy * s, "y1": (oy + h) * s, "size": SIZE,
              "aspect": w / h}
    return canvas.resize((SIZE, SIZE), Image.LANCZOS), bounds


def bleed(rgba):
    """Push-pull fill: carry the character's colours outward into the transparent background so a
    texture lookup that lands a pixel outside the silhouette picks up the nearest edge colour,
    not the backdrop (which shows as white specks on the model). Alpha is kept as is."""
    arr = np.asarray(rgba).astype(np.float32) / 255.0
    a = (arr[..., 3:4] > 0.5).astype(np.float32)
    c = arr[..., :3] * a
    levels = []
    C, Acc = c, a
    while C.shape[0] > 1 and C.shape[0] % 2 == 0 and C.shape[1] % 2 == 0:
        levels.append((C, Acc))
        h, w = C.shape[:2]
        C = C.reshape(h // 2, 2, w // 2, 2, 3).sum((1, 3))
        Acc = Acc.reshape(h // 2, 2, w // 2, 2, 1).sum((1, 3))
    fill = C / np.maximum(Acc, 1e-6)
    for C, Acc in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
        fill = np.where(Acc > 0, C / np.maximum(Acc, 1e-6), up)
    out = np.concatenate([fill, arr[..., 3:4]], -1)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def runs(row):
    """Number of solid runs in a boolean row, ignoring specks under 1% of the width."""
    n, i, L, minw = 0, 0, len(row), max(2, len(row) // 100)
    while i < L:
        if row[i]:
            j = i
            while j < L and row[j]:
                j += 1
            if j - i >= minw:
                n += 1
            i = j
        else:
            i += 1
    return n


def pose_check(rgba, bounds):
    a = np.asarray(rgba)[..., 3] > 127
    y0, y1 = int(bounds["y0"]), int(bounds["y1"])
    h = y1 - y0
    rows = lambda f0, f1: [runs(a[y]) for y in range(y0 + int(h * f0), y0 + int(h * f1))]
    torso = rows(0.30, 0.50)        # arm level, below the shoulders
    legs = rows(0.62, 0.90)         # thighs to shins
    arms_clear = np.mean([r >= 3 for r in torso]) > 0.3
    t_pose = not arms_clear and bounds["aspect"] > 0.85
    legs_apart = np.mean([r >= 2 for r in legs]) > 0.5
    notes = []
    if not (arms_clear or t_pose):
        notes.append("arms look pressed to the torso: ask for an A-pose (arms ~30-45 deg out) or a T-pose")
    if not legs_apart:
        notes.append("legs look joined (or a long skirt/robe): leg weights will be poor; ask for feet shoulder-width apart")
    pose = "T-pose" if t_pose else ("A-pose" if arms_clear else "unclear")
    return {"pose": pose, "arms_clear": bool(arms_clear or t_pose), "legs_apart": bool(legs_apart),
            "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--front", required=True)
    for v in ("back", "left", "right"):
        ap.add_argument(f"--{v}")
    ap.add_argument("--force-matte", action="store_true", help="run BiRefNet even on RGBA inputs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    meta = {}
    for name in ("front", "back", "left", "right"):
        src = getattr(args, name)
        if not src:
            continue
        img = Image.open(src)
        img.load()
        if has_real_alpha(img) and not args.force_matte:
            rgba, how = img.convert("RGBA"), "own alpha"
        else:
            rgba, how = remove_bg(img), "BiRefNet"
        framed, bounds = frame(rgba)
        path = os.path.join(args.out, f"{name}.png")
        framed.save(path)
        tex = os.path.join(args.out, f"{name}_tex.png")
        bleed(framed).save(tex)   # colour-bled copy for texture projection only
        meta[name] = {"src": os.path.abspath(src), "path": os.path.abspath(path),
                      "tex": os.path.abspath(tex), "matte": how, **bounds}
        print(f"[prep] {name}: {path} ({how})", flush=True)
    meta["front"]["check"] = pose_check(Image.open(meta["front"]["path"]), meta["front"])
    c = meta["front"]["check"]
    print(f"[prep] front pose: {c['pose']}", flush=True)
    for n in c["notes"]:
        print(f"[prep] warning: {n}", flush=True)
    with open(os.path.join(args.out, "views.json"), "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
