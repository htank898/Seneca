"""Background knockout shared by ellipses.py (fit/trace/generate --source) and pod_export.py (image input).

Removes a plain background: pixels near the key colour that connect to the image border. White eyes or
highlights inside the subject survive because they don't touch the border.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import shapes as S


def key_colour(src):
    """Median of the four 8x8 corners, as an RGB float array 0..1."""
    rgb = np.asarray(src.convert("RGB"), np.float32) / 255
    corners = np.concatenate([rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3),
                              rgb[-8:, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)])
    return np.median(corners, 0)


def subject_mask(src, knockout, tol, has_alpha):
    """Full-ish resolution (<=2048) subject mask, float 0..1, or None."""
    m = src.copy()
    m.thumbnail((2048, 2048), Image.LANCZOS)
    if has_alpha:
        return m.getchannel("A")
    if knockout == "none":
        return None
    rgb = np.asarray(m.convert("RGB"), np.float32) / 255
    if knockout == "auto":
        corners = np.concatenate([rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3),
                                  rgb[-8:, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)])
        key = np.median(corners, 0)
    else:
        key = np.array(S.hex_to_rgb(knockout), np.float32) / 255
    near = (np.sqrt(((rgb - key) ** 2).sum(-1) / 3) <= tol).astype(np.uint8) * 255
    b = Image.fromarray(near).copy()  # .copy(): floodfill is a silent no-op on a read-only array-backed image
    # background = key-coloured pixels connected to the border, so white eyes or highlights inside the subject survive
    W, H = b.size
    step = 24
    seeds = [(x, 0) for x in range(0, W, step)] + [(x, H - 1) for x in range(0, W, step)] + \
            [(0, y) for y in range(0, H, step)] + [(W - 1, y) for y in range(0, H, step)]
    for p in seeds:
        if b.getpixel(p) == 255:
            ImageDraw.floodfill(b, p, 128)
    keep = (np.asarray(b) != 128).astype(np.uint8) * 255
    return Image.fromarray(keep, "L").filter(ImageFilter.GaussianBlur(1.2))


