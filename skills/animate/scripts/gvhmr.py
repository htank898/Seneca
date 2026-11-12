#!/usr/bin/env python3
"""Capture world-grounded 3D body motion from a video with GVHMR, on a rented RunPod GPU.

GVHMR (Shen et al., SIGGRAPH Asia 2024) is the strongest open single-camera method with released
code: it recovers the body AND its path over the ground in a gravity-aligned world frame, from a
moving or static camera, with far less foot sliding than per-frame trackers (MediaPipe).

LICENCE: GVHMR is for educational, research and non-profit use only; it predicts SMPL-X bodies,
whose models are non-commercial and need your own free registration. Never use this path for
commercial work; pose.py (MediaPipe, Apache-2.0) is the commercial-safe capture.

usage:
  python3 scripts/gvhmr.py --check                      # what is missing, and how to fix it
  python3 scripts/gvhmr.py clip.mp4 [--out motion.bvh] [--static-cam] [--f-mm 24]
        [--gpu "NVIDIA GeForce RTX 4090"] [--keep-pod] [--pod POD_ID]

Then, in Blender:  mo = rig.load_bvh("motion.bvh", height=H); rig.retarget(arm, mo, locomotion="root", quality=True)

What it needs (one time):
  ~/.config/runpod/api_key (or $RUNPOD_API_KEY)          RunPod API key (runpod.io > Settings > API Keys)
  ~/.cache/seneca-gvhmr/body_models/smplx/SMPLX_NEUTRAL.npz   from smpl-x.is.tue.mpg.de (register, "SMPL-X v1.1 NPZ")
  ~/.cache/seneca-gvhmr/body_models/smpl/SMPL_NEUTRAL.pkl     from smpl.is.tue.mpg.de ("SMPL for Python v1.1.0",
                                                         basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl renamed)
What it does: resamples the clip to 30 fps (GVHMR's rate), starts a GPU pod, uploads the clip, your
body models and two small scripts over SSH, installs GVHMR from upstream (~6-10 min on a fresh pod),
runs it, downloads motion.bvh, and TERMINATES the pod (always, even on errors) unless --keep-pod.
A run on a short clip costs cents; --keep-pod + --pod ID reuses an installed pod for several clips.
Standard library only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://rest.runpod.io/v1"
KEY_FILE = Path.home() / ".config" / "runpod" / "api_key"
SSH_KEY = Path.home() / ".config" / "runpod" / "seneca_ed25519"
MODELS = Path.home() / ".cache" / "seneca-gvhmr" / "body_models"
NEEDED = [MODELS / "smplx" / "SMPLX_NEUTRAL.npz", MODELS / "smpl" / "SMPL_NEUTRAL.pkl"]
IMAGE = "runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04"
GPUS = ["NVIDIA GeForce RTX 4090", "NVIDIA RTX A5000", "NVIDIA L40S", "NVIDIA RTX A6000", "NVIDIA A40"]


def log(*a):
    print("[gvhmr]", *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- checks
def api_key():
    """RUNPOD_API_KEY (what runpodctl and the RunPod plugin read), else ~/.config/runpod/api_key."""
    k_ = os.environ.get("RUNPOD_API_KEY", "").strip()
    if k_:
        return k_
    return KEY_FILE.read_text().strip() if KEY_FILE.exists() else ""


def check(verbose=True):
    problems = []
    if not api_key():
        problems.append(f"RunPod API key missing: create one at https://www.runpod.io/console/user/settings "
                        f"(API Keys), copy it, then:\n    mkdir -p {KEY_FILE.parent} && pbpaste > {KEY_FILE} "
                        f"&& chmod 600 {KEY_FILE}")
    for p in NEEDED:
        if not p.exists():
            src = ("https://smpl-x.is.tue.mpg.de (register > Download > 'SMPL-X v1.1 (NPZ+PKL)')" if "smplx" in p.parts
                   else "https://smpl.is.tue.mpg.de (register > Download > 'SMPL for Python v1.1.0'; "
                        "rename basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl)")
            problems.append(f"{p.name} missing: get it from {src}\n    and put it at {p}")
    for tool in ("ssh", "scp", "ssh-keygen", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            problems.append(f"'{tool}' not found on PATH")
    if verbose:
        if problems:
            log("not ready:")
            for p in problems:
                print("  - " + p, file=sys.stderr)
        else:
            log("ready: RunPod key, SMPL-X + SMPL body models, ssh and ffmpeg all present")
    return problems


# ---------------------------------------------------------------- RunPod REST
def api(method, path, body=None):
    key = api_key()
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"RunPod {method} {path}: HTTP {e.code} {e.read().decode(errors='ignore')[:400]}")


def ensure_ssh_key():
    if not SSH_KEY.exists():
        SSH_KEY.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "seneca-gvhmr", "-f", str(SSH_KEY)],
                       check=True)
    return SSH_KEY.with_suffix(".pub").read_text().strip()


def create_pod(gpu):
    pub = ensure_ssh_key()
    gpus = [gpu] if gpu else GPUS
    last = None
    for cloud in ("SECURE", "COMMUNITY"):
        try:
            pod = api("POST", "/pods", {
                "name": "seneca-gvhmr", "imageName": IMAGE, "gpuTypeIds": gpus, "gpuCount": 1,
                "cloudType": cloud, "containerDiskInGb": 60, "volumeInGb": 0,
                "ports": ["22/tcp"], "supportPublicIp": True, "env": {"PUBLIC_KEY": pub}})
            log(f"pod {pod['id']} created ({cloud} cloud)")
            return pod["id"]
        except RuntimeError as e:
            last = e
            log(f"no {cloud} capacity: {str(e)[:160]}")
    raise RuntimeError(f"could not create a pod: {last}")


def wait_ssh(pod_id, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        pod = api("GET", f"/pods/{pod_id}")
        ip, ports = pod.get("publicIp"), pod.get("portMappings") or {}
        port = ports.get("22") or ports.get(22)
        if ip and port:
            r = subprocess.run(ssh_cmd(ip, port) + ["echo ok"], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                log(f"ssh up at {ip}:{port} after {time.time() - t0:.0f}s")
                return ip, int(port)
        time.sleep(10)
    raise RuntimeError(f"pod {pod_id} never became reachable over ssh")


def ssh_cmd(ip, port):
    return ["ssh", "-i", str(SSH_KEY), "-p", str(port), "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=20", f"root@{ip}"]


def scp(ip, port, srcs, dst, down=False):
    base = ["scp", "-r", "-i", str(SSH_KEY), "-P", str(port), "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    if down:
        cmd = base + [f"root@{ip}:{s}" for s in srcs] + [str(dst)]
    else:
        cmd = base + [str(s) for s in srcs] + [f"root@{ip}:{dst}"]
    subprocess.run(cmd, check=True)


def remote(ip, port, cmd):
    r = subprocess.run(ssh_cmd(ip, port) + [cmd])
    if r.returncode != 0:
        raise RuntimeError(f"remote command failed ({r.returncode}): {cmd}")


# ---------------------------------------------------------------- main
def resample(video, tmp):
    out = Path(tmp) / (Path(video).stem + "_30fps.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "fps=30", "-an",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def main(argv):
    if "--check" in argv or "--setup" in argv:
        sys.exit(1 if check() else 0)
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    video = Path(args[0]).resolve()
    out = Path(opt("--out") or video.with_name(video.stem + ".gvhmr.bvh")).resolve()
    if check(verbose=False):
        check()
        sys.exit(1)
    keep = "--keep-pod" in argv
    pod_id = opt("--pod")
    created = False
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        clip = resample(video, tmp)
        try:
            if not pod_id:
                pod_id = create_pod(opt("--gpu"))
                created = True
            ip, port = wait_ssh(pod_id)
            remote(ip, port, "mkdir -p /workspace/body_models /workspace/job")
            scp(ip, port, [MODELS / "smplx", MODELS / "smpl"], "/workspace/body_models/")
            scp(ip, port, [HERE / "pod" / "setup_gvhmr.sh", HERE / "pod" / "run_gvhmr.py", clip], "/workspace/job/")
            log("installing GVHMR on the pod (first run on a pod: several minutes)")
            remote(ip, port, "bash /workspace/job/setup_gvhmr.sh")
            flags = (" --static-cam" if "--static-cam" in argv else "") + \
                    (f" --f-mm {opt('--f-mm')}" if opt("--f-mm") else "")
            log("running GVHMR")
            remote(ip, port, f"cd /workspace/job && python run_gvhmr.py {clip.name} out{flags}")
            scp(ip, port, ["/workspace/job/out/motion.bvh"], tmp, down=True)
            shutil.copy(Path(tmp) / "motion.bvh", out)
            log(f"wrote {out}  ({time.time() - t0:.0f}s)")
        finally:
            if pod_id and (created or "--terminate" in argv) and not keep:
                try:
                    api("DELETE", f"/pods/{pod_id}")
                    log(f"pod {pod_id} terminated")
                except Exception as e:
                    log(f"WARNING: could not terminate pod {pod_id} ({e}); delete it at "
                        f"https://www.runpod.io/console/pods to stop billing")
            elif pod_id:
                log(f"pod {pod_id} left running (--keep-pod); reuse with --pod {pod_id}, "
                    f"stop billing with --pod {pod_id} --terminate or the RunPod console")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
