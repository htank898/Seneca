#!/usr/bin/env python3
"""Synthesize a narration track, one WAV per scene, with Kokoro (hexgrad/Kokoro-82M, Apache-2.0).

Runs fully locally: no API keys, no paid services. On first run it creates a
Python 3.12 virtualenv inside this skill folder (.venv/) with `uv`, installs
Kokoro there, and re-runs itself inside it. The model weights (~330 MB) are
downloaded once from Hugging Face into the standard Hugging Face cache.

usage:
  python3 scripts/tts.py scenes.json [--out voice/] [--voice af_heart] [--speed 1.0]
      [--gap 0.35] [--lead-in 0.6] [--tail 1.2] [--force]
  python3 scripts/tts.py --setup            # bootstrap only
  python3 scripts/tts.py --list-voices

scenes.json:
  {
    "voice": "af_heart", "speed": 1.0,             # optional, CLI flags win
    "gap": 0.35, "leadIn": 0.6, "tail": 1.2,       # optional, seconds
    "scenes": [
      { "id": "hook", "say": "Spoken line, 8 to 20 words.", "show": { ...anything the animation needs... } }
    ]
  }

Writes to --out (default: voice/ next to scenes.json):
  01-hook.wav, 02-....wav     24 kHz mono, one per scene, edge silence trimmed
  timings.json                every scene's start/end/duration on the final timeline
  timings.js                  the same, as `window.VIDEO_TIMINGS = {...}` for file:// previews
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV = SKILL_DIR / ".venv"
VENV_PY = VENV / "bin" / "python"
REQUIREMENTS = SKILL_DIR / "requirements.txt"
SAMPLE_RATE = 24000
MODEL_REPO = "hexgrad/Kokoro-82M"

VOICES = {
    # English voices shipped with Kokoro-82M. "Top-rated" follows the grades in the model card's VOICES.md.
    "af_heart": "American English, female, top-rated (default)",
    "af_bella": "American English, female, top-rated",
    "af_nicole": "American English, female",
    "af_aoede": "American English, female",
    "af_kore": "American English, female",
    "af_sarah": "American English, female",
    "af_nova": "American English, female",
    "af_sky": "American English, female",
    "af_alloy": "American English, female",
    "af_jessica": "American English, female",
    "af_river": "American English, female",
    "am_michael": "American English, male",
    "am_fenrir": "American English, male",
    "am_puck": "American English, male",
    "am_echo": "American English, male",
    "am_eric": "American English, male",
    "am_liam": "American English, male",
    "am_onyx": "American English, male",
    "am_adam": "American English, male",
    "bf_emma": "British English, female",
    "bf_isabella": "British English, female",
    "bf_alice": "British English, female",
    "bf_lily": "British English, female",
    "bm_george": "British English, male",
    "bm_fable": "British English, male",
    "bm_lewis": "British English, male",
    "bm_daniel": "British English, male",
}


# ---------------------------------------------------------------- bootstrap
def find_uv():
    for cand in (shutil.which("uv"), str(Path.home() / ".local/bin/uv"), "/opt/homebrew/bin/uv"):
        if cand and Path(cand).exists():
            return cand
    return None


def bootstrap():
    """Create .venv inside the skill folder and install Kokoro into it (idempotent)."""
    marker = VENV / ".ai-video-ready"
    if marker.exists() and VENV_PY.exists():
        return
    uv = find_uv()
    if not uv:
        sys.exit("[setup] `uv` is required to build the voice environment.\n"
                 "        Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not VENV_PY.exists():
        print(f"[setup] creating Python 3.12 venv at {VENV}", file=sys.stderr)
        subprocess.run([uv, "venv", "--python", "3.12", str(VENV)], check=True)
    print("[setup] installing Kokoro + soundfile (one time, a few minutes)", file=sys.stderr)
    subprocess.run([uv, "pip", "install", "--python", str(VENV_PY), "-r", str(REQUIREMENTS)], check=True)
    # Smoke-test the phonemizer stack so problems surface here, not mid-render.
    probe = subprocess.run([str(VENV_PY), "-c", "from misaki import en; g=en.G2P(trf=False, british=False); print(g('Hello there')[0])"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        print(probe.stderr[-2000:], file=sys.stderr)
        if "espeak" in probe.stderr.lower():
            sys.exit("[setup] Kokoro's phonemizer could not find espeak-ng.\n"
                     "        Install it, then re-run:  brew install espeak-ng")
        sys.exit("[setup] Kokoro installed but the English phonemizer failed to load (see above).")
    marker.write_text("ok\n")
    print("[setup] voice environment ready", file=sys.stderr)


def in_venv():
    return Path(sys.prefix).resolve() == VENV.resolve()


# ---------------------------------------------------------------- helpers
def parse_args(argv):
    out = {"_": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            nxt = argv[i + 1] if i + 1 < len(argv) else None
            if nxt is None or nxt.startswith("--"):
                out[key] = True
            else:
                out[key] = nxt
                i += 1
        else:
            out["_"].append(a)
        i += 1
    return out


def slug(s):
    keep = "".join(c.lower() if c.isalnum() else "-" for c in str(s))
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-") or "scene"


def scene_hash(text, voice, speed):
    h = hashlib.sha256(json.dumps({"text": text, "voice": voice, "speed": round(float(speed), 4),
                                   "model": MODEL_REPO, "trim": 2}, sort_keys=True).encode())
    return h.hexdigest()[:16]


def trim_silence(audio, sr, threshold_db=-45.0, keep=0.04):
    """Trim leading/trailing near-silence, keeping `keep` seconds of room on each side."""
    import numpy as np
    if audio.size == 0:
        return audio
    thr = 10 ** (threshold_db / 20) * max(1e-9, float(np.max(np.abs(audio))))
    win = int(sr * 0.01)
    env = np.convolve(np.abs(audio), np.ones(win) / win, mode="same")
    idx = np.where(env > thr)[0]
    if idx.size == 0:
        return audio
    a = max(0, idx[0] - int(keep * sr))
    b = min(audio.size, idx[-1] + int(keep * sr))
    return audio[a:b]


def wav_duration(path):
    import soundfile as sf
    info = sf.info(str(path))
    return info.frames / info.samplerate


# ---------------------------------------------------------------- main
def main():
    args = parse_args(sys.argv[1:])

    if args.get("list-voices"):
        for k, v in VOICES.items():
            print(f"{k:12s} {v}")
        return

    if not in_venv():
        bootstrap()
        if args.get("setup"):
            return
        os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

    if args.get("setup"):
        return
    if not args["_"]:
        sys.exit(__doc__)

    scenes_path = Path(args["_"][0]).resolve()
    spec = json.loads(scenes_path.read_text())
    scenes = spec["scenes"]
    voice = args.get("voice") or spec.get("voice") or "af_heart"
    speed = float(args.get("speed") or spec.get("speed") or 1.0)
    gap = float(args.get("gap") or spec.get("gap") or 0.35)
    lead_in = float(args.get("lead-in") or spec.get("leadIn") or 0.6)
    tail = float(args.get("tail") or spec.get("tail") or 1.2)
    out_dir = Path(args.get("out") or scenes_path.parent / "voice").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    force = bool(args.get("force"))

    if voice not in VOICES:
        print(f"[tts] warning: '{voice}' is not in the known voice list; trying it anyway", file=sys.stderr)
    lang = voice[0]  # a = American English, b = British English, ...

    timings_path = out_dir / "timings.json"
    previous = {}
    if timings_path.exists():
        try:
            for s in json.loads(timings_path.read_text()).get("scenes", []):
                previous[s["file"]] = s.get("hash")
        except Exception:
            pass

    pipeline = None
    rows = []
    t = lead_in
    expected_files = set()
    for i, sc in enumerate(scenes):
        sid = sc.get("id") or f"scene{i + 1}"
        text = (sc.get("say") or sc.get("text") or "").strip()
        if not text:
            sys.exit(f"[tts] scene {sid} has no 'say' text")
        fname = f"{i + 1:02d}-{slug(sid)}.wav"
        expected_files.add(fname)
        wav = out_dir / fname
        h = scene_hash(text, voice, speed)
        if not force and wav.exists() and previous.get(fname) == h:
            print(f"[tts] {fname}: cached", file=sys.stderr)
        else:
            if pipeline is None:
                import warnings
                warnings.filterwarnings("ignore")
                import numpy as np  # noqa: F401
                import torch
                from kokoro import KPipeline
                print(f"[tts] loading Kokoro ({MODEL_REPO}), voice {voice}, speed {speed}", file=sys.stderr)
                pipeline = KPipeline(lang_code=lang, repo_id=MODEL_REPO)
            import numpy as np
            import soundfile as sf
            import torch
            torch.manual_seed(0)  # Kokoro's vocoder injects noise; seed it so re-runs are identical
            parts = []
            for _gs, _ps, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+"):
                if audio is not None:
                    parts.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
            if not parts:
                sys.exit(f"[tts] Kokoro produced no audio for scene {sid}")
            pcm = trim_silence(np.concatenate(parts).astype("float32"), SAMPLE_RATE)
            sf.write(str(wav), pcm, SAMPLE_RATE, subtype="PCM_16")
            print(f"[tts] {fname}: {len(pcm) / SAMPLE_RATE:.2f}s", file=sys.stderr)
        dur = wav_duration(wav)
        rows.append({
            "id": sid, "index": i, "file": fname, "text": text,
            "start": round(t, 3), "end": round(t + dur, 3), "duration": round(dur, 3), "hash": h,
            "show": sc.get("show", {}),
        })
        t += dur + (gap if i < len(scenes) - 1 else 0)

    total = t + tail
    # Visual window for each scene: cut in the middle of the gap before it, so the picture
    # changes during the silence, a beat before the next line starts.
    for i, r in enumerate(rows):
        r["from"] = 0.0 if i == 0 else round(r["start"] - gap / 2, 3)
    for i, r in enumerate(rows):
        r["to"] = round(total, 3) if i == len(rows) - 1 else rows[i + 1]["from"]

    # Remove stale WAVs from earlier versions of the script (renamed or deleted scenes).
    for p in out_dir.glob("[0-9][0-9]-*.wav"):
        if p.name not in expected_files:
            p.unlink()

    words = sum(len(r["text"].split()) for r in rows)
    speech = sum(r["duration"] for r in rows)
    timings = {
        "sampleRate": SAMPLE_RATE, "voice": voice, "speed": speed, "model": MODEL_REPO,
        "gap": gap, "leadIn": lead_in, "tail": tail,
        "duration": round(total, 3), "scenes": rows,
    }
    timings_path.write_text(json.dumps(timings, indent=2) + "\n")
    # Same data as a script, so an animation opened from file:// can preview with real timings
    # (browsers block fetch() of local JSON, but <script src> works).
    (out_dir / "timings.js").write_text("window.VIDEO_TIMINGS = " + json.dumps(timings, indent=2) + ";\n")
    print(f"[tts] {len(rows)} scenes, {total:.2f}s total, {words} words, "
          f"{words / (total / 60):.0f} wpm overall ({words / (speech / 60):.0f} while speaking; aim for ~150 overall)", file=sys.stderr)
    print(f"timings: {timings_path}")


if __name__ == "__main__":
    main()
