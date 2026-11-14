"""Hard-edged generative styles: flat, opaque vector shapes that stay razor sharp at any print size.

  bauhaus   a grid of tiles, each a quarter/half circle, triangle, bars or ring, in a limited palette
  truchet   continuous curving lines from randomly rotated quarter-arc tiles (also a seamless-ish pattern)
  packing   non-overlapping solid circles; with --source, packed inside the subject and coloured from it
  contours  topographic lines from a noise landscape, or from an image's tones with --source
  topo      the same landscape as stacked filled bands (terraced map look)

Every style is style(rng, w, h, pal, count, src=None) -> list of shapes (see shapes.py). pal[0] is the background.
src, when given, is a Source: the image resized to the art's coordinates plus an optional subject mask.
"""
import math

import numpy as np

import shapes as S


def _f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _lum(c):
    r, g, b = (v / 255 for v in S.hex_to_rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_order(pal):
    return sorted(pal[1:], key=lambda c: -abs(_lum(c) - _lum(pal[0])))


class Source:
    """An image in art coordinates: rgb (h, w, 3) 0..255 at 1 px per art unit, keep (h, w) bool or None."""

    def __init__(self, rgb, keep):
        self.rgb = rgb.astype(np.float32)
        self.keep = keep
        self.h, self.w = rgb.shape[:2]

    def _ij(self, x, y):
        return (np.clip(np.asarray(y, int), 0, self.h - 1), np.clip(np.asarray(x, int), 0, self.w - 1))

    def color(self, x, y):
        i, j = self._ij(x, y)
        return self.rgb[i, j]

    def inside(self, x, y):
        if self.keep is None:
            return np.ones(np.shape(x), bool)
        i, j = self._ij(x, y)
        return self.keep[i, j]


def _snap(rgb, pal_rgb):
    return pal_rgb[int(((pal_rgb - rgb) ** 2).sum(-1).argmin())]


# ------------------------------------------------------------------ bauhaus
def style_bauhaus(rng, w, h, pal, count, src=None):
    bg, cols = pal[0], pal[1:]
    n = int(count or rng.integers(4, 7))
    m = min(w, h) * 0.07
    c = (w - 2 * m) / n
    rows = max(1, int((h - 2 * m) // c))
    gx, gy = m, (h - rows * c) / 2
    out = []
    motifs = ["quarter", "quarter", "half", "half", "circle", "triangle", "bars", "ring", "quarters", "blank"]
    for r in range(rows):
        for q in range(n):
            x, y = gx + q * c, gy + r * c
            cbg = cols[int(rng.integers(len(cols)))] if rng.random() < 0.8 else bg
            fg = rng.choice([k for k in cols + [bg] if k != cbg])
            alt = rng.choice([k for k in cols + [bg] if k not in (cbg, fg)] or [bg])
            # a hair of overlap so neighbouring tiles never show an anti-aliased seam
            out.append({"type": "rect", "x": x - 0.3, "y": y - 0.3, "w": c + 0.6, "h": c + 0.6, "fill": cbg})
            rot = f"rotate({90 * int(rng.integers(4))} {_f(x + c / 2)} {_f(y + c / 2)})"
            kind = motifs[int(rng.integers(len(motifs)))]
            P = lambda d, fill, tf=rot: {"type": "path", "d": d, "fill": fill, "transform": tf}  # noqa: E731
            if kind == "quarter":
                out.append(P(f"M{_f(x)} {_f(y)}L{_f(x + c)} {_f(y)}A{_f(c)} {_f(c)} 0 0 1 {_f(x)} {_f(y + c)}Z", fg))
            elif kind == "quarters":
                for k, col in ((1.0, fg), (0.5, alt)):
                    rr = c * k
                    out.append(P(f"M{_f(x)} {_f(y)}L{_f(x + rr)} {_f(y)}A{_f(rr)} {_f(rr)} 0 0 1 {_f(x)} {_f(y + rr)}Z",
                                 col))
            elif kind == "half":
                out.append(P(f"M{_f(x)} {_f(y)}L{_f(x + c)} {_f(y)}A{_f(c / 2)} {_f(c / 2)} 0 0 1 {_f(x)} {_f(y)}Z",
                             fg))
                if rng.random() < 0.5:  # a second half facing it
                    out.append(P(f"M{_f(x + c)} {_f(y + c)}L{_f(x)} {_f(y + c)}A{_f(c / 2)} {_f(c / 2)} 0 0 1 "
                                 f"{_f(x + c)} {_f(y + c)}Z", alt))
            elif kind == "circle":
                out.append({"type": "circle", "cx": x + c / 2, "cy": y + c / 2, "r": c * rng.choice([0.32, 0.42, 0.5]),
                            "fill": fg})
            elif kind == "ring":
                out.append({"type": "circle", "cx": x + c / 2, "cy": y + c / 2, "r": c * 0.42, "fill": fg})
                out.append({"type": "circle", "cx": x + c / 2, "cy": y + c / 2, "r": c * 0.2, "fill": alt})
            elif kind == "triangle":
                out.append(P(f"M{_f(x)} {_f(y)}L{_f(x + c)} {_f(y)}L{_f(x)} {_f(y + c)}Z", fg))
            elif kind == "bars":
                bw = c / 7
                out.append(P("".join(f"M{_f(x + k * bw)} {_f(y)}h{_f(bw)}v{_f(c)}h{_f(-bw)}Z" for k in (1, 3, 5)), fg))
    return out


# ------------------------------------------------------------------ truchet
def style_truchet(rng, w, h, pal, count, src=None):
    n = int(count or rng.integers(6, 12))
    t = w / n
    rows = math.ceil(h / t)
    oy = (h - rows * t) / 2
    ink = _contrast_order(pal)
    a, b = ink[0], (ink[1] if len(ink) > 1 else ink[0])
    r = t / 2
    variant = rng.choice(["solid", "tube", "two"])
    layers = {"solid": [(a, 0.34)], "tube": [(a, 0.42), (pal[0], 0.22), (a, 0.06)], "two": [(a, 0.4), (b, 0.16)]}[variant]
    tiles = [(q * t, oy + k * t, int(rng.integers(2))) for k in range(rows) for q in range(n)]
    out = []
    for col, wf in layers:
        for x, y, o in tiles:
            d = (f"M{_f(x + r)} {_f(y)}A{_f(r)} {_f(r)} 0 0 1 {_f(x)} {_f(y + r)}"
                 f"M{_f(x + t)} {_f(y + r)}A{_f(r)} {_f(r)} 0 0 0 {_f(x + r)} {_f(y + t)}")
            s = {"type": "path", "d": d, "fill": None, "stroke": col, "strokeWidth": t * wf}
            if o:
                s["transform"] = f"rotate(90 {_f(x + r)} {_f(y + r)})"
            out.append(s)
    return out


# ------------------------------------------------------------------ packing
def style_packing(rng, w, h, pal, count, src=None, snap=False):
    target = int(count or (2500 if src is not None else 1100))
    cols = pal[1:]
    pal_rgb = np.array([S.hex_to_rgb(p) for p in pal], np.float32)
    gap = min(w, h) * 0.0035
    rmax, rmin = min(w, h) * (0.09 if src is not None else 0.14), min(w, h) * 0.006
    placed = np.zeros((0, 3), np.float32)
    out = []
    ring = np.linspace(0, 2 * math.pi, 12, endpoint=False)
    if src is not None:
        rmin = min(w, h) * 0.004
        iy, ix = np.nonzero(src.keep) if src.keep is not None else np.mgrid[0:src.h, 0:src.w].reshape(2, -1)
    attempts = 0
    budget = target * (200 if src is not None else 80)
    while len(out) < target and attempts < budget:
        attempts += 1
        prog = min(1.0, attempts / (budget * 0.4))
        r = rmax * (1 - prog) ** 2 + rmin
        if src is not None:  # centres drawn from subject pixels only
            k = int(rng.integers(len(ix)))
            x, y = ix[k] + rng.uniform(0, 1), iy[k] + rng.uniform(0, 1)
        else:
            x, y = rng.uniform(0, w), rng.uniform(0, h)
        if len(placed):
            d = np.hypot(placed[:, 0] - x, placed[:, 1] - y) - placed[:, 2]
            room = float(d.min()) - gap
            if room < rmin:
                continue
            r = min(r, room)
        if src is not None:
            # shrink until the circle sits inside the subject and over one roughly flat colour region,
            # so detail (edges, eyes) gets small circles and flat areas get big ones
            while r >= rmin:
                px, py = x + 0.9 * r * np.cos(ring), y + 0.9 * r * np.sin(ring)
                cs = src.color(np.append(px, x), np.append(py, y))
                if src.inside(px, py).all() and np.abs(cs - cs.mean(0)).max() < 60:
                    break
                r *= 0.75
            if r < rmin:
                continue
            rgb = cs.mean(0)
            fill = S.rgb_to_hex(_snap(rgb, pal_rgb[1:]) if snap else rgb)
        else:
            fill = cols[int(rng.integers(len(cols)))]
        out.append({"type": "circle", "cx": x, "cy": y, "r": r, "fill": fill})
        placed = np.vstack([placed, [[x, y, r]]]).astype(np.float32)
    return out


# ------------------------------------------------------------------ contours / topo
def _landscape(rng, w, h, src):
    gw = 700
    k = gw / max(w, h)
    nx, ny = max(8, round(w * k)), max(8, round(h * k))
    xs, ys = np.linspace(0, w, nx), np.linspace(0, h, ny)
    X, Y = np.meshgrid(xs, ys)
    if src is not None:
        from PIL import Image
        lum = (src.rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)).astype(np.float32)
        rad = max(2.0, nx * 0.01)  # tones, not skin/fabric texture

        kx = np.arange(-int(3 * rad), int(3 * rad) + 1)
        g = np.exp(-kx ** 2 / (2 * rad * rad))
        g /= g.sum()

        def blur(arr):  # separable gaussian in float (PIL's blur is 8-bit only)
            im = Image.fromarray(arr.astype(np.float32), "F").resize((nx, ny), Image.BILINEAR)
            a = np.asarray(im, np.float32)
            a = np.apply_along_axis(lambda r: np.convolve(np.pad(r, len(g) // 2, mode="edge"), g, "valid"), 1, a)
            return np.apply_along_axis(lambda c: np.convolve(np.pad(c, len(g) // 2, mode="edge"), g, "valid"), 0, a)
        if src.keep is None:
            return xs, ys, 255 - blur(lum)  # dark = high ground, so shadows get dense lines
        k = src.keep.astype(np.float32)
        keep = np.asarray(Image.fromarray(k * 255, "F").resize((nx, ny), Image.BILINEAR), np.float32) / 255
        # normalized blur: average only subject pixels, so the background never bleeds a gradient into the edge
        Z = 255 - blur(lum * k) / np.maximum(blur(k), 1e-3)
        Z = np.ma.masked_where(keep < 0.5, Z)  # no lines outside the subject
        Z.keep = keep
        return xs, ys, Z
    Z = np.zeros_like(X)
    L = max(w, h)
    for _ in range(int(rng.integers(9, 16))):
        cx, cy = rng.uniform(-0.1 * w, 1.1 * w), rng.uniform(-0.1 * h, 1.1 * h)
        s = L * rng.uniform(0.08, 0.3)
        Z += rng.uniform(-0.6, 1.0) * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * s * s))
    for _ in range(4):
        kx, ky, ph = rng.normal(0, 7 / L), rng.normal(0, 7 / L), rng.uniform(0, 2 * math.pi)
        Z += 0.08 * np.sin(kx * X + ky * Y + ph)
    return xs, ys, Z


def _levels(Z, n, src):
    vals = Z.compressed() if np.ma.isMaskedArray(Z) else Z.ravel()
    lo, hi = np.percentile(vals, [2 if src is None else 8, 98])
    return np.linspace(lo, hi, n + 2)[1:-1]


def _poly_d(pts, close):
    pts = pts[np.r_[True, np.hypot(*np.diff(pts, axis=0).T) > 0.4]]
    if len(pts) < 3:
        return ""
    return "M" + "L".join(f"{_f(px)} {_f(py)}" for px, py in pts) + ("Z" if close else "")


def style_contours(rng, w, h, pal, count, src=None):
    import contourpy
    xs, ys, Z = _landscape(rng, w, h, src)
    levels = _levels(Z, int(count or (22 if src is not None else 26)), src)
    gen = contourpy.contour_generator(xs, ys, Z, line_type=contourpy.LineType.Separate)
    ink = _contrast_order(pal)
    mono = src is not None or rng.random() < 0.5
    sw = min(w, h) * (0.0026 if src is not None else 0.0034)
    out = []
    for i, lv in enumerate(levels):
        col = ink[0] if mono else pal[1:][i * len(pal[1:]) // len(levels)]
        heavy = (i % 5 == 4)  # every fifth line is an index contour, like a survey map
        for line in gen.lines(lv):
            closed = np.allclose(line[0], line[-1])
            d = _poly_d(line, closed)
            if d:
                out.append({"type": "path", "d": d, "fill": None, "stroke": col,
                            "strokeWidth": sw * (2.0 if heavy else 1.0), "cap": "round"})
    if np.ma.isMaskedArray(Z) and hasattr(Z, "keep"):  # one clean silhouette line around a cut-out subject
        sil = contourpy.contour_generator(xs, ys, Z.keep, line_type=contourpy.LineType.Separate).lines(0.5)
        for line in sil:
            d = _poly_d(line, np.allclose(line[0], line[-1]))
            if d:
                out.append({"type": "path", "d": d, "fill": None, "stroke": ink[0], "strokeWidth": sw * 2.4,
                            "cap": "round"})
    return out


def style_topo(rng, w, h, pal, count, src=None):
    import contourpy
    xs, ys, Z = _landscape(rng, w, h, src)
    levels = _levels(Z, int(count or 9), src)
    gen = contourpy.contour_generator(xs, ys, Z, fill_type=contourpy.FillType.OuterOffset)
    cols = sorted(pal[1:], key=_lum, reverse=_lum(pal[0]) >= 0.5)  # low ground blends with the background
    top = float(Z.max()) + 1
    out = []
    for i, lv in enumerate(levels):
        col = cols[min(len(cols) - 1, i * len(cols) // len(levels))]
        polys, offsets = gen.filled(lv, top)
        for pts, off in zip(polys, offsets):
            d = "".join(_poly_d(pts[off[k]:off[k + 1]], True) for k in range(len(off) - 1))
            if d:
                out.append({"type": "path", "d": d, "fill": col, "evenodd": True})
    return out


STYLES = {"bauhaus": style_bauhaus, "truchet": style_truchet, "packing": style_packing,
          "contours": style_contours, "topo": style_topo}
SOURCE_STYLES = {"packing", "contours", "topo"}
