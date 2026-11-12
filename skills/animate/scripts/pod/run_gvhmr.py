"""Run GVHMR on one video and write the body motion as BVH. Runs ON THE GPU POD (see gvhmr.py).

    python run_gvhmr.py clip_30fps.mp4 out_dir [--static-cam] [--f-mm 24]

Writes out_dir/motion.bvh (22 SMPL-X body joints, SMPL names: pelvis, left_hip, ... right_wrist;
Y up, metres, 30 fps, world-grounded: the root path over the ground is in the root channels) and
out_dir/hmr4d_results.pt (GVHMR's raw prediction). Rendering is skipped (it needs extra SMPL
mapping files and a display; Seneca renders in Blender instead).

GVHMR: Shen et al., "World-Grounded Human Motion Recovery via Gravity-View Coordinates",
SIGGRAPH Asia 2024. (c) Zhejiang University; educational, research and non-profit use only.
"""
import os
import sys
from pathlib import Path

ROOT = Path("/workspace/GVHMR")
SMPL_NAMES = ["pelvis", "left_hip", "right_hip", "spine1", "left_knee", "right_knee", "spine2",
              "left_ankle", "right_ankle", "spine3", "left_foot", "right_foot", "neck", "left_collar",
              "right_collar", "head", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
              "left_wrist", "right_wrist"]
PARENTS = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]


def predict(video, out_root, static_cam, f_mm):
    os.chdir(ROOT)
    sys.path[:0] = [str(ROOT), str(ROOT / "tools" / "demo")]
    sys.argv = ["demo.py", "--video", str(video), "--output_root", str(out_root)]
    if static_cam:
        sys.argv.append("-s")
    if f_mm:
        sys.argv += ["--f_mm", str(f_mm)]
    import hydra
    import torch
    import demo  # GVHMR's tools/demo/demo.py (functions only; its __main__ also renders)
    from hmr4d.utils.net_utils import detach_to_cpu

    cfg = demo.parse_args_to_cfg()
    demo.run_preprocess(cfg)
    data = demo.load_data_dict(cfg)
    out = Path(cfg.paths.hmr4d_results)
    if not out.exists():
        model = hydra.utils.instantiate(cfg.model, _recursive_=False)
        model.load_pretrained_model(cfg.ckpt_path)
        model = model.eval().cuda()
        with torch.no_grad():
            pred = detach_to_cpu(model.predict(data, static_cam=cfg.static_cam))
        torch.save(pred, out)
    return torch.load(out)


def rest_joints(betas):
    """The subject's own rest skeleton (22 body joints) from SMPL-X with their mean shape."""
    import smplx
    import torch
    m = smplx.create(str(ROOT / "inputs/checkpoints/body_models"), model_type="smplx", gender="neutral",
                     num_betas=10, use_pca=False, flat_hand_mean=True)
    with torch.no_grad():
        o = m(betas=betas.mean(0, keepdim=True).float())
    return o.joints[0, :22].numpy()


