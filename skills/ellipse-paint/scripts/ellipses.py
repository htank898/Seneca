#!/usr/bin/env python3
"""ellipses.py: paint images from shapes. The output is vector, so it prints at any size.

  fit        approximate a target image (Gemini output, photo, sketch) with N translucent ellipses (soft, painterly)
  trace      posterize a target image to a few flat colours and trace them to vector paths (hard-edged screen print)
  generate   seeded procedural art. Soft ellipse styles: bloom | field | orbits | pebbles.
             Hard-edged styles: bauhaus | truchet | packing | contours | topo (packing/contours/topo take --source)
  render     art.json -> PNG at any size (quick look; use pod_export.py for print files)
  timelapse  art.json -> MP4 of the artwork building up, shape by shape (Etsy listing video)

usage:
  python3 scripts/ellipses.py fit TARGET.png --out work/ [--shapes 2000] [--work 200] [--alpha 0.5]
          [--knockout none|auto|#ffffff] [--tol 0.12] [--seed 1]
  python3 scripts/ellipses.py trace TARGET.png --out work/ [--colors 6] [--palette riso|"#hex,..."] [--work 1600]
          [--smooth 5] [--speckle 8] [--knockout none|auto|#hex] [--tol 0.12]
  python3 scripts/ellipses.py generate --style bloom --out work/ [--aspect 2:3] [--palette terracotta|"#hex,#hex,..."]
          [--seed 7] [--count N] [--transparent] [--source IMG --knockout auto]
  python3 scripts/ellipses.py render work/art.json --out look.png [--long 2000] [--transparent]
  python3 scripts/ellipses.py timelapse work/art.json --out listing.mp4 [--seconds 10] [--fps 30] [--long 1080]
  python3 scripts/ellipses.py palettes            # list named palettes

fit/trace/generate write into --out: art.json (the artwork), art.svg, preview.png.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

_env.ensure(__file__)

import argparse  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageOps  # noqa: E402

import geometric as G  # noqa: E402
import posterize  # noqa: E402
import shapes as S  # noqa: E402

# First colour is the background.
PALETTES = {
    "terracotta": ["#f3e9dc", "#c8553d", "#f28f3b", "#588b8b", "#2d3047", "#ffd5c2"],
    "midnight":   ["#0b1320", "#1c3144", "#d00000", "#ffba08", "#3f88c5", "#f8f9fa"],
    "sage":       ["#eef0eb", "#b4c5a9", "#6b8f71", "#3d5a40", "#e8c07d", "#c97b63"],
    "riso":       ["#f6f1e7", "#ff48b0", "#0078bf", "#ffe800", "#00a95c", "#222222"],
    "ocean":      ["#e9f1f2", "#0a2342", "#2ca58d", "#84bc9c", "#f46197", "#fffdf7"],
    "mono":       ["#f5f3ee", "#111111", "#4a4a4a", "#8c8c8c", "#c9c9c9"],
    "sunset":     ["#2b1b3d", "#ff6b6b", "#feca57", "#ff9ff3", "#48dbfb", "#f8f1e4"],
}


# ------------------------------------------------------------------ outputs
def write_outputs(doc, out_dir, preview_long=1200):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    S.save(doc, out_dir / "art.json")
    transparent = doc.get("background") is None or bool(doc.get("mask"))
    (out_dir / "art.svg").write_text(S.to_svg(doc, transparent=transparent))
    k = preview_long / max(doc["w"], doc["h"])
    img = S.render(S.to_svg(doc, width=round(doc["w"] * k), height=round(doc["h"] * k), transparent=transparent))
    img.save(out_dir / "preview.png")
    return out_dir / "art.json"


# ------------------------------------------------------------------ fit
def _subject_mask(src, knockout, tol, has_alpha):
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


def cmd_fit(a):
    rng = np.random.default_rng(a.seed)
    src = ImageOps.exif_transpose(Image.open(a.target))
    has_alpha = src.mode in ("RGBA", "LA", "PA") or "transparency" in src.info
    src = src.convert("RGBA")
    W0, H0 = src.size
    s = a.work / max(W0, H0)
    w, h = max(8, round(W0 * s)), max(8, round(H0 * s))
    T = (np.asarray(src.convert("RGB").resize((w, h), Image.LANCZOS), np.float32) / 255).reshape(-1, 3)

    mask_img = _subject_mask(src, a.knockout, a.tol, has_alpha)
    if mask_img is not None:
        wgt = (np.asarray(mask_img.resize((w, h), Image.BILINEAR), np.float32) / 255 > 0.5).astype(np.float32).ravel()
        if wgt.sum() < 0.02 * wgt.size:
            sys.exit("[fit] the subject mask is almost empty; try --knockout none or a smaller --tol")
    else:
        wgt = np.ones(w * h, np.float32)

    al = float(a.alpha)
    bg = (T * wgt[:, None]).sum(0) / wgt.sum()
    C = np.tile(bg, (w * h, 1)).astype(np.float32)
    ys, xs = np.mgrid[0:h, 0:w]
    xs = (xs.ravel() + 0.5).astype(np.float32)
    ys = (ys.ravel() + 0.5).astype(np.float32)
    L = float(max(w, h))

    def feats(Tp, Cp, wp):
        D = (1 - al) * Cp - Tp
        return np.concatenate([wp[:, None] * Tp, wp[:, None] * Cp, wp[:, None] * D,
                               (wp * (D * D).sum(1))[:, None], (wp * ((Cp - Tp) ** 2).sum(1))[:, None],
                               wp[:, None]], 1).astype(np.float32)

    F = feats(T, C, wgt)
    E = wgt * ((C - T) ** 2).sum(1)

    def masks(P):
        cx, cy, rx, ry, th = (P[:, i:i + 1] for i in range(5))
        dx = xs - cx
        dy = ys - cy
        c, sn = np.cos(th), np.sin(th)
        u = (dx * c + dy * sn) / rx
        v = (dy * c - dx * sn) / ry
        return (u * u + v * v <= 1).astype(np.float32)

    def score_chunk(P):
        S_ = masks(P) @ F
        n = S_[:, 11]
        ST, SC, SD = S_[:, 0:3], S_[:, 3:6], S_[:, 6:9]
        col = np.clip((ST - (1 - al) * SC) / (al * np.maximum(n, 1e-6))[:, None], 0, 1)
        new = S_[:, 9] + 2 * al * (col * SD).sum(1) + al * al * n * (col * col).sum(1)
        d = new - S_[:, 10]
        d[n < 0.5] = np.inf
        return d, col

    threads = a.threads or max(1, (os.cpu_count() or 4) - 1)
    pool = ThreadPoolExecutor(threads)

    def score(P):
        chunks = np.array_split(P, min(threads, len(P)))
        res = list(pool.map(score_chunk, chunks))
        return np.concatenate([r[0] for r in res]), np.concatenate([r[1] for r in res])

    def random_candidates(k, progress):
        rmax = L * (0.035 + 0.42 * (1 - progress) ** 2)
        P = np.empty((k, 5), np.float32)
        # half the centres go where the error is (importance sampling), half anywhere
        half = k // 2
        p = E / E.sum() if E.sum() > 0 else None
        idx = rng.choice(w * h, size=half, p=p)
        P[:half, 0] = xs[idx] + rng.uniform(-1, 1, half)
        P[:half, 1] = ys[idx] + rng.uniform(-1, 1, half)
        P[half:, 0] = rng.uniform(0, w, k - half)
        P[half:, 1] = rng.uniform(0, h, k - half)
        P[:, 2] = np.exp(rng.uniform(math.log(0.7), math.log(rmax), k))
        P[:, 3] = P[:, 2] * np.exp(rng.uniform(math.log(0.2), math.log(1.0), k))
        P[:, 4] = rng.uniform(0, math.pi, k)
        return P

    def mutate(b, k):
        P = np.repeat(b[None], k, 0)
        r = max(b[2], b[3])
        P[:, 0] += rng.normal(0, 0.15 * r + 1, k)
        P[:, 1] += rng.normal(0, 0.15 * r + 1, k)
        P[:, 2] *= np.exp(rng.normal(0, 0.18, k))
        P[:, 3] *= np.exp(rng.normal(0, 0.18, k))
        P[:, 4] += rng.normal(0, 0.25, k)
        P[:, 2:4] = np.clip(P[:, 2:4], 0.5, L)
        return P

    meta = {"source": str(Path(a.target).resolve()), "work": a.work, "alpha": al, "seed": a.seed,
            "knockout": a.knockout if mask_img is not None else None}
    mask_uri = None
    if mask_img is not None:
        import base64
        import io
        buf = io.BytesIO()
        mask_img.save(buf, "PNG", optimize=True)
        mask_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    doc = {"version": 1, "mode": "fit", "w": w, "h": h, "background": S.rgb_to_hex(bg * 255),
           "mask": mask_uri, "shapes": [], "meta": meta}
    if mask_img is not None:
        out_px = (1 - wgt) > 0.5
        doc["backdrop"] = S.rgb_to_hex(T[out_px].mean(0) * 255) if has_alpha is False and out_px.any() else "#ffffff"

    t0 = time.time()
    wsum = float(wgt.sum())
    print(f"[fit] {w}x{h} working canvas, {a.shapes} ellipses, alpha {al}, {threads} threads", flush=True)
    stalls = 0
    i = 0
    while len(doc["shapes"]) < a.shapes and stalls < 200:
        prog = len(doc["shapes"]) / a.shapes
        P = random_candidates(a.candidates, prog)
        d, col = score(P)
        j = int(np.argmin(d))
        best, bd, bc = P[j].copy(), d[j], col[j]
        for _ in range(a.rounds):
            Q = mutate(best, a.mutations)
            dq, cq = score(Q)
            jq = int(np.argmin(dq))
            if dq[jq] < bd:
                best, bd, bc = Q[jq].copy(), dq[jq], cq[jq]
        i += 1
        if not np.isfinite(bd) or bd >= 0:
            stalls += 1
            continue
        stalls = 0
        m = masks(best[None])[0].astype(bool)
        C[m] = C[m] + al * (bc - C[m])
        F[m] = feats(T[m], C[m], wgt[m])
        E[m] = wgt[m] * ((C[m] - T[m]) ** 2).sum(1)
        doc["shapes"].append({"cx": float(best[0]), "cy": float(best[1]), "rx": float(best[2]),
                              "ry": float(best[3]), "angle": float(math.degrees(best[4]) % 180),
                              "fill": S.rgb_to_hex(bc * 255), "opacity": al})
        n = len(doc["shapes"])
        if n % 100 == 0 or n == a.shapes:
            rms = math.sqrt(E.sum() / wsum / 3) * 255
            print(f"[fit] {n}/{a.shapes} shapes  rms {rms:.1f}  {time.time() - t0:.0f}s", flush=True)
        if a.checkpoint and n % a.checkpoint == 0:
            doc["meta"]["rms"] = math.sqrt(E.sum() / wsum / 3) * 255
            write_outputs(doc, a.out)
    pool.shutdown()
    doc["meta"]["rms"] = round(math.sqrt(E.sum() / wsum / 3) * 255, 2)
    doc["meta"]["seconds"] = round(time.time() - t0, 1)
    p = write_outputs(doc, a.out)
    print(f"[fit] done: {len(doc['shapes'])} ellipses, rms {doc['meta']['rms']} (0-255), "
          f"{doc['meta']['seconds']}s -> {p}")


# ------------------------------------------------------------------ generate
def _palette(spec):
    if spec in PALETTES:
        return PALETTES[spec]
    cols = [c.strip() for c in spec.split(",") if c.strip()]
    if len(cols) < 2:
        sys.exit(f"[generate] palette needs a name ({', '.join(PALETTES)}) or 2+ comma-separated hex colours")
    return cols


def _smooth_field(rng, w, h, waves=4, scale=1.0):
    ks = [(rng.normal(0, 2.2 * scale / w), rng.normal(0, 2.2 * scale / h), rng.uniform(0, 2 * math.pi),
           rng.uniform(0.5, 1.0)) for _ in range(waves)]
    return lambda x, y: sum(a * math.sin(kx * x * math.pi + ky * y * math.pi + ph) for kx, ky, ph, a in ks) / \
        sum(k[3] for k in ks)


def style_bloom(rng, w, h, pal, count):
    cx, cy = w / 2, h / 2
    R = min(w, h) * 0.46
    fold = int(rng.integers(6, 15))
    rings = int(count or rng.integers(8, 13))
    cols = pal[1:]
    out = []
    # soft halo discs behind the flower
    for i in range(3):
        rr = R * (1.08 - 0.12 * i)
        out.append({"cx": cx, "cy": cy, "rx": rr, "ry": rr, "angle": 0, "fill": cols[i % len(cols)], "opacity": 0.12})
    for i in range(rings, 0, -1):
        t = i / rings
        r = R * t * 0.82
        petals = fold * (2 if i > rings * 0.5 else 1)
        pl = R / rings * rng.uniform(1.4, 2.4)
        pw = pl * rng.uniform(0.22, 0.55)
        off = (math.pi / petals) * (i % 2)
        col = cols[i % len(cols)]
        for k in range(petals):
            ang = 2 * math.pi * k / petals + off
            out.append({"cx": cx + r * math.cos(ang), "cy": cy + r * math.sin(ang), "rx": pl, "ry": pw,
                        "angle": math.degrees(ang) % 180, "fill": col, "opacity": 0.85})
            if i % 3 == 0:  # fine stroke echo on every third ring
                out.append({"cx": cx + r * math.cos(ang), "cy": cy + r * math.sin(ang), "rx": pl * 0.6,
                            "ry": pw * 0.45, "angle": math.degrees(ang) % 180, "fill": None, "opacity": 0.9,
                            "stroke": cols[(i + 2) % len(cols)], "strokeWidth": max(0.6, R * 0.004)})
    for j, f in enumerate((0.09, 0.055, 0.025)):
        out.append({"cx": cx, "cy": cy, "rx": R * f, "ry": R * f, "angle": 0, "fill": cols[(j + 1) % len(cols)],
                    "opacity": 0.95})
    return out


def style_field(rng, w, h, pal, count):
    n = int(count or 1600)
    ang = _smooth_field(rng, w, h, 4, 1.0)
    size = _smooth_field(rng, w, h, 3, 0.7)
    hue = _smooth_field(rng, w, h, 3, 0.8)
    cols = pal[1:]
    base = math.sqrt(w * h / n)
    pts = []
    for _ in range(n):
        x, y = rng.uniform(-0.03 * w, 1.03 * w), rng.uniform(-0.03 * h, 1.03 * h)
        s = base * (0.35 + 0.75 * (size(x, y) + 1) / 2) * rng.uniform(0.7, 1.15)
        pts.append((s, x, y))
    pts.sort(reverse=True)  # big first, detail on top
    out = []
    for s, x, y in pts:
        ci = int(((hue(x, y) + 1) / 2 * len(cols) + rng.normal(0, 0.35))) % len(cols)
        out.append({"cx": x, "cy": y, "rx": s, "ry": s * rng.uniform(0.22, 0.5),
                    "angle": math.degrees(ang(x, y) * math.pi) % 180, "fill": cols[ci], "opacity": 0.9})
    return out


def style_orbits(rng, w, h, pal, count):
    n = int(count or 64)

    def lum(c):
        r, g, b = (v / 255 for v in S.hex_to_rgb(c))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    # the two stroke colours that stand out most against the background
    cols = sorted(pal[1:], key=lambda c: -abs(lum(c) - lum(pal[0])))[:2]
    R = math.hypot(w, h) * 0.55
    out = []
    for fam in range(2):
        cx = w / 2 + (fam - 0.5) * w * rng.uniform(0.08, 0.18)
        cy = h / 2 + rng.normal(0, h * 0.05)
        ecc = rng.uniform(0.55, 0.85)
        a0 = rng.uniform(0, 180)
        twist = rng.uniform(-0.6, 0.6)
        col = cols[fam % len(cols)]
        step = R / n
        for i in range(1, n + 1):
            r = step * i
            out.append({"cx": cx, "cy": cy, "rx": r, "ry": r * ecc, "angle": (a0 + twist * i) % 180,
                        "fill": None, "opacity": 0.85, "stroke": col, "strokeWidth": step * 0.42})
    return out


def style_pebbles(rng, w, h, pal, count):
    target = int(count or 900)
    cols = pal[1:]
    gap = min(w, h) * 0.004
    placed = np.zeros((0, 3), np.float32)  # x, y, bounding radius
    out = []
    rmax, rmin = min(w, h) * 0.16, min(w, h) * 0.008
    attempts = 0
    while len(out) < target and attempts < target * 60:
        attempts += 1
        prog = min(1.0, attempts / (target * 25))
        r = rmax * (1 - prog) ** 2.2 + rmin
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        if len(placed):
            d = np.hypot(placed[:, 0] - x, placed[:, 1] - y) - placed[:, 2]
            room = float(d.min()) - gap
            if room < rmin:
                continue
            r = min(r, room)
        ry = r * rng.uniform(0.72, 1.0)
        out.append({"cx": x, "cy": y, "rx": r, "ry": ry, "angle": float(rng.uniform(0, 180)),
                    "fill": cols[int(rng.integers(len(cols)))], "opacity": 1.0})
        placed = np.vstack([placed, [[x, y, r]]]).astype(np.float32)
    return out


SOFT_STYLES = {"bloom": style_bloom, "field": style_field, "orbits": style_orbits, "pebbles": style_pebbles}
STYLES = {**SOFT_STYLES, **G.STYLES}
PAPER = "#f5f1e8"  # default background when a --source sets the colours


def _load_source(path, knockout, tol, long_side=1000):
    """-> (w, h in art units, Source at 1 px per art unit, backdrop hex for cut-outs or None)."""
    src = ImageOps.exif_transpose(Image.open(path))
    has_alpha = src.mode in ("RGBA", "LA", "PA") or "transparency" in src.info
    src = src.convert("RGBA")
    W0, H0 = src.size
    k = long_side / max(W0, H0)
    w, h = max(8, round(W0 * k)), max(8, round(H0 * k))
    rgb = np.asarray(src.convert("RGB").resize((w, h), Image.LANCZOS), np.float32)
    mask_img = _subject_mask(src, knockout, tol, has_alpha)
    keep, backdrop = None, None
    if mask_img is not None:
        keep = np.asarray(mask_img.resize((w, h), Image.BILINEAR)) > 127
        if keep.mean() < 0.02:
            sys.exit("[source] the subject mask is almost empty; try --knockout none or a smaller --tol")
        backdrop = "#ffffff" if has_alpha or not (~keep).any() else S.rgb_to_hex(rgb[~keep].mean(0))
    return w, h, G.Source(rgb, keep), backdrop


def cmd_generate(a):
    rng = np.random.default_rng(a.seed)
    src, backdrop = None, None
    if a.source:
        if a.style not in G.SOURCE_STYLES:
            sys.exit(f"[generate] --source works with {', '.join(sorted(G.SOURCE_STYLES))}")
        if a.style == "topo" and a.knockout != "none":
            sys.exit("[generate] topo bands get stair-stepped edges on a cut-out; for a flat-colour cut-out use\n"
                     "           `trace TARGET --knockout auto --colors 5 --palette ...` (topo --source works full-frame)")
        w, h, src, backdrop = _load_source(a.source, a.knockout, a.tol)
        pal = _palette(a.palette) if a.palette else [PAPER, "#1b1b1b", "#c8553d", "#2d3047"]
    else:
        pal = _palette(a.palette or "terracotta")
        rw, rh = (float(x) for x in a.aspect.split(":"))
        w, h = (1000.0, 1000.0 * rh / rw) if rw <= rh else (1000.0 * rw / rh, 1000.0)
    fn = STYLES[a.style]
    if a.style == "packing":
        shapes = fn(rng, w, h, pal, a.count, src, snap=bool(a.palette))
    elif a.style in G.STYLES:
        shapes = fn(rng, w, h, pal, a.count, src)
    else:
        shapes = fn(rng, w, h, pal, a.count)
    cut = src is not None and src.keep is not None
    if a.transparent:
        # garments and stickers: no see-through shapes (DTG dithers partial alpha); drop faint glazes entirely
        shapes = [dict(s, opacity=1.0) for s in shapes if s.get("opacity", 1) >= 0.3]
    doc = {"version": 1, "mode": "generate", "w": round(w, 2), "h": round(h, 2),
           "background": None if (a.transparent or cut) else pal[0], "mask": None, "shapes": shapes,
           "meta": {"style": a.style, "seed": a.seed, "palette": pal, "aspect": a.aspect, "count": a.count,
                    "source": str(Path(a.source).resolve()) if a.source else None}}
    if cut:
        doc.update(cutout=True, backdrop=backdrop if a.style != "contours" else PAPER)
    p = write_outputs(doc, a.out)
    print(f"[generate] {a.style}, seed {a.seed}, {len(shapes)} shapes -> {p}")


def cmd_trace(a):
    t0 = time.time()
    src = ImageOps.exif_transpose(Image.open(a.target))
    has_alpha = src.mode in ("RGBA", "LA", "PA") or "transparency" in src.info
    src = src.convert("RGBA")
    W0, H0 = src.size
    k = a.work / max(W0, H0)  # small sources are upscaled first: smoother traced edges
    w, h = max(8, round(W0 * k)), max(8, round(H0 * k))
    rgb_img = src.convert("RGB").resize((w, h), Image.LANCZOS)
    mask_img = _subject_mask(src, a.knockout, a.tol, has_alpha)
    keep = np.asarray(mask_img.resize((w, h), Image.BILINEAR)) > 127 if mask_img is not None else None
    pal = _palette(a.palette) if a.palette else None
    colors = a.colors or (len(pal) if pal else 6)
    shapes, hexes, counts = posterize.trace(rgb_img, keep, colors, pal, smooth=a.smooth, speckle=a.speckle,
                                            corner=a.corner, seed=a.seed)
    cut = keep is not None
    doc = {"version": 1, "mode": "trace", "w": w, "h": h,
           "background": None if cut else hexes[int(np.argmax(counts))], "mask": None, "shapes": shapes,
           "meta": {"source": str(Path(a.target).resolve()), "colors": hexes, "work": a.work, "smooth": a.smooth,
                    "speckle": a.speckle, "palette": pal, "knockout": a.knockout if cut else None}}
    if cut:
        rgb = np.asarray(rgb_img, np.float32)
        doc.update(cutout=True, backdrop="#ffffff" if has_alpha or not (~keep).any() else S.rgb_to_hex(rgb[~keep].mean(0)))
    p = write_outputs(doc, a.out)
    share = ", ".join(f"{c} {n / max(1, counts.sum()):.0%}" for c, n in sorted(zip(hexes, counts), key=lambda t: -t[1]))
    print(f"[trace] {w}x{h}, {colors} colours ({share}), {len(shapes)} paths, {time.time() - t0:.1f}s -> {p}")


# ------------------------------------------------------------------ render / timelapse
def _size(doc, long_side):
    k = long_side / max(doc["w"], doc["h"])
    return round(doc["w"] * k), round(doc["h"] * k)


def cmd_render(a):
    doc = S.load(a.doc)
    W, H = _size(doc, a.long)
    img = S.render(S.to_svg(doc, width=W, height=H, transparent=a.transparent))
    img.save(a.out)
    print(f"[render] {W}x{H} -> {a.out}")


def cmd_timelapse(a):
    doc = S.load(a.doc)
    W, H = _size(doc, a.long)
    W, H = W // 2 * 2, H // 2 * 2
    N = len(doc["shapes"])
    hold = int(a.hold * a.fps)
    build = max(2, int(a.seconds * a.fps) - hold)
    bg = S.hex_to_rgb(doc.get("backdrop") or doc.get("background") or "#ffffff")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-movflags", "+faststart", a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    last = None
    transparent = False
    for f in range(build + hold):
        t = min(1.0, f / (build - 1))
        k = N if t >= 1 else max(1, math.ceil(N * t ** a.curve))
        if k != last:
            img = S.render(S.to_svg(doc, width=W, height=H, limit=k, transparent=transparent))
            canvas = Image.new("RGB", img.size, bg)
            canvas.paste(img, mask=img.getchannel("A"))
            frame = canvas.resize((W, H)).tobytes()
            last = k
        ff.stdin.write(frame)
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("[timelapse] ffmpeg failed")
    print(f"[timelapse] {W}x{H}, {(build + hold) / a.fps:.1f}s -> {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fit")
    f.add_argument("target")
    f.add_argument("--out", required=True)
    f.add_argument("--shapes", type=int, default=2000)
    f.add_argument("--work", type=int, default=200, help="working canvas long side in px (bigger = slower, finer)")
    f.add_argument("--alpha", type=float, default=0.5)
    f.add_argument("--candidates", type=int, default=128)
    f.add_argument("--rounds", type=int, default=6)
    f.add_argument("--mutations", type=int, default=64)
    f.add_argument("--knockout", default="none", help="none | auto (corner colour) | #hex: cut out a plain background")
    f.add_argument("--tol", type=float, default=0.12)
    f.add_argument("--seed", type=int, default=1)
    f.add_argument("--checkpoint", type=int, default=500)
    f.add_argument("--threads", type=int, default=0)

    g = sub.add_parser("generate")
    g.add_argument("--style", choices=sorted(STYLES), required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--aspect", default="2:3")
    g.add_argument("--palette", help="name or #hex list; default terracotta, or paper+ink with --source")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--count", type=int, default=0)
    g.add_argument("--transparent", action="store_true")
    g.add_argument("--source", help="image to build from (packing, contours, topo)")
    g.add_argument("--knockout", default="none", help="with --source: none | auto | #hex")
    g.add_argument("--tol", type=float, default=0.12)

    tr = sub.add_parser("trace")
    tr.add_argument("target")
    tr.add_argument("--out", required=True)
    tr.add_argument("--colors", type=int, default=0, help="flat colours (default 6, or the palette size)")
    tr.add_argument("--palette", help="recolour by tone: darkest region gets the darkest palette colour")
    tr.add_argument("--work", type=int, default=1600, help="tracing resolution, long side px")
    tr.add_argument("--smooth", type=int, default=5, help="majority-filter size: higher = simpler, rounder regions")
    tr.add_argument("--speckle", type=int, default=8, help="drop regions smaller than this many px")
    tr.add_argument("--corner", type=int, default=60, help="corner threshold in degrees (lower = more corners)")
    tr.add_argument("--knockout", default="none", help="none | auto | #hex: cut out a plain background")
    tr.add_argument("--tol", type=float, default=0.12)
    tr.add_argument("--seed", type=int, default=1)

    r = sub.add_parser("render")
    r.add_argument("doc")
    r.add_argument("--out", required=True)
    r.add_argument("--long", type=int, default=2000)
    r.add_argument("--transparent", action="store_true")

    t = sub.add_parser("timelapse")
    t.add_argument("doc")
    t.add_argument("--out", required=True)
    t.add_argument("--seconds", type=float, default=10)
    t.add_argument("--fps", type=int, default=30)
    t.add_argument("--long", type=int, default=1080)
    t.add_argument("--hold", type=float, default=1.5)
    t.add_argument("--curve", type=float, default=2.4, help=">1 lingers on the early, big shapes")

    sub.add_parser("palettes")

    a = ap.parse_args()
    if a.cmd == "palettes":
        for k, v in PALETTES.items():
            print(f"{k:11s} bg {v[0]}  {' '.join(v[1:])}")
        return
    {"fit": cmd_fit, "trace": cmd_trace, "generate": cmd_generate, "render": cmd_render, "timelapse": cmd_timelapse}[a.cmd](a)


if __name__ == "__main__":
    main()
