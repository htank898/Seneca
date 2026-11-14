"""Self-bootstrapping environment shared by ellipse-paint's scripts.

Any system python3 can launch a script. On first run this creates a Python 3.12 venv at
<skill>/.venv with `uv`, installs requirements.txt, then re-executes the script inside it.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV = SKILL_DIR / ".venv"
VENV_PY = VENV / "bin" / "python"
REQUIREMENTS = SKILL_DIR / "requirements.txt"
MARKER = VENV / ".ellipse-paint-ready"


def _find_uv():
    uv = shutil.which("uv")
    if uv:
        return uv
    for p in (Path.home() / ".local/bin/uv", Path.home() / ".cargo/bin/uv", Path("/opt/homebrew/bin/uv")):
        if p.exists():
            return str(p)
    return None


def _req_hash():
    import hashlib
    return hashlib.sha1(REQUIREMENTS.read_bytes()).hexdigest()[:12]


def bootstrap():
    # the marker holds a hash of requirements.txt, so adding a dependency reinstalls on the next run
    if VENV_PY.exists() and MARKER.exists() and MARKER.read_text().strip() == _req_hash():
        return
    uv = _find_uv()
    if not uv:
        sys.exit("[setup] `uv` is required to build the ellipse-paint environment.\n"
                 "        Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not VENV_PY.exists():
        print(f"[setup] creating Python 3.12 venv at {VENV}", file=sys.stderr)
        subprocess.run([uv, "venv", "-q", "--python", "3.12", str(VENV)], check=True)
    print("[setup] installing requirements.txt (numpy, pillow, resvg, vtracer, contourpy)", file=sys.stderr)
    subprocess.run([uv, "pip", "install", "-q", "--python", str(VENV_PY), "-r", str(REQUIREMENTS)], check=True)
    probe = subprocess.run([str(VENV_PY), "-c", "import numpy, PIL, resvg_py, vtracer, contourpy"], capture_output=True, text=True)
    if probe.returncode != 0:
        sys.exit(f"[setup] install finished but imports failed:\n{probe.stderr[-1500:]}")
    MARKER.write_text(_req_hash() + "\n")
    print("[setup] ellipse-paint environment ready", file=sys.stderr)


def ensure(script_path):
    """Call at the top of every entry script, before importing numpy/PIL/resvg."""
    if Path(sys.prefix).resolve() == VENV.resolve():
        return
    bootstrap()
    os.execv(str(VENV_PY), [str(VENV_PY), str(script_path), *sys.argv[1:]])
