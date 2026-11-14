"""The shapes document: one JSON file that is the artwork. SVG and every raster are derived from it.

{
  "version": 1, "mode": "fit" | "generate", "w": 200, "h": 300,     # art coordinates (viewBox units)
  "background": "#f3e9dc" | null,                                 # base colour under the shapes; null = none
  "mask": "data:image/png;base64,..." | null,                     # optional subject cut-out (white = keep)
  "backdrop": "#c0c0bf",                                          # masked art only: field outside the subject
  "shapes": [ {"cx":..,"cy":..,"rx":..,"ry":..,"angle":deg,         # ellipse (no "type" = ellipse)
               "fill":"#rrggbb"|null, "opacity":0.5,
               "stroke":"#rrggbb"|null, "strokeWidth":1.5},
              {"type":"circle", "cx":..,"cy":..,"r":.., ...paint},
              {"type":"rect", "x":..,"y":..,"w":..,"h":.., "angle":deg, ...paint},
              {"type":"path", "d":"M..Z", "transform":"translate(..)"?, "evenodd":bool?, ...paint} ],
              # paint = fill / opacity / stroke / strokeWidth (+ "cap":"round" for open strokes)
  "meta": {...}                                                   # how it was made (source, seed, params)
}
"""
import io
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def save(doc, path):
    Path(path).write_text(json.dumps(doc, separators=(",", ":")))


def _f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _paint(s):
    a = [f'fill="{s["fill"]}"' if s.get("fill") else 'fill="none"']
    op = s.get("opacity", 1)
    if op < 1:
        a.append(f'opacity="{_f(op)}"')
    if s.get("stroke"):
        a.append(f'stroke="{s["stroke"]}" stroke-width="{_f(s.get("strokeWidth", 1))}"')
        if s.get("cap"):
            a.append(f'stroke-linecap="{s["cap"]}" stroke-linejoin="round"')
    return a


def shape_el(s):
    t = s.get("type", "ellipse")
    if t == "path":
        a = [f'd="{s["d"]}"']
        if s.get("transform"):
            a.append(f'transform="{s["transform"]}"')
        if s.get("evenodd"):
            a.append('fill-rule="evenodd"')
        return f'<path {" ".join(a + _paint(s))}/>'
    if t == "circle":
        a = [f'cx="{_f(s["cx"])}" cy="{_f(s["cy"])}" r="{_f(max(s["r"], 0.05))}"']
        return f'<circle {" ".join(a + _paint(s))}/>'
    if t == "rect":
        a = [f'x="{_f(s["x"])}" y="{_f(s["y"])}" width="{_f(s["w"])}" height="{_f(s["h"])}"']
        if s.get("angle"):
            a.append(f'transform="rotate({_f(s["angle"])} {_f(s["x"] + s["w"] / 2)} {_f(s["y"] + s["h"] / 2)})"')
        return f'<rect {" ".join(a + _paint(s))}/>'
    a = [f'cx="{_f(s["cx"])}" cy="{_f(s["cy"])}" rx="{_f(max(s["rx"], 0.05))}" ry="{_f(max(s["ry"], 0.05))}"']
    if s.get("angle"):
        a.append(f'transform="rotate({_f(s["angle"])} {_f(s["cx"])} {_f(s["cy"])})"')
    return f'<ellipse {" ".join(a + _paint(s))}/>'


def to_svg(doc, view=None, width=None, height=None, transparent=False, limit=None, background=None):
    """view = (x, y, w, h) in art units; defaults to the whole artwork.

    transparent drops the background; background overrides its colour (e.g. padding for 'contain')."""
    W, H = doc["w"], doc["h"]
    vx, vy, vw, vh = view or (0, 0, W, H)
    width = width or vw
    height = height or vh
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="{_f(vx)} {_f(vy)} {_f(vw)} {_f(vh)}" width="{int(width)}" height="{int(height)}">']
    full = f'x="{_f(vx)}" y="{_f(vy)}" width="{_f(vw)}" height="{_f(vh)}"'
    if doc.get("mask"):
        # Cut-out art: the fitted base colour + shapes live inside the subject mask; outside it is the
        # backdrop (a solid field for posters) or nothing (transparent, for apparel and stickers).
        backdrop = background or doc.get("backdrop") or "#ffffff"
        if not transparent:
            out.append(f'<rect {full} fill="{backdrop}"/>')
        out.append(f'<mask id="subject" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
                   f'<image href="{doc["mask"]}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="none"/></mask>')
        out.append('<g mask="url(#subject)">')
        if doc.get("background"):
            out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{doc["background"]}"/>')
    else:
        # a vector cut-out (trace/generate with a knockout) has no background, but posters still want its backdrop
        fallback = doc.get("backdrop") if doc.get("cutout") else None
        bg = None if transparent else (background or doc.get("background") or fallback)
        if bg:
            out.append(f'<rect {full} fill="{bg}"/>')
        out.append('<g>')
    shapes = doc["shapes"] if limit is None else doc["shapes"][:limit]
    out.extend(shape_el(s) for s in shapes)
    out.append("</g></svg>")
    return "\n".join(out)


def render(svg):
    """SVG string -> PIL RGBA image, rendered by resvg at the svg's width/height."""
    import resvg_py
    from PIL import Image
    png = resvg_py.svg_to_bytes(svg_string=svg)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02x}" for v in rgb)
