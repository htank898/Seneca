#!/usr/bin/env bash
# One-time (idempotent) install of the local image -> 3D engine for character-3d.
#
#   bash setup.sh            # install engine + prefetch the 512-pipeline weights
#   bash setup.sh --check    # report status only, change nothing
#
# Everything lands in $SENECA_CHAR3D_HOME (default ~/.cache/seneca/char3d), never in the repo:
#   trellis-silicon/   TRELLIS.2 for Apple Silicon (MIT), pinned commit, its own .venv
#   Hugging Face cache TRELLIS.2-4B 512 checkpoints (MIT), DINOv3 (Meta, gated), BiRefNet (MIT)
#
# RMBG-2.0 (CC BY-NC) is deliberately NOT downloaded: generate.py swaps TRELLIS.2's background
# remover for BiRefNet (MIT), and prep.py hands it RGBA cut-outs anyway.
set -euo pipefail

HOME_DIR="${SENECA_CHAR3D_HOME:-$HOME/.cache/seneca/char3d}"
PORT_DIR="$HOME_DIR/trellis-silicon"
PORT_URL="https://github.com/sanchez-kim/trellis-silicon.git"
PORT_COMMIT="${TRELLIS_SILICON_COMMIT:-fd2a86ff09b9fd3220f166df144ba3182a5b5564}"
PY="$PORT_DIR/.venv/bin/python"
NEED_GB="${SENECA_CHAR3D_MIN_GB:-17}"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

say() { printf '[setup] %s\n' "$*"; }

if [ "$(uname -m)" != "arm64" ] || [ "$(uname -s)" != "Darwin" ]; then
  say "This engine targets Apple Silicon Macs (MPS). On NVIDIA/Linux use upstream TRELLIS.2 instead."
  exit 1
fi

mem_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
free_gb=$(df -g "$HOME" | awk 'NR==2 {print $4}')
say "unified memory: ${mem_gb} GB   free disk: ${free_gb} GB"
[ "$mem_gb" -lt 24 ] && say "note: < 24 GB memory. The 512 pipeline peaks ~17-18 GB, so expect swap; close other apps while generating."

# ---------------------------------------------------------------- engine
engine_ok=0
if [ -x "$PY" ] && [ "$(git -C "$PORT_DIR" rev-parse HEAD 2>/dev/null)" = "$PORT_COMMIT" ] \
   && "$PY" -c "import trellis_silicon" 2>/dev/null; then
  engine_ok=1
fi
say "engine (trellis-silicon @ ${PORT_COMMIT:0:10}): $([ $engine_ok = 1 ] && echo installed || echo missing)"

if [ $CHECK_ONLY = 1 ] && [ $engine_ok = 0 ]; then
  say "not ready: run 'bash $0' to install"
  exit 1
fi
if [ $CHECK_ONLY = 0 ] && [ $engine_ok = 0 ]; then
  if [ "$free_gb" -lt "$NEED_GB" ]; then
    say "need ~${NEED_GB} GB free (engine ~4 GB + weights ~11 GB + headroom), have ${free_gb} GB."
    say "free space first, e.g. with the icloud-offload skill, then re-run."
    exit 1
  fi
  mkdir -p "$HOME_DIR"
  if [ ! -d "$PORT_DIR/.git" ]; then
    git clone -q "$PORT_URL" "$PORT_DIR"
  fi
  git -C "$PORT_DIR" fetch -q origin "$PORT_COMMIT" 2>/dev/null || true
  git -C "$PORT_DIR" checkout -q "$PORT_COMMIT"
  if ! xcrun -sdk macosx -f metal >/dev/null 2>&1; then
    say "no Metal compiler (needs full Xcode + 'xcodebuild -downloadComponent MetalToolchain')."
    say "continuing: Metal extensions that fail to build fall back to slower PyTorch/CPU paths."
  fi
  (cd "$PORT_DIR" && bash setup.sh)
  "$PY" -c "import trellis_silicon" || { say "engine import failed, see output above"; exit 1; }
fi

# BiRefNet's remote modeling code (prep.py, generate.py) imports these; the port's lockfile
# covers timm + kornia but not einops.
if [ $CHECK_ONLY = 0 ] && [ -x "$PY" ] && ! "$PY" -c "import einops, timm, kornia" 2>/dev/null; then
  uv pip install -q --python "$PY" einops timm kornia
fi

# ---------------------------------------------------------------- Hugging Face auth
if [ -x "$PY" ]; then
  if "$PY" -c "from huggingface_hub import get_token; assert get_token()" 2>/dev/null; then
    say "hugging face login: ok"
  else
    say "hugging face login: MISSING"
    say "  1. create a read token at https://huggingface.co/settings/tokens"
    say "  2. request access (usually instant): https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m"
    say "  3. run: hf auth login   (no hf on PATH? uv tool install huggingface_hub, or use $PORT_DIR/.venv/bin/hf)"
    say "  (RMBG-2.0 access is NOT needed; this skill never uses it.)"
    exit 1
  fi
fi

# ---------------------------------------------------------------- weights (512 pipeline only)
# Selective prefetch: ~11 GB instead of the full ~17 GB repo (the *_1024 flow models are skipped).
if [ -x "$PY" ]; then
  "$PY" - "$CHECK_ONLY" <<'PY'
import sys
from huggingface_hub import snapshot_download, try_to_load_from_cache
check_only = sys.argv[1] == "1"
SETS = [
    ("microsoft/TRELLIS.2-4B", ["pipeline.json",
        "ckpts/ss_flow_img_dit_1_3B_64_bf16.*",
        "ckpts/shape_dec_next_dc_f16c32_fp16.*",
        "ckpts/tex_dec_next_dc_f16c32_fp16.*",
        "ckpts/slat_flow_img2shape_dit_1_3B_512_bf16.*",
        "ckpts/slat_flow_imgshape2tex_dit_1_3B_512_bf16.*"]),
    ("microsoft/TRELLIS-image-large", ["ckpts/ss_dec_conv3d_16l8_fp16.*"]),
    ("facebook/dinov3-vitl16-pretrain-lvd1689m", None),
    ("ZhengPeng7/BiRefNet", None),
]
missing = []
for repo, pats in SETS:
    try:
        snapshot_download(repo, allow_patterns=pats, local_files_only=True)
        print(f"[setup] weights {repo}: cached")
    except Exception:
        missing.append((repo, pats))
        print(f"[setup] weights {repo}: missing")
if missing and not check_only:
    for repo, pats in missing:
        print(f"[setup] downloading {repo} ...", flush=True)
        try:
            snapshot_download(repo, allow_patterns=pats)
        except Exception as e:
            print(f"[setup] FAILED {repo}: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
            if "dinov3" in repo:
                print("[setup] DINOv3 is gated: request access at https://huggingface.co/" + repo)
            sys.exit(1)
sys.exit(1 if (missing and check_only) else 0)
PY
fi

say "ready. run: node $(cd "$(dirname "$0")" && pwd)/char3d.mjs front.png --out <dir>"
