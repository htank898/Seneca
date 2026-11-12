#!/usr/bin/env python3
"""Transcribe a video locally with word-level timestamps: who said what, and exactly when.

Uses faster-whisper (MIT) running OpenAI's Whisper models (MIT) on this machine. No API keys,
nothing leaves the computer. On first run it creates a Python 3.12 virtualenv at .venv/ inside
this skill with `uv`, installs requirements.txt, and re-runs itself inside it. The model
(~1.6 GB for large-v3-turbo) downloads once into the Hugging Face cache.

usage:
  python3 scripts/transcribe.py talk.mov [--out talk.transcript.json] [--model large-v3-turbo]
      [--language en] [--prompt "Seneca, Acme Corp"]   # prompt: names/jargon to spell right
  python3 scripts/transcribe.py --setup

Writes next to the video (or --out):
  talk.transcript.json   { duration, language, text, segments: [{start, end, text, words: [...]}],
                           words: [{i, word, start, end, p}] }   (seconds, p = confidence 0..1)
  talk.srt / talk.vtt    caption files, <= 2 lines of <= 42 chars, split at sentence/clause breaks
"""
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
MARKER = VENV / ".ai-video-edit-ready"


# ---------------------------------------------------------------- bootstrap
def find_uv():
    for cand in (shutil.which("uv"), str(Path.home() / ".local/bin/uv"), "/opt/homebrew/bin/uv"):
        if cand and Path(cand).exists():
            return cand
    return None


def bootstrap():
    if MARKER.exists() and VENV_PY.exists():
        return
    uv = find_uv()
    if not uv:
        sys.exit("[setup] `uv` is required. Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not VENV_PY.exists():
        print(f"[setup] creating Python 3.12 venv at {VENV}", file=sys.stderr)
        subprocess.run([uv, "venv", "--python", "3.12", str(VENV)], check=True)
    print("[setup] installing faster-whisper (one time)", file=sys.stderr)
    subprocess.run([uv, "pip", "install", "--python", str(VENV_PY), "-r", str(REQUIREMENTS)], check=True)
    probe = subprocess.run([str(VENV_PY), "-c", "import faster_whisper; print(faster_whisper.__version__)"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        print(probe.stderr[-2000:], file=sys.stderr)
        sys.exit("[setup] faster-whisper installed but failed to import (see above).")
    MARKER.write_text("ok\n")


def in_venv():
    return Path(sys.prefix).resolve() == VENV.resolve()


def parse_args(argv):
    out = {"_": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            nxt = argv[i + 1] if i + 1 < len(argv) else None
            if nxt is None or nxt.startswith("--"):
                out[a[2:]] = True
            else:
                out[a[2:]] = nxt
                i += 1
        else:
            out["_"].append(a)
        i += 1
    return out


# ---------------------------------------------------------------- captions
def cue_lines(words, max_chars=42, max_lines=2, max_dur=6.0):
    """Group words into caption cues: break at sentence ends first, then clauses, then length."""
    cues, cur = [], []

    def flush():
        if cur:
            cues.append(cur[:])
            cur.clear()

    for w in words:
        cur.append(w)
        text = "".join(x["word"] for x in cur).strip()
        dur = cur[-1]["end"] - cur[0]["start"]
        ends_sentence = w["word"].strip()[-1:] in ".?!"
        if ends_sentence or len(text) > max_chars * max_lines - 6 or dur > max_dur:
            flush()
        elif w["word"].strip()[-1:] in ",;:" and len(text) > max_chars * 0.9:
            flush()
    flush()
    out = []
    for c in cues:
        text = "".join(x["word"] for x in c).strip()
        if len(text) > max_chars:   # balance two lines at the space nearest the middle
            mid = len(text) // 2
            spaces = [i for i, ch in enumerate(text) if ch == " "]
            cut = min(spaces, key=lambda i: abs(i - mid)) if spaces else mid
            text = text[:cut].strip() + "\n" + text[cut:].strip()
        out.append({"start": c[0]["start"], "end": c[-1]["end"], "text": text})
    return out


def ts(t, sep=","):
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)) % 1000:03d}"


# ---------------------------------------------------------------- main
def main():
    args = parse_args(sys.argv[1:])
    bootstrap()
    if args.get("setup"):
        return
    if not in_venv():
        os.execv(str(VENV_PY), [str(VENV_PY), __file__, *sys.argv[1:]])

    if not args["_"]:
        sys.exit(__doc__)
    src = Path(args["_"][0]).resolve()
    if not src.exists():
        sys.exit(f"no such file: {src}")
    stem = src.with_suffix("")
    out = Path(args.get("out") or f"{stem}.transcript.json").resolve()
    model_name = args.get("model") or "large-v3-turbo"

    import numpy as np
    from faster_whisper import WhisperModel

    # Decode with the system ffmpeg (16 kHz mono float) rather than the bundled PyAV, so any
    # container/codec ffmpeg reads works and PyAV version drift can't break transcription.
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)

    print(f"[asr] loading Whisper {model_name} (first run downloads it)", file=sys.stderr)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio, language=args.get("language"), word_timestamps=True, vad_filter=True,
        initial_prompt=args.get("prompt"), beam_size=5, condition_on_previous_text=False,
    )
    segs, words = [], []
    for s in segments:
        ws = [{"i": len(words) + k, "word": w.word, "start": round(w.start, 3), "end": round(w.end, 3),
               "p": round(w.probability, 3)} for k, w in enumerate(s.words or [])]
        words.extend(ws)
        segs.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "words": ws})
        print(f"[asr] {s.start:6.2f}-{s.end:6.2f}  {s.text.strip()}", file=sys.stderr)

    data = {"source": str(src), "model": model_name, "language": info.language, "duration": round(info.duration, 3),
            "text": " ".join(s["text"] for s in segs), "segments": segs, "words": words}
    out.write_text(json.dumps(data, indent=2) + "\n")

    cues = cue_lines(words)
    srt = "\n".join(f"{i + 1}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues))
    vtt = "WEBVTT\n\n" + "\n".join(f"{ts(c['start'], '.')} --> {ts(c['end'], '.')}\n{c['text']}\n" for c in cues)
    Path(f"{stem}.srt").write_text(srt)
    Path(f"{stem}.vtt").write_text(vtt)
    low = [w for w in words if w["p"] < 0.5]
    print(f"transcript: {out} ({len(words)} words, {info.duration:.1f}s, language {info.language})")
    print(f"captions: {stem}.srt, {stem}.vtt ({len(cues)} cues)")
    if low:
        print("low-confidence words (check spelling): " + ", ".join(f"{w['word'].strip()}@{w['start']:.1f}s" for w in low))


if __name__ == "__main__":
    main()
