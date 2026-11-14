#!/usr/bin/env python3
"""pod_export.py: turn an art.json (from ellipses.py) into print-on-demand files at 300 DPI.

usage:
  python3 scripts/pod_export.py work/art.json --out print/ --preset wall-art [--preset tee ...]
          [--name moth-bloom] [--focus 0.5,0.4] [--margin 0.04] [--keep-background] [--flatten-alpha]
  python3 scripts/pod_export.py work/art.json --out print/ --size 3000x3000 --fit cover
  python3 scripts/pod_export.py concept.png --out print/ --preset all      # an image (e.g. Gemini) directly:
          [--knockout auto|none|#hex] [--upscale auto|off] [--upscale-model anime|general]
  python3 scripts/pod_export.py --install-upscaler                          # one-time Real-ESRGAN download
  python3 scripts/pod_export.py --list

Presets are single products (poster-2x3, tee, mug-11oz, sticker-4in, ...) or sets (wall-art, apparel,
mug, stickers, all). Writes <name>-<preset>.(png|jpg) with 300 DPI metadata, and export.json listing
every file, its pixel size, MB, and any warnings (dark-fabric visibility, semi-transparency, file size).
Image input (.png/.jpg/.webp) cuts out a plain background, upscales with Real-ESRGAN only as far as the largest
product needs, and reports each file's detail DPI (real pixels per printed inch).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

_env.ensure(__file__)

import argparse  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

import shapes as S  # noqa: E402
import raster_export as R  # noqa: E402

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

Image.MAX_IMAGE_PIXELS = None  # print files are legitimately huge

DPI = 300
ETSY_DIGITAL_MAX_MB = 20  # Etsy: up to 5 files per digital listing, 20 MB each

# name: (w, h, fit, kind, note). fit: cover = fill and crop, contain = whole art inside a margin.
PRESETS = {
    "poster-2x3":   (7200, 10800, "cover", "wall", "24x36 in; scales to 4x6, 8x12, 12x18, 16x24, 20x30"),
    "poster-3x4":   (5400, 7200, "cover", "wall", "18x24 in; scales to 6x8, 9x12, 12x16"),
    "poster-4x5":   (4800, 6000, "cover", "wall", "16x20 in; scales to 8x10, 4x5"),
    "poster-11x14": (3300, 4200, "cover", "wall", "11x14 in"),
    "poster-iso":   (7016, 9933, "cover", "wall", "A1; scales to A2-A5"),
    "tee":          (4500, 5400, "contain", "apparel", "15x18 in front print, transparent (Printify/Printful standard)"),
    "hoodie":       (4500, 5400, "contain", "apparel", "front print, transparent; check the provider's pocket zone"),
    "mug-11oz":     (2700, 1050, "mug", "mug", "9x3.5 in wrap; art placed on both sides of the handle"),
    "sticker-3in":  (900, 900, "contain", "sticker", "die-cut, transparent, white outline"),
    "sticker-4in":  (1200, 1200, "contain", "sticker", "die-cut, transparent, white outline"),
    "sticker-5.5in": (1650, 1650, "contain", "sticker", "die-cut, transparent, white outline"),
}
SETS = {
    "wall-art": ["poster-2x3", "poster-3x4", "poster-4x5", "poster-11x14", "poster-iso"],
    "apparel": ["tee"],
    "mug": ["mug-11oz"],
    "stickers": ["sticker-4in"],
}
SETS["all"] = SETS["wall-art"] + SETS["apparel"] + SETS["mug"] + SETS["stickers"]


def view_for(doc, W, H, fit, focus, margin):
    aw, ah = (doc["w"], doc["h"]) if isinstance(doc, dict) else (doc.w, doc.h)
    if fit == "cover":
        s = max(W / aw, H / ah)
        vw, vh = W / s, H / s
        vx = min(max(focus[0] * aw - vw / 2, 0), aw - vw)
        vy = min(max(focus[1] * ah - vh / 2, 0), ah - vh)
    else:
        s = min(W * (1 - 2 * margin) / aw, H * (1 - 2 * margin) / ah)
        vw, vh = W / s, H / s
        vx, vy = (aw - vw) / 2, (ah - vh) / 2
    return vx, vy, vw, vh


def render(doc, W, H, fit, focus, margin, transparent, backdrop=None):
    if fit == "mug":
        # the art twice, centred in each half, so it shows whichever hand holds the mug
        half = render(doc, W // 2, H, "contain", focus, margin, transparent, backdrop)
        cut = doc.get("mask") or doc.get("cutout")
        field = backdrop or (doc.get("backdrop") if cut else doc.get("background")) or "#ffffff"
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0) if transparent else S.hex_to_rgb(field) + (255,))
        out.alpha_composite(half, (0, 0))
        out.alpha_composite(half, (W - half.width, 0))
        return out
    v = view_for(doc, W, H, fit, focus, margin)
    return S.render(S.to_svg(doc, view=v, width=W, height=H, transparent=transparent, background=backdrop))


def sticker_outline(img, px):
    a = img.getchannel("A").point(lambda v: 255 if v > 127 else 0)
    # dilation by ~px: blur then a low threshold, then smooth the edge
    grown = a.filter(ImageFilter.GaussianBlur(px / 2)).point(lambda v: 255 if v > 6 else 0)
    grown = grown.filter(ImageFilter.GaussianBlur(2)).point(lambda v: 255 if v > 127 else 0)
    base = Image.new("RGBA", img.size, (255, 255, 255, 0))
    base.putalpha(grown)
    base.alpha_composite(img)
    return base


def checks(img, kind):
    warn = []
    arr = np.asarray(img, np.float32) / 255
    a = arr[..., 3]
    opaque = a > 0.5
    if kind in ("apparel", "sticker") and opaque.any():
        rgb = arr[..., :3][opaque]
        lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        dark, light = float((lum < 0.12).mean()), float((lum > 0.92).mean())
        if dark > 0.25:
            warn.append(f"{dark:.0%} of the design is near-black: it will vanish on black/navy garments")
        if light > 0.25:
            warn.append(f"{light:.0%} of the design is near-white: it will vanish on white garments")
        semi = float(((a > 0.05) & (a < 0.95)).mean() / max(opaque.mean(), 1e-6))
        if kind == "apparel" and semi > 0.15:  # stickers sit on an opaque white outline, so partial alpha is fine  # a soft anti-aliased cut-out edge alone is ~5-10%; above that the body is see-through
            warn.append(f"{semi:.0%} of the edge/body is semi-transparent: DTG printers dither this; "
                        "consider --flatten-alpha")
        if float(opaque.mean()) < 0.03:
            warn.append("the design covers under 3% of the print area")
    return warn


def save(img, path, fmt):
    if fmt == "jpg":
        rgb = Image.new("RGB", img.size, (255, 255, 255))
        rgb.paste(img, mask=img.getchannel("A"))
        for q in (95, 92, 88, 84, 80):
            buf = io.BytesIO()
            rgb.save(buf, "JPEG", quality=q, dpi=(DPI, DPI), optimize=True, subsampling=0 if q >= 92 else 2)
            if buf.tell() <= ETSY_DIGITAL_MAX_MB * 1e6:
                break
        Path(path).write_bytes(buf.getvalue())
    else:
        img.save(path, "PNG", dpi=(DPI, DPI), optimize=False, compress_level=6)
    return Path(path).stat().st_size / 1e6


def build_jobs(a):
    jobs = []
    for p in a.preset or ([] if a.size else ["wall-art"]):
        for q in SETS.get(p, [p]):
            if q not in PRESETS:
                sys.exit(f"unknown preset {q!r}; see --list")
            jobs.append((q, *PRESETS[q]))
    if a.size:
        w, h = (int(x) for x in a.size.lower().split("x"))
        jobs.append((f"{w}x{h}", w, h, a.fit, "custom", "custom size"))
    return jobs


def export_image(a):
    """Image file -> print files. Same presets, checks and manifest as the vector path."""
    art = R.RasterArt(a.doc, a.knockout, a.tol, trim=not a.no_trim)
    focus = tuple(float(x) for x in a.focus.split(","))
    name = a.name or Path(a.doc).stem
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = []
    for preset, W, H, fit, kind, note in build_jobs(a):
        margin = a.margin if kind != "sticker" else max(a.margin, 0.06)
        if kind == "wall":
            # a cut-out floats whole on its own backdrop colour (seamless); a full scene fills the frame
            wf = a.wall_fit if a.wall_fit != "auto" else ("contain" if art.cut else "cover")
            fit, margin = wf, (max(a.margin, 0.08) if wf == "contain" else margin)
        transparent = kind in ("apparel", "sticker") and art.cut and not a.keep_background
        if fit == "mug":
            v = view_for(art, W // 2, H, "contain", focus, margin)
            plan.append((preset, W, H, kind, note, v, W // 2, transparent, True))
        else:
            plan.append((preset, W, H, kind, note, view_for(art, W, H, fit, focus, margin), W, transparent, False))
    need = max(pw / v[2] for *_, v, pw, _t, _m in plan)
    print(f"[export] {art.w}x{art.h} source, {'cut-out on ' + art.backdrop if art.cut else 'no cut-out'}, "
          f"largest product needs {need:.2f}x", flush=True)
    art.prepare(need, a.upscale, a.upscale_model, out / ".work")
    manifest = {"source": str(Path(a.doc).resolve()), "dpi": DPI, "upscale": round(art.factor, 3),
                "upscaler": f"Real-ESRGAN {R.MODELS[a.upscale_model]}" if art.factor > 1 else None, "files": []}
    for preset, W, H, kind, note, v, pw, transparent, mug in plan:
        if mug:
            half = art.render(pw, H, v, True)
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0) if transparent else
                            S.hex_to_rgb(a.backdrop or art.backdrop) + (255,))
            img.alpha_composite(half, (0, 0))
            img.alpha_composite(half, (W - half.width, 0))
        else:
            img = art.render(W, H, v, transparent, a.backdrop)
        if a.flatten_alpha:
            img.putalpha(img.getchannel("A").point(lambda x: 255 if x > 127 else 0))
        warn = checks(img, kind)
        if kind in ("apparel", "sticker") and not art.cut:
            warn.append("no plain background was found, so this prints as a full rectangle; "
                        "regenerate on a flat background or pass --knockout #hex")
        ddpi = R.detail_dpi(art, v, pw)
        if ddpi < 270:
            fix = ("install the upscaler (--install-upscaler)" if not R.esrgan_bin() else
                   "fine at the smaller sizes this ratio scales to; for full detail use a larger source "
                   "(Gemini --size 4K)")
            warn.append(f"detail DPI {ddpi} at full size: {fix}")
        if kind == "sticker":
            img = sticker_outline(img, px=round(W * 0.03))
        fmt = a.format if a.format != "auto" else ("jpg" if kind == "wall" else "png")
        path = out / f"{name}-{preset}.{fmt}"
        mb = save(img, path, fmt)
        if kind == "wall" and mb > ETSY_DIGITAL_MAX_MB:
            warn.append(f"{mb:.1f} MB is over Etsy's {ETSY_DIGITAL_MAX_MB} MB digital-file limit")
        manifest["files"].append({"preset": preset, "file": str(path), "px": [W, H],
                                  "inches": [round(W / DPI, 2), round(H / DPI, 2)], "mb": round(mb, 2),
                                  "detail_dpi": ddpi, "note": note, "warnings": warn})
        print(f"[export] {path.name}  {W}x{H}  {mb:.1f} MB  detail {ddpi} DPI"
              + "".join(f"\n         ! {w}" for w in warn), flush=True)
    (out / "export.json").write_text(json.dumps(manifest, indent=2))
    print(f"[export] {len(plan)} files -> {out}/  (manifest: export.json)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc", nargs="?")
    ap.add_argument("--out", default="print")
    ap.add_argument("--preset", action="append", default=[])
    ap.add_argument("--size", help="custom WxH in px (300 DPI assumed)")
    ap.add_argument("--fit", choices=["cover", "contain"], default="cover")
    ap.add_argument("--name")
    ap.add_argument("--focus", default="0.5,0.5", help="x,y in 0..1: what to keep when a crop is needed")
    ap.add_argument("--margin", type=float, default=0.04, help="contain/mug/sticker inset, fraction of the side")
    ap.add_argument("--wall-fit", choices=["auto", "cover", "contain"], default="auto",
                    help="posters: auto = contain for cut-out art, cover (full bleed, cropped) otherwise")
    ap.add_argument("--keep-background", action="store_true", help="apparel/stickers: keep the art's background block")
    ap.add_argument("--backdrop", help="#hex field behind the art for posters/mugs (cut-out art defaults to the "
                                       "knocked-out colour; generated art to its own background)")
    ap.add_argument("--flatten-alpha", action="store_true", help="snap alpha to 0/255 (cleaner DTG prints)")
    ap.add_argument("--format", choices=["auto", "png", "jpg"], default="auto",
                    help="auto: JPG for wall art (fits Etsy's 20 MB), PNG for everything else")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--knockout", default="auto", help="image input: auto | none | #hex background to cut out")
    ap.add_argument("--tol", type=float, default=0.12, help="image input: knockout colour tolerance")
    ap.add_argument("--upscale", choices=["auto", "off"], default="auto",
                    help="image input: Real-ESRGAN when a product needs more pixels than the source has")
    ap.add_argument("--upscale-model", choices=sorted(R.MODELS), default="anime",
                    help="anime = flat illustration/cartoon (default); general = photo or painterly")
    ap.add_argument("--no-trim", action="store_true", help="image input: keep the source framing around a cut-out")
    ap.add_argument("--install-upscaler", action="store_true", help="download Real-ESRGAN (~50 MB, BSD-3) once")
    a = ap.parse_args()

    if a.install_upscaler:
        R.install_esrgan()
        return

    if a.list or not a.doc:
        for k, (w, h, fit, kind, note) in PRESETS.items():
            print(f"{k:14s} {w}x{h}  {fit:7s} {note}")
        for k, v in SETS.items():
            print(f"set {k:10s} {', '.join(v)}")
        return

    if Path(a.doc).suffix.lower() in IMAGE_EXT:
        return export_image(a)
    doc = S.load(a.doc)
    focus = tuple(float(x) for x in a.focus.split(","))
    name = a.name or Path(a.doc).resolve().parent.name
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    jobs = build_jobs(a)

    manifest = {"source": str(Path(a.doc).resolve()), "dpi": DPI, "files": []}
    for preset, W, H, fit, kind, note in jobs:
        margin = a.margin
        cut = bool(doc.get("mask") or doc.get("cutout"))
        if kind == "wall" and (cut and a.wall_fit == "auto" or a.wall_fit == "contain"):
            fit, margin = "contain", max(a.margin, 0.08)  # never crop a cut-out subject; float it on the backdrop
        transparent = kind in ("apparel", "sticker") and not a.keep_background
        if doc.get("background") is None and not cut:
            transparent = True
        img = render(doc, W, H, fit, focus, margin if kind != "sticker" else max(margin, 0.06), transparent,
                     a.backdrop)
        if a.flatten_alpha:
            img.putalpha(img.getchannel("A").point(lambda v: 255 if v > 127 else 0))
        warn = checks(img, kind)  # before the outline, so its white border isn't judged as artwork
        if kind == "sticker":
            img = sticker_outline(img, px=round(W * 0.03))
        fmt = a.format if a.format != "auto" else ("jpg" if kind == "wall" else "png")
        path = out / f"{name}-{preset}.{fmt}"
        mb = save(img, path, fmt)
        if kind == "wall" and mb > ETSY_DIGITAL_MAX_MB:
            warn.append(f"{mb:.1f} MB is over Etsy's {ETSY_DIGITAL_MAX_MB} MB digital-file limit")
        manifest["files"].append({"preset": preset, "file": str(path), "px": [W, H],
                                  "inches": [round(W / DPI, 2), round(H / DPI, 2)], "mb": round(mb, 2),
                                  "note": note, "warnings": warn})
        print(f"[export] {path.name}  {W}x{H}  {mb:.1f} MB" + "".join(f"\n         ! {w}" for w in warn), flush=True)
    (out / "export.json").write_text(json.dumps(manifest, indent=2))
    print(f"[export] {len(jobs)} files -> {out}/  (manifest: export.json)")


if __name__ == "__main__":
    main()
