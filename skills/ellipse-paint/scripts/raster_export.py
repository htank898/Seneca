"""Image input for pod_export.py: a Gemini (or any) PNG/JPG straight to 300 DPI print files.

Pipeline: knock out the plain background -> upscale with Real-ESRGAN only as far as the largest product needs
-> per product, crop or fit, composite onto a backdrop or keep transparent. Each file reports its *detail DPI*:
the resolution of real (source or AI-upscaled) pixels behind it, so a 24x36 poster from a 1K image can't
pass silently as 300 DPI.
"""
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

import shapes as S
from cutout import subject_mask

ESRGAN_RELEASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
ESRGAN_ZIP = {"Darwin": "realesrgan-ncnn-vulkan-20220424-macos.zip",
              "Linux": "realesrgan-ncnn-vulkan-20220424-ubuntu.zip",
              "Windows": "realesrgan-ncnn-vulkan-20220424-windows.zip"}
ESRGAN_HOME = Path(os.environ.get("SENECA_REALESRGAN_HOME", Path.home() / ".cache" / "seneca" / "realesrgan"))
MODELS = {"anime": "realesrgan-x4plus-anime",  # flat illustration / cartoon: crisp outlines, clean fills
          "general": "realesrgan-x4plus"}      # photographic or painterly sources


def esrgan_bin():
    exe = "realesrgan-ncnn-vulkan" + (".exe" if platform.system() == "Windows" else "")
    for p in (os.environ.get("SENECA_REALESRGAN"), ESRGAN_HOME / "pkg" / exe):
        if p and Path(p).exists():
            return Path(p)
    return None


def install_esrgan():
    """Download the pinned Real-ESRGAN ncnn-vulkan release (BSD-3) into ESRGAN_HOME/pkg."""
    name = ESRGAN_ZIP.get(platform.system())
    if not name:
        sys.exit(f"[upscale] no Real-ESRGAN build for {platform.system()}")
    ESRGAN_HOME.mkdir(parents=True, exist_ok=True)
    z = ESRGAN_HOME / name
    print(f"[upscale] downloading {ESRGAN_RELEASE}{name} (~50 MB) -> {ESRGAN_HOME}", flush=True)
    urllib.request.urlretrieve(ESRGAN_RELEASE + name, z)
    with zipfile.ZipFile(z) as f:
        f.extractall(ESRGAN_HOME / "pkg")
    b = esrgan_bin()
    if not b:
        sys.exit("[upscale] unpacked, but the realesrgan-ncnn-vulkan binary wasn't found")
    b.chmod(0o755)
    z.unlink()
    print(f"[upscale] ready: {b}")
    return b


def upscale(img, factor_needed, model, work_dir):
    """img (RGB) -> (upscaled RGB, factor). Pre-shrinks so 4x lands near the needed size (bounded memory)."""
    b = esrgan_bin()
    if not b:
        print("[upscale] Real-ESRGAN isn't installed; using plain resampling. "
              "Run `pod_export.py --install-upscaler` once for sharp upscales.", file=sys.stderr)
        return img, 1.0
    pre = min(1.0, factor_needed / 4)
    src = img if pre >= 0.999 else img.resize((round(img.width * pre), round(img.height * pre)), Image.LANCZOS)
    work_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    tag = hashlib.sha1(img.tobytes() + f"{model}{src.size}".encode()).hexdigest()[:12]
    out = work_dir / f"upscaled-{tag}.png"
    if not out.exists():
        with tempfile.TemporaryDirectory() as t:
            inp = Path(t) / "in.png"
            src.save(inp)
            print(f"[upscale] Real-ESRGAN {model} x4: {src.width}x{src.height} -> {src.width * 4}x{src.height * 4}",
                  flush=True)
            r = subprocess.run([str(b), "-i", str(inp), "-o", str(out), "-n", MODELS[model],
                                "-m", str(b.parent / "models")], capture_output=True, text=True)
            if r.returncode != 0 or not out.exists():
                sys.exit(f"[upscale] Real-ESRGAN failed:\n{r.stderr[-1500:]}")
    else:
        print(f"[upscale] reusing {out.name}", flush=True)
    up = Image.open(out).convert("RGB")
    return up, up.width / img.width


