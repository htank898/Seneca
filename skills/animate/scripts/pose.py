#!/usr/bin/env python3
"""Capture a human performance from a video with MediaPipe Pose (Apache-2.0), fully locally.

On first run it creates a Python 3.12 virtualenv inside this skill folder (skills/animate/.venv/) with `uv`,
installs mediapipe + opencv + numpy there, downloads the pose model (~30 MB, once, into
~/.cache/seneca-adapt/), and re-runs itself inside the venv. No API keys.

usage:
  python3 scripts/pose.py ref.mp4 [--out motion.json] [--subject largest|left|right|center|N]
      [--people 2] [--pick-frame N] [--smooth 1.5] [--min-vis 0.5] [--model heavy|full|lite] [--preview]
      [--no-lift] [--lift-smooth 1.0] [--height 1.75]

By default the 3D skeleton is rebuilt from the 2D keypoints (lift.py): every bone keeps the exact
on-screen direction that was tracked, and only its depth is solved from its length. --no-lift keeps
MediaPipe's own 3D estimate instead.
  python3 scripts/pose.py --setup

--subject picks which person to follow when several are in frame (chosen on --pick-frame, a
1-based frame number, else the first frame in the opening 3 s that shows the most people); they're
then tracked forward and backward by nose/shoulder/hip position. --preview writes <out>.check.mp4 (skeleton drawn over
the footage) and <out>.check.png (6 frames tiled) so you can verify the track by eye.

motion.json:
  { fps, frames, width, height, subject, coverage, names: [33 landmark names],
    world: [frame][33][x,y,z]    metres, hip-centred, BLENDER axes (x = camera right, y = away
                                 from camera, z = up), smoothed, gaps interpolated
    image: [frame][33][u,v,vis]  normalized image coords (0..1, v down) for composite/camera work
    valid: [frame] bool          true where the subject was actually detected (not interpolated)
    lengths: { bone: metres }    median segment lengths, used by rig.py to size the skeleton }
"""
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV = SKILL_DIR / ".venv"
VENV_PY = VENV / "bin" / "python"
PKGS = ["mediapipe>=0.10.14", "opencv-python-headless", "numpy"]
CACHE = Path.home() / ".cache" / "seneca-adapt"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task")

NAMES = ["nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye",
         "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right", "left_shoulder",
         "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_pinky",
         "right_pinky", "left_index", "right_index", "left_thumb", "right_thumb", "left_hip",
         "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel",
         "right_heel", "left_foot_index", "right_foot_index"]
# Segments measured for the skeleton (landmark index pairs; midpoints written as tuples).
SEGMENTS = {
    "torso": ((23, 24), (11, 12)), "shoulder_width": (11, 12), "hip_width": (23, 24),
    "neck": ((11, 12), (7, 8)),
    "upper_arm": [(11, 13), (12, 14)], "forearm": [(13, 15), (14, 16)],
    "hand": [(15, (17, 19)), (16, (18, 20))],
    "thigh": [(23, 25), (24, 26)], "shin": [(25, 27), (26, 28)],
    "foot": [(27, 31), (28, 32)], "heel": [(27, 29), (28, 30)],
}
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
         (23, 25), (25, 27), (27, 31), (27, 29), (24, 26), (26, 28), (28, 32), (28, 30), (7, 8)]


# ---------------------------------------------------------------- bootstrap
def find_uv():
    for cand in (shutil.which("uv"), str(Path.home() / ".local/bin/uv"), "/opt/homebrew/bin/uv"):
        if cand and Path(cand).exists():
            return cand
    return None