def euler_zxy(aa):
    """Axis-angle (n,3) -> BVH 'Zrotation Xrotation Yrotation' degrees, i.e. R = Rz @ Rx @ Ry."""
    import numpy as np
    th = np.linalg.norm(aa, axis=1, keepdims=True)
    k = np.where(th > 1e-9, aa / np.maximum(th, 1e-12), np.array([[1.0, 0, 0]]))
    K = np.zeros((len(aa), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 0] = -k[:, 2], k[:, 1], k[:, 2]
    K[:, 1, 2], K[:, 2, 0], K[:, 2, 1] = -k[:, 0], -k[:, 1], k[:, 0]
    t = th[:, :, None]
    R = np.eye(3)[None] + np.sin(t) * K + (1 - np.cos(t)) * (K @ K)
    # R = Rz(a) Rx(b) Ry(c):  R[2,1] = sin b,  R[0,1] = -sin a cos b,  R[1,1] = cos a cos b,
    #                         R[2,0] = -cos b sin c,  R[2,2] = cos b cos c
    b = np.arcsin(np.clip(R[:, 2, 1], -1, 1))
    a = np.arctan2(-R[:, 0, 1], R[:, 1, 1])
    c = np.arctan2(-R[:, 2, 0], R[:, 2, 2])
    return np.degrees(np.stack([a, b, c], 1))


def write_bvh(path, J, aa, transl, fps=30.0):
    """J (22,3) rest joints; aa (n,22,3) local axis-angle (joint 0 = global orient); transl (n,3).
    SMPL-X's root rotates about the pelvis joint, so the world pelvis = transl + J[0]."""
    import numpy as np
    n = aa.shape[0]
    children = {i: [c for c, p in enumerate(PARENTS) if p == i] for i in range(22)}
    end = {15: (0, 0.12, 0), 20: None, 21: None, 10: None, 11: None}
    lines = ["HIERARCHY"]

    def emit(i, depth):
        ind = "  " * depth
        off = J[i] - (J[PARENTS[i]] if PARENTS[i] >= 0 else 0)
        if PARENTS[i] < 0:
            lines.append(f"ROOT {SMPL_NAMES[i]}")
        else:
            lines.append(f"{ind}JOINT {SMPL_NAMES[i]}")
        lines.append(f"{ind}{{")
        lines.append(f"{ind}  OFFSET {off[0]:.6f} {off[1]:.6f} {off[2]:.6f}")
        if PARENTS[i] < 0:
            lines.append(f"{ind}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
        else:
            lines.append(f"{ind}  CHANNELS 3 Zrotation Xrotation Yrotation")
        for c in children[i]:
            emit(c, depth + 1)
        if not children[i]:
            if i in (20, 21):      # hand: extend the forearm direction by a palm length
                d = J[i] - J[PARENTS[i]]
                e = d / max(np.linalg.norm(d), 1e-6) * 0.09
            elif i in (10, 11):    # toe tip: a little further along the foot
                d = J[i] - J[PARENTS[i]]
                e = d / max(np.linalg.norm(d), 1e-6) * 0.05
            else:
                e = end.get(i) or (0, 0.08, 0)
            lines.append(f"{ind}  End Site")
            lines.append(f"{ind}  {{")
            lines.append(f"{ind}    OFFSET {e[0]:.6f} {e[1]:.6f} {e[2]:.6f}")
            lines.append(f"{ind}  }}")
        lines.append(f"{ind}}}")

    emit(0, 0)
    order = []

    def walk(i):
        order.append(i)
        for c in children[i]:
            walk(c)

    walk(0)
    eul = euler_zxy(aa.reshape(-1, 3)).reshape(n, 22, 3)
    lines += ["MOTION", f"Frames: {n}", f"Frame Time: {1.0 / fps:.6f}"]
    root = transl + J[0]
    for f in range(n):
        vals = [*root[f]]
        for i in order:
            vals += list(eul[f, i])
        lines.append(" ".join(f"{v:.5f}" for v in vals))
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    import numpy as np
    args = sys.argv[1:]
    video, out_dir = Path(args[0]).resolve(), Path(args[1]).resolve()
    static_cam = "--static-cam" in args
    f_mm = args[args.index("--f-mm") + 1] if "--f-mm" in args else None
    out_dir.mkdir(parents=True, exist_ok=True)
    pred = predict(video, out_dir / "gvhmr", static_cam, f_mm)
    g = pred["smpl_params_global"]
    body = g["body_pose"].reshape(-1, 21, 3).numpy()
    orient = g["global_orient"].reshape(-1, 1, 3).numpy()
    aa = np.concatenate([orient, body], 1)
    J = rest_joints(g["betas"])
    write_bvh(out_dir / "motion.bvh", J, aa, g["transl"].numpy())
    import shutil
    shutil.copy(out_dir / "gvhmr" / video.stem / "hmr4d_results.pt", out_dir / "hmr4d_results.pt")
    print(f"[pod] wrote {out_dir / 'motion.bvh'} ({aa.shape[0]} frames)", flush=True)


if __name__ == "__main__":
    main()
