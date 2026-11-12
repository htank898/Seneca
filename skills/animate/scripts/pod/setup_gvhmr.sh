#!/usr/bin/env bash
# One-time GVHMR install on a RunPod GPU pod (Ubuntu 22.04, Python 3.10, CUDA 12.x image).
# Runs remotely via gvhmr.py; idempotent (a marker file skips it on a reused pod).
#
# GVHMR (c) Zhejiang University 3D Vision Group: educational, research and non-profit use only.
# It is cloned from upstream at install time, never vendored into Seneca.
set -euo pipefail
W=/workspace
MARK=$W/.gvhmr_ready
[ -f "$MARK" ] && { echo "[pod] GVHMR already installed"; exit 0; }

echo "[pod] system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ffmpeg git > /dev/null

echo "[pod] cloning GVHMR"
cd $W
[ -d GVHMR ] || git clone --depth 1 https://github.com/zju3dv/GVHMR
cd GVHMR

echo "[pod] python deps (torch 2.3 cu121, pytorch3d wheel, ...)"
python -m pip install -q --upgrade pip
python -m pip install -q cython gdown
python -m pip install -q -r requirements.txt
python -m pip install -q -e .

echo "[pod] checkpoints (GVHMR, HMR2, ViTPose, YOLOv8, DPVO) from the authors' Google Drive"
mkdir -p inputs/checkpoints $W/ckpt_dl
if [ ! -f inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt ]; then
  gdown -q --folder "https://drive.google.com/drive/folders/1eebJ13FUEXrKBawHpJroW0sNSxLjh9xD" -O $W/ckpt_dl
  for d in gvhmr hmr2 vitpose yolo dpvo; do
    src=$(find $W/ckpt_dl -maxdepth 3 -type d -name "$d" | head -1)
    [ -n "$src" ] && rm -rf "inputs/checkpoints/$d" && mv "$src" "inputs/checkpoints/$d"
  done
fi
test -f inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt || {
  echo "[pod] ERROR: GVHMR checkpoint download failed (Google Drive quota?). Retry later." >&2; exit 2; }

# SMPL / SMPL-X come from the user's own registration, uploaded by gvhmr.py
ln -sfn $W/body_models inputs/checkpoints/body_models
test -f inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz || {
  echo "[pod] ERROR: SMPLX_NEUTRAL.npz missing (upload failed?)" >&2; exit 3; }

touch "$MARK"
echo "[pod] GVHMR ready"