def bootstrap():
    marker = VENV / ".ai-animate-ready"
    if marker.exists() and VENV_PY.exists():
        return
    uv = find_uv()
    if not uv:
        sys.exit("[setup] `uv` is required to build the pose environment.\n"
                 "        Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not VENV_PY.exists():
        print(f"[setup] creating Python 3.12 venv at {VENV}", file=sys.stderr)
        subprocess.run([uv, "venv", "--python", "3.12", str(VENV)], check=True)
    print("[setup] installing mediapipe + opencv + numpy (one time)", file=sys.stderr)
    subprocess.run([uv, "pip", "install", "--python", str(VENV_PY), *PKGS], check=True)
    probe = subprocess.run([str(VENV_PY), "-c", "import mediapipe, cv2, numpy; print(mediapipe.__version__)"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        sys.exit(f"[setup] mediapipe failed to import:\n{probe.stderr[-2000:]}")
    marker.write_text("ok\n")
    print(f"[setup] pose environment ready (mediapipe {probe.stdout.strip()})", file=sys.stderr)


def in_venv():
    return Path(sys.prefix).resolve() == VENV.resolve()


def parse_args(argv):
    out = {"_": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out[a[2:]] = argv[i + 1]
                i += 2
                continue
            out[a[2:]] = True
        else:
            out["_"].append(a)
        i += 1
    return out


def model_path(variant):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"pose_landmarker_{variant}.task"
    if not p.exists():
        url = MODEL_URL.format(v=variant)
        print(f"[pose] downloading {url}", file=sys.stderr)
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(p)
    return str(p)


# ---------------------------------------------------------------- capture
TRACK_PTS = [0, 11, 12, 23, 24]  # nose, shoulders, hips: stable identity anchors
APP_WEIGHT = 2.0  # how much torso colour counts against position when matching
APP_MAX = 0.45    # hard cap: beyond this Bhattacharyya distance a candidate is someone else
# The working cap adapts: 3x the subject's own recent appearance jitter (+0.04), so a subject
# that matches itself at ~0.07 rejects a look-alike at ~0.25.


def _cand(img_lms, w_lms, box=None):
    """One detected person. box=(x0, y0, cw, ch) maps crop-normalized coords back to the frame."""
    import numpy as np
    im = np.array([[p.x, p.y, p.visibility] for p in img_lms])
    if box is not None:
        x0, y0, cw, ch = box
        im[:, 0] = x0 + im[:, 0] * cw
        im[:, 1] = y0 + im[:, 1] * ch
    wl = np.array([[p.x, p.y, p.z] for p in w_lms])
    torso = float(np.linalg.norm(im[[11, 12], :2].mean(0) - im[[23, 24], :2].mean(0)))
    return {"im": im, "wl": wl, "center": im[[23, 24], :2].mean(0), "torso": max(torso, 1e-3)}


def appearance(rgb, c):
    """Colour signature of the torso (shoulders-to-hips box): HSV histogram, L1-normalized."""
    import cv2
    import numpy as np
    h, w = rgb.shape[:2]
    q = c["im"][[11, 12, 23, 24], :2]
    x0, x1 = int(max(0, q[:, 0].min() * w)), int(min(w, q[:, 0].max() * w))
    y0, y1 = int(max(0, q[:, 1].min() * h)), int(min(h, q[:, 1].max() * h))
    pad = int(0.15 * max(x1 - x0, 1))
    x0, x1 = max(0, x0 - pad), min(w, x1 + pad)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    hsv = cv2.cvtColor(np.ascontiguousarray(rgb[y0:y1, x0:x1]), cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 8], [0, 180, 0, 256, 0, 256]).flatten()
    return hist / max(hist.sum(), 1e-6)


def app_dist(a, b):
    """Bhattacharyya distance 0 (same) .. 1 (disjoint)."""
    import numpy as np
    if a is None or b is None:
        return 0.0
    return float(np.sqrt(max(0.0, 1.0 - np.sum(np.sqrt(a * b)))))


def _cost(c, pred, scale):
    import numpy as np
    return float(np.linalg.norm(c["im"][TRACK_PTS, :2] - pred, axis=1).mean() / scale)


class Detector:
    """MediaPipe in two modes: VIDEO (temporal tracker, follows one person well) and IMAGE
    (re-detects every frame, finds several people). Their candidates are merged per frame."""

    def __init__(self, variant, people):
        import mediapipe as mp
        self.mp = mp
        vision = mp.tasks.vision
        base = mp.tasks.BaseOptions(model_asset_path=model_path(variant))
        kw = dict(min_pose_detection_confidence=0.3, min_pose_presence_confidence=0.3)
        self.video = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=base, running_mode=vision.RunningMode.VIDEO, num_poses=people,
            min_tracking_confidence=0.4, **kw))
        self.image = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=base, running_mode=vision.RunningMode.IMAGE, num_poses=people + 1, **kw))

    def _img(self, rgb):
        return self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)

    def frame(self, rgb, ms):
        cands = []
        for res in (self.video.detect_for_video(self._img(rgb), ms), self.image.detect(self._img(rgb))):
            for a, b in zip(res.pose_landmarks, res.pose_world_landmarks):
                c = _cand(a, b)
                # drop near-duplicates (the two modes often find the same person)
                if all(_cost(c, o["im"][TRACK_PTS, :2], o["torso"]) > 0.25 for o in cands):
                    cands.append(c)
        return cands

    def crop(self, rgb, pts, scale):
        """Re-detect inside a box around a predicted pose; finds a subject the full frame missed."""
        import numpy as np
        h, w = rgb.shape[:2]
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        half_w, half_h = 1.6 * scale, 2.6 * scale  # body is ~3.5 torsos tall
        x0, x1 = max(0.0, cx - half_w), min(1.0, cx + half_w)
        y0, y1 = max(0.0, cy - half_h), min(1.0, cy + half_h)
        X0, X1, Y0, Y1 = int(x0 * w), int(x1 * w), int(y0 * h), int(y1 * h)
        if X1 - X0 < 32 or Y1 - Y0 < 32:
            return []
        sub = np.ascontiguousarray(rgb[Y0:Y1, X0:X1])
        res = self.image.detect(self._img(sub))
        box = (X0 / w, Y0 / h, (X1 - X0) / w, (Y1 - Y0) / h)
        return [_cand(a, b, box) for a, b in zip(res.pose_landmarks, res.pose_world_landmarks)]

    def close(self):
        self.video.close()
        self.image.close()


