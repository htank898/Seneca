#!/usr/bin/env python3
"""Run Manim Community (MIT) from a private virtualenv inside this skill folder.

On first run it creates a Python 3.12 virtualenv at .venv/ with `uv`, installs
requirements.txt (Manim + Typst for equations, so no TeX install is needed),
smoke-tests a Typst equation render, and then re-runs itself inside the venv.
Every other argument is passed straight to `manim`.

usage:
  python3 scripts/manim.py --setup                      # bootstrap only
  python3 scripts/manim.py render scene.py MyScene -qh  # any manim CLI call
  python3 scripts/manim.py --version

Normally you call scripts/render-math.mjs, which wraps this with output
handling (MP4, GIF, transparent clip). Call this directly for anything else
manim can do (`manim cfg`, `manim checkhealth`, ...).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV = SKILL_DIR / ".venv"
VENV_PY = VENV / "bin" / "python"
REQUIREMENTS = SKILL_DIR / "requirements.txt"
MARKER = VENV / ".ai-math-ready"


def find_uv():
    for cand in (shutil.which("uv"), str(Path.home() / ".local/bin/uv"), "/opt/homebrew/bin/uv"):
        if cand and Path(cand).exists():
            return cand
    return None


def bootstrap():
    """Create .venv inside the skill folder and install Manim into it (idempotent)."""
    if MARKER.exists() and VENV_PY.exists():
        return
    uv = find_uv()
    if not uv:
        sys.exit("[setup] `uv` is required to build the animation environment.\n"
                 "        Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not shutil.which("ffmpeg"):
        sys.exit("[setup] ffmpeg is required (macOS: brew install ffmpeg)")
    if not VENV_PY.exists():
        print(f"[setup] creating Python 3.12 venv at {VENV}", file=sys.stderr)
        subprocess.run([uv, "venv", "--python", "3.12", str(VENV)], check=True)
    print("[setup] installing Manim + Typst (one time, a minute or two)", file=sys.stderr)
    r = subprocess.run([uv, "pip", "install", "--python", str(VENV_PY), "-r", str(REQUIREMENTS)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:], file=sys.stderr)
        if "cairo" in r.stderr.lower() or "pkg-config" in r.stderr.lower():
            sys.exit("[setup] pycairo needs Cairo and pkg-config to build. Install them, then re-run:\n"
                     "        brew install cairo pkgconf")
        sys.exit("[setup] installing Manim failed (see above).")
    # Smoke-test the equation stack so problems surface here, not mid-render.
    # Run it in a temp dir: Manim writes its Typst scratch files to ./media.
    with tempfile.TemporaryDirectory() as tmp:
        probe = subprocess.run([str(VENV_PY), "-W", "ignore", "-c",
                                "from manim import MathTypst; m = MathTypst('a^2 + b^2 = c^2'); print(len(m.submobjects))"],
                               capture_output=True, text=True, cwd=tmp)
    if probe.returncode != 0:
        print(probe.stderr[-2000:], file=sys.stderr)
        sys.exit("[setup] Manim installed but a Typst equation failed to render (see above).")
    MARKER.write_text("ok\n")
    print("[setup] animation environment ready", file=sys.stderr)


def main():
    argv = sys.argv[1:]
    bootstrap()
    if argv == ["--setup"]:
        return
    # Make templates/seneca_scene.py importable from any scene file.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SKILL_DIR / "templates"), env.get("PYTHONPATH")]))
    env.setdefault("PYTHONWARNINGS", "ignore::SyntaxWarning")
    cmd = [str(VENV_PY), "-m", "manim", *argv]
    sys.exit(subprocess.run(cmd, env=env).returncode)


if __name__ == "__main__":
    main()
