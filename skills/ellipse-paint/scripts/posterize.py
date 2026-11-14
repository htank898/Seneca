"""Posterize-and-trace: reduce an image to a few flat colours, then trace each colour region into vector paths.

The result is screen-print / risograph flat art with hard edges at any print size. Used by `ellipses.py trace`.
"""
import io
import re

import numpy as np
from PIL import Image, ImageFilter

import shapes as S


def _lum(rgb):
    rgb = np.asarray(rgb, np.float32)
    return rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def kmeans(pixels, k, seed=1, iters=20):
    """pixels (N,3) float 0..255 -> centres (k,3). k-means++ init on a sample, Lloyd iterations."""
    rng = np.random.default_rng(seed)
    x = pixels[rng.choice(len(pixels), min(len(pixels), 60000), replace=False)]
    c = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min(((x[:, None, :] - np.array(c)[None]) ** 2).sum(-1), 1)
        c.append(x[rng.choice(len(x), p=d / d.sum())] if d.sum() > 0 else x[rng.integers(len(x))])
    c = np.array(c, np.float32)
    for _ in range(iters):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        new = np.array([x[lab == i].mean(0) if (lab == i).any() else c[i] for i in range(k)], np.float32)
        if np.abs(new - c).max() < 0.5:
            c = new
            break
        c = new
    return c


def assign(rgb, centres):
    flat = rgb.reshape(-1, 3)
    out = np.empty(len(flat), np.uint8)
    for i in range(0, len(flat), 200000):
        out[i:i + 200000] = ((flat[i:i + 200000, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
    return out.reshape(rgb.shape[:2])


def palette_map(centres, palette):
    """Recolour clusters with a palette by matching luminance rank (darkest cluster -> darkest colour)."""
    pal = np.array([S.hex_to_rgb(p) for p in palette], np.float32)
    pal = pal[np.argsort(_lum(pal))]
    order = np.argsort(_lum(centres))
    out = np.zeros_like(centres)
    for rank, ci in enumerate(order):
        j = round(rank * (len(pal) - 1) / max(1, len(order) - 1))
        out[ci] = pal[j]
    return out


_PATH = re.compile(r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"(?: transform="([^"]+)")?\s*/>')


def trace(src_rgb, keep, colors, palette=None, smooth=5, speckle=8, corner=60, seed=1):
    """src_rgb: PIL RGB at working size; keep: bool array (subject) or None.

    Returns (shapes, colours_hex, label_counts)."""
    img = src_rgb.filter(ImageFilter.MedianFilter(3))
    rgb = np.asarray(img, np.float32)
    mask = keep if keep is not None else np.ones(rgb.shape[:2], bool)
    centres = kmeans(rgb[mask], colors, seed)
    labels = assign(rgb, centres)
    if smooth > 1:
        # majority filter on the label map: kills speckle and rounds off stair-stepped region edges
        size = smooth if smooth % 2 else smooth + 1
        labels = np.asarray(Image.fromarray(labels, "L").filter(ImageFilter.ModeFilter(size)))
    final = palette_map(centres, palette) if palette else centres
    out = np.zeros(rgb.shape[:2] + (4,), np.uint8)
    out[..., :3] = np.clip(np.round(final[labels]), 0, 255).astype(np.uint8)
    out[..., 3] = np.where(mask, 255, 0)
    buf = io.BytesIO()
    Image.fromarray(out, "RGBA").save(buf, "PNG")
    import vtracer
    svg = vtracer.convert_raw_image_to_svg(
        buf.getvalue(), img_format="png", colormode="color", hierarchical="stacked", mode="spline",
        filter_speckle=int(speckle), color_precision=8, layer_difference=1, corner_threshold=int(corner),
        length_threshold=4.0, max_iterations=10, splice_threshold=45, path_precision=2)
    hexes = [S.rgb_to_hex(c) for c in final]
    pal_arr = np.array([S.hex_to_rgb(h) for h in hexes], np.float32)
    shapes = []
    for d, fill, tf in _PATH.findall(svg):
        # vtracer re-quantizes slightly; snap every fill back onto the exact poster colours
        f = np.array(S.hex_to_rgb(fill), np.float32)
        fill = hexes[int(((pal_arr - f) ** 2).sum(-1).argmin())]
        s = {"type": "path", "d": d.strip(), "fill": fill, "opacity": 1.0}
        if tf:
            s["transform"] = tf
        shapes.append(s)
    counts = np.bincount(labels[mask].ravel(), minlength=len(hexes))
    return shapes, hexes, counts