def read_frames(video):
    import cv2
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    return fps, frames


def choose_subject(cands, subject):
    if subject.isdigit():
        order = sorted(cands, key=lambda c: c["center"][0])
        return order[min(int(subject), len(order) - 1)]
    if subject == "left":
        return min(cands, key=lambda c: c["center"][0])
    if subject == "right":
        return max(cands, key=lambda c: c["center"][0])
    if subject == "center":
        return min(cands, key=lambda c: abs(c["center"][0] - 0.5))
    return max(cands, key=lambda c: c["torso"])  # largest


def track(rgb, dets, det, subject, fps, pick_frame=None):
    """Lock the subject on one frame, then follow it forward and backward.

    The subject is chosen on pick_frame, else on the earliest frame (within the first 3 s)
    that shows the most people, so "left"/"right" mean what the viewer sees there.
    Cost = mean distance of nose/shoulders/hips to a constant-velocity prediction, in units of
    the subject's torso length. When no full-frame candidate is close enough, re-detect on a
    crop around the prediction before giving up on the frame.
    """
    import numpy as np
    n = len(dets)
    if pick_frame is None:
        window = range(min(n, int(3 * fps) + 1))
        most = max(len(dets[i]) for i in window)
        pick_frame = next(i for i in window if len(dets[i]) == most)
    pick_frame = max(0, min(n - 1, pick_frame))
    while pick_frame < n and not dets[pick_frame]:
        pick_frame += 1
    if pick_frame >= n:
        return [None] * n, 0, 0
    chosen = [None] * n
    chosen[pick_frame] = choose_subject(dets[pick_frame], subject)
    rescued = 0

    ref_app = appearance(rgb[pick_frame], chosen[pick_frame])

    def follow(order):
        nonlocal rescued
        last, prev, gap = chosen[pick_frame], None, 0
        app = ref_app
        own = []  # recent appearance distances of accepted matches
        for i in order:
            pts = last["im"][TRACK_PTS, :2]
            vel = (pts - prev["im"][TRACK_PTS, :2]) if prev is not None else 0
            pred = pts + vel * (gap + 1)
            scale = last["torso"]
            limit = 0.6 + 0.05 * min(gap, 6)  # loosen only slightly across dropouts
            jitter = float(np.median(own[-24:])) if len(own) >= 3 else 0.08
            app_max = min(APP_MAX, max(0.15, 3 * jitter + 0.04))

            def score(c):
                # geometry (torso units) + appearance (0..1, weighted) ; appearance breaks ties
                # when two people overlap in lockstep
                c.setdefault("app", appearance(rgb[i], c))
                return _cost(c, pred, scale) + APP_WEIGHT * app_dist(c["app"], app)

            ranked = sorted(dets[i], key=score)
            # appearance only disambiguates between people: with one candidate, geometry decides
            multi = len(dets[i]) > 1
            ok = lambda c: _cost(c, pred, scale) < limit and (not multi or app_dist(c["app"], app) < app_max)
            best = ranked[0] if ranked and ok(ranked[0]) else None
            # Two people close together: if the runner-up is nearly as good, the full-frame
            # pick is ambiguous, so confirm with a crop centred on the prediction.
            ambiguous = best is not None and len(ranked) > 1 and score(ranked[1]) < 1.5 * score(best) + 0.1
            if best is None or ambiguous:
                crop = sorted(det.crop(rgb[i], pred, scale), key=score)
                if crop and ok(crop[0]) and (best is None or score(crop[0]) <= score(best)):
                    best = crop[0]
                    rescued += 1
            if best is None and gap >= 2:
                # Re-identify after a dropout: the prediction is stale, so accept anyone within
                # a few torsos whose torso colour clearly matches the subject's.
                reid = [c for c in dets[i] if _cost(c, pred, scale) < 3.0
                        and app_dist(c["app"], app) < 0.8 * app_max]
                if reid:
                    best = min(reid, key=lambda c: app_dist(c["app"], app))
            if best is not None:
                chosen[i] = best
                own.append(app_dist(best["app"], app))
                if best["app"] is not None and app is not None:
                    app = 0.9 * app + 0.1 * best["app"]  # slow drift for lighting changes
                prev, last, gap = (last if gap == 0 else None), best, 0
            else:
                gap += 1
                if gap > fps:  # lost for over a second: stop predicting motion
                    prev = None

    follow(range(pick_frame + 1, n))
    follow(range(pick_frame - 1, -1, -1))
    return chosen, pick_frame, rescued