class RasterArt:
    """The source image plus its knockout, in original-pixel 'art units' (like a shapes doc's w/h)."""

    def __init__(self, path, knockout, tol, trim=True):
        src = ImageOps.exif_transpose(Image.open(path))
        has_alpha = src.mode in ("RGBA", "LA", "PA") or "transparency" in src.info
        src = src.convert("RGBA")
        self.path = Path(path)
        self.rgb = src.convert("RGB")
        self.w, self.h = src.size
        self.mask = None   # PIL L at <=2048, white = keep
        self.key = None    # knocked-out background colour, RGB 0..255
        self.backdrop = "#ffffff"
        m = subject_mask(src, knockout, tol, has_alpha)
        if m is not None and knockout == "auto" and not has_alpha:
            # only a *plain* background counts: most of the border must sit near the corner colour,
            # otherwise this is a full scene and "auto" would eat whatever touches the edge
            small = np.asarray(self.rgb.resize(m.size), np.float32) / 255
            border = np.concatenate([small[[0, -1]].reshape(-1, 3), small[:, [0, -1]].reshape(-1, 3)])
            key = np.median(border, 0)
            near = float((np.sqrt(((border - key) ** 2).sum(-1) / 3) <= tol).mean())
            if near < 0.85:
                print(f"[export] only {near:.0%} of the border is one flat colour: treating this as a full scene "
                      "(no cut-out). Pass --knockout #hex to force one.", file=sys.stderr)
                m = None
        if m is not None:
            frac = float((np.asarray(m) > 127).mean())
            if frac > 0.97 or frac < 0.02:
                print(f"[export] knockout kept {frac:.0%} of the image, so it found no plain background; "
                      "exporting the full image (no cut-out)", file=sys.stderr)
            else:
                self.mask = m
                if has_alpha:
                    self.key = np.array([255, 255, 255], np.float32)
                else:
                    small = np.asarray(self.rgb.resize(m.size), np.float32)
                    self.key = small[np.asarray(m) <= 127].mean(0)
                self.backdrop = S.rgb_to_hex(self.key)
        if self.mask is not None and trim:
            # generators frame the subject with lots of empty background; trim to the subject (+2% pad) so
            # products are sized to the character, not to Gemini's framing
            ys, xs = np.nonzero(np.asarray(self.mask) > 127)
            k = self.w / self.mask.width
            pad = 0.02 * max(self.w, self.h)
            x0, y0 = max(0, int(xs.min() * k - pad)), max(0, int(ys.min() * k - pad))
            x1, y1 = min(self.w, int((xs.max() + 1) * k + pad)), min(self.h, int((ys.max() + 1) * k + pad))
            self.rgb = self.rgb.crop((x0, y0, x1, y1))
            self.mask = self.mask.crop((round(x0 / k), round(y0 / k), round(x1 / k), round(y1 / k)))
            self.w, self.h = self.rgb.size
        if self.mask is None:
            border = np.concatenate([np.asarray(self.rgb)[[0, -1]].reshape(-1, 3),
                                     np.asarray(self.rgb)[:, [0, -1]].reshape(-1, 3)]).astype(np.float32)
            self.backdrop = S.rgb_to_hex(np.median(border, 0))
        self.up, self.factor = self.rgb, 1.0
        self.rgba = None

    @property
    def cut(self):
        return self.mask is not None

    def prepare(self, factor_needed, mode, model, work_dir):
        if mode != "off" and factor_needed > 1.05:
            self.up, self.factor = upscale(self.rgb, factor_needed, model, work_dir)
        uw, uh = self.up.size
        a = np.full((uh, uw), 255, np.uint8)
        rgb = np.asarray(self.up, np.float32)
        if self.cut:
            # the mask is <=2048 px; resample it to the upscaled size, then re-sharpen the edge so it is
            # ~1-2 px wide at print size instead of a blurry ramp, biased slightly inward to drop the fringe
            ratio = uw / self.mask.width
            m = np.asarray(self.mask.resize((uw, uh), Image.LANCZOS), np.float32) / 255
            k = max(1.0, ratio / 1.5)
            m = np.clip((m - 0.68) * k * 1.6 + 0.5, 0, 1)  # inward bias: no light rim on dark fabric
            # decontaminate edge pixels: remove the background colour mixed into them
            edge = (m > 0.02) & (m < 0.98)
            mm = m[edge][:, None]
            rgb[edge] = np.clip((rgb[edge] - (1 - mm) * self.key) / np.maximum(mm, 0.05), 0, 255)
            a = (m * 255).round().astype(np.uint8)
        self.rgba = Image.fromarray(np.dstack([rgb.round().astype(np.uint8), a]), "RGBA")

    def render(self, W, H, view, transparent, backdrop=None):
        vx, vy, vw, vh = (v * self.factor for v in view)
        img = self.rgba.crop((round(vx), round(vy), round(vx + vw), round(vy + vh))).resize((W, H), Image.LANCZOS)
        if transparent:
            return img
        out = Image.new("RGBA", (W, H), S.hex_to_rgb(backdrop or self.backdrop) + (255,))
        out.alpha_composite(img)
        return out


def detail_dpi(art, view, W):
    """Real source/AI-upscaled pixels per printed inch (300 = full detail)."""
    need = W / view[2]  # output px per original px
    return round(300 * min(1.0, art.factor / need))