def capture(video, variant, people, subject, pick_frame=None):
    import numpy as np
    fps, rgb = read_frames(video)
    if not rgb:
        sys.exit(f"[pose] could not read frames from {video}")
    h, w = rgb[0].shape[:2]
    det = Detector(variant, people)
    dets = [det.frame(f, int(i * 1000 / fps)) for i, f in enumerate(rgb)]
    chosen, picked, rescued = track(rgb, dets, det, subject, fps, pick_frame)
    det.close()
    world = np.array([c["wl"] if c else np.full((33, 3), np.nan) for c in chosen])
    image = np.array([c["im"] if c else np.full((33, 3), np.nan) for c in chosen])
    valid = np.array([c is not None for c in chosen])
    crowd = sum(1 for f in dets if len(f) > 1)
    print(f"[pose] subject '{subject}' locked on frame {picked + 1}; {crowd} frame(s) had several people; "
          f"{rescued} frame(s) resolved by crop re-detection", file=sys.stderr)
    return fps, w, h, world, image, valid


# ---------------------------------------------------------------- cleanup
def fill_and_smooth(arr, mask, sigma):
    """Per-channel: interpolate frames where mask is False, then zero-phase Gaussian smooth."""
    import numpy as np
    n = arr.shape[0]
    out = arr.copy()
    t = np.arange(n)
    good = mask
    if good.sum() == 0:
        return out
    for j in range(arr.shape[1]):
        for c in range(arr.shape[2]):
            out[:, j, c] = np.interp(t, t[good[:, j]] if good.ndim > 1 else t[good],
                                     arr[good[:, j], j, c] if good.ndim > 1 else arr[good, j, c])
    if sigma > 0:
        r = int(3 * sigma + 0.5)
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
        k /= k.sum()
        pad = np.pad(out, ((r, r), (0, 0), (0, 0)), mode="edge")
        sm = np.empty_like(out)
        for j in range(out.shape[1]):
            for c in range(out.shape[2]):
                sm[:, j, c] = np.convolve(pad[:, j, c], k, mode="valid")
        out = sm
    return out


def mid(a, idx):
    import numpy as np
    if isinstance(idx, tuple):
        return a[..., list(idx), :].mean(-2)
    return a[..., idx, :]


def seg_len(world, a, b):
    import numpy as np
    return np.linalg.norm(mid(world, a) - mid(world, b), axis=-1)


def measure(world, valid):
    import numpy as np
    w = world[valid]
    out = {}
    for name, spec in SEGMENTS.items():
        pairs = spec if isinstance(spec, list) else [spec]
        vals = np.concatenate([seg_len(w, a, b) for a, b in pairs])
        out[name] = round(float(np.median(vals)), 4)
    return out


def preview(video, image, valid, out_base, fps):
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(video)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = str(out_base) + ".check.tmp.mp4"
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = len(image)
    picks = set(int(round(x)) for x in np.linspace(0, n - 1, 6))
    tiles = []
    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        col = (60, 220, 60) if valid[i] else (40, 160, 255)
        pts = [(int(u * w), int(v * h)) for u, v, _ in image[i]]
        for a, b in EDGES:
            cv2.line(frame, pts[a], pts[b], col, 3, cv2.LINE_AA)
        for j in range(11, 33):
            cv2.circle(frame, pts[j], 4, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.putText(frame, f"{i + 1}", (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
        vw.write(frame)
        if i in picks:
            tiles.append(cv2.resize(frame, (480, int(480 * h / w))))
    vw.release()
    cap.release()
    final = str(out_base) + ".check.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", final], check=False)
    Path(tmp).unlink(missing_ok=True)
    while len(tiles) % 3:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
    cv2.imwrite(str(out_base) + ".check.png", np.vstack(rows))
    return final, str(out_base) + ".check.png"


def main():
    import os
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    args = parse_args(sys.argv[1:])
    if args.get("setup"):
        return
    if not args["_"]:
        sys.exit(__doc__)
    import numpy as np
    video = str(Path(args["_"][0]).resolve())
    out = Path(args.get("out") or Path(video).with_name("motion.json")).resolve()
    variant = args.get("model", "heavy")
    people = int(args.get("people", 2))
    subject = str(args.get("subject", "largest"))
    sigma = float(args.get("smooth", 1.5))
    min_vis = float(args.get("min-vis", 0.5))

    pick = int(args["pick-frame"]) - 1 if args.get("pick-frame") else None
    fps, w, h, world, image, valid = capture(video, variant, people, subject, pick)
    n = len(valid)
    if valid.sum() == 0:
        sys.exit("[pose] no person detected in any frame")
    # A landmark counts where the subject was found and that landmark was visible enough.
    vis = np.nan_to_num(image[:, :, 2]) >= min_vis
    lm_mask = vis & valid[:, None]
    # Never leave a landmark with no samples at all: fall back to "subject found".
    for j in range(33):
        if lm_mask[:, j].sum() < 2:
            lm_mask[:, j] = valid
    world_s = fill_and_smooth(np.nan_to_num(world), lm_mask, sigma)
    img_s = fill_and_smooth(np.nan_to_num(image), np.repeat(valid[:, None], 33, 1), sigma * 0.5)
    # MediaPipe world: x right, y down, z away from camera  ->  Blender: x right, y away, z up
    world_b = np.stack([world_s[..., 0], world_s[..., 2], -world_s[..., 1]], -1)
    lift_stats = None
    if not args.get("no-lift"):
        # Keep what the camera saw: on-screen bone directions from the 2D keypoints, depth from
        # bone length (see lift.py). MediaPipe's 3D only decides toward/away from camera.
        import lift as lift_mod
        err_before = lift_mod.reprojection_error(world_b, img_s, w, h, valid)
        lifted, scale_px, lift_stats = lift_mod.lift(img_s, world_b, valid, w, h, min_vis=min_vis,
                                                     height_m=float(args.get("height", 1.75)))
        lifted = fill_and_smooth(lifted, np.ones(lifted.shape[:2], bool), float(args.get("lift-smooth", 1.0)))
        err_after = lift_mod.reprojection_error(lifted, img_s, w, h, valid)
        lift_stats.update(reproj_err_pct_mediapipe=round(err_before, 2), reproj_err_pct_lifted=round(err_after, 2))
        world_b = lifted
    lengths = measure(world_b, valid)
    coverage = float(valid.mean())
    body = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    body_vis = float((vis[:, body] & valid[:, None]).mean())

    data = {
        "source": video, "fps": round(fps, 3), "frames": n, "width": w, "height": h,
        "subject": subject, "coverage": round(coverage, 4), "body_visibility": round(body_vis, 4),
        "names": NAMES, "lengths": lengths,
        "lift": lift_stats,
        "world": np.round(world_b, 4).tolist(),
        "image": np.round(img_s, 4).tolist(),
        "valid": valid.tolist(),
    }
    out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"[pose] {n} frames @ {fps:.3f} fps, subject '{subject}'", file=sys.stderr)
    print(f"[pose] coverage {coverage:.1%} of frames, body landmarks visible {body_vis:.1%}", file=sys.stderr)
    gaps = n - int(valid.sum())
    if gaps:
        print(f"[pose] {gaps} frame(s) interpolated (subject not detected)", file=sys.stderr)
    if coverage < 0.9:
        print("[pose] WARNING: coverage under 90% - trim to a cleaner shot or try --subject / --model heavy",
              file=sys.stderr)
    print(f"[pose] median lengths (m): {json.dumps(lengths)}", file=sys.stderr)
    if lift_stats:
        print(f"[pose] 2D-anchored lift: reprojection error {lift_stats['reproj_err_pct_mediapipe']}% -> "
              f"{lift_stats['reproj_err_pct_lifted']}% of torso length (MediaPipe 3D -> lifted); "
              f"{lift_stats['clamped_bone_frames']} clamped, {lift_stats['occluded_bone_frames']} occluded "
              f"of {lift_stats['bone_frames']} bone-frames", file=sys.stderr)
    print(f"[pose] wrote {out}", file=sys.stderr)
    if args.get("preview"):
        mp4, png = preview(video, img_s, valid, out.with_suffix(""), fps)
        print(f"[pose] check video: {mp4}\n[pose] check sheet: {png}", file=sys.stderr)


if __name__ == "__main__":
    if not in_venv():
        bootstrap()
        if sys.argv[1:] == ["--setup"]:
            sys.exit(0)
        sys.exit(subprocess.run([str(VENV_PY), __file__, *sys.argv[1:]]).returncode)
    main()
