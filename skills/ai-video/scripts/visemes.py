#!/usr/bin/env python3
"""Lip-sync data for a character: per-scene viseme (mouth-shape) timelines from Kokoro's own alignment.

Kokoro 0.9.x returns, for every chunk it speaks, the phoneme string it read, word tokens with
start_ts/end_ts, and `pred_dur`: the duration (in 1/40 s frames) the model gave each phoneme
character. The audio is exactly sum(pred_dur) * 600 samples long, so each phoneme's span in the
WAV is known precisely. This script re-runs the same pipeline (same voice, speed and seed as
tts.py) to recover that alignment, checks that it reproduces the existing WAV, maps phonemes to
mouth shapes, and writes them next to the timings. It never writes or changes any WAV.

usage:
  python3 scripts/visemes.py path/to/scenes.json [--voice-dir path/to/voice] [--lead 0.04] [--amplitude]

  --lead       seconds the mouth leads the sound (lips form a shape just before you hear it; default 0.04)
  --amplitude  skip phonemes and write an RMS mouth-opening envelope per video frame instead
               (fallback for voices or languages without timestamps)

writes (into the voice dir, default voice/ next to scenes.json):
  visemes.json   { method, fps, shapes, scenes: [{ id, file, start, words:[{text,t0,t1}],
                   phones:[{p,t0,t1,v}], cues:[{t0,t1,v}], open:[...] }] }   times are seconds from
                   the start of that scene's WAV; add the scene's `start` from timings.json for video time
  visemes.js     the same, as `window.VIDEO_VISEMES = {...}` so a file:// page can load it with <script src>

Mouth shapes (9): rest, MBP (lips pressed), AI (open), E (wide, teeth), O (round open),
U (small round: oo, w, r, sh), FV (lower lip under top teeth), L (tongue: l, th), etc (slightly open:
s t d n k g y and neutral schwa).
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV = SKILL_DIR / ".venv"
VENV_PY = VENV / "bin" / "python"
SR = 24000
FRAME = 600  # samples per Kokoro duration frame (24000 / 40)

SHAPES = ["rest", "MBP", "AI", "E", "O", "U", "FV", "L", "etc"]

# misaki (Kokoro's English G2P) symbols -> mouth shape. Diphthongs are split into two shapes.
PHONE = {}
for c in "mbp": PHONE[c] = "MBP"
for c in "fv": PHONE[c] = "FV"
for c in "lθð": PHONE[c] = "L"
for c in "wuʊɹɚʃʒʧʤ": PHONE[c] = "U"
for c in "ɔo": PHONE[c] = "O"
for c in "æɑʌaɐ": PHONE[c] = "AI"
for c in "ɛeiɪ": PHONE[c] = "E"
for c in "əᵊᵻszdtnkɡgŋjɾʔ": PHONE[c] = "etc"
DIPH = {"I": ("AI", "E"), "W": ("AI", "U"), "O": ("O", "U"), "Y": ("O", "E"), "A": ("E", "E")}
VOWEL_SHAPES = {"AI", "E", "O", "U"}
PUNCT = set(";:,.!?—…\"()“”-")
MODIFIERS = set("ˈˌː")


def load_tts():
    spec = importlib.util.spec_from_file_location("ai_video_tts", SKILL_DIR / "scripts" / "tts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def trim_offset(audio, sr, threshold_db=-45.0, keep=0.04):
    """Samples removed from the front by tts.trim_silence (same rule, so offsets match the WAV)."""
    import numpy as np
    thr = 10 ** (threshold_db / 20) * max(1e-9, float(np.max(np.abs(audio))))
    win = int(sr * 0.01)
    env = np.convolve(np.abs(audio), np.ones(win) / win, mode="same")
    idx = np.where(env > thr)[0]
    return 0 if idx.size == 0 else max(0, idx[0] - int(keep * sr))


def phones_from_chunk(phonemes, pred_dur, t0):
    """Walk the phoneme string with its per-character frame durations. Returns [(char, start, end)]."""
    d = [int(x) for x in pred_dur]
    out = []
    t = t0 + d[0] / 40.0  # <bos>
    for k, ch in enumerate(phonemes):
        dur = d[k + 1] / 40.0 if k + 1 < len(d) - 1 else 0.0
        out.append((ch, t, t + dur))
        t += dur
    return out, t + (d[-1] / 40.0)


def to_visemes(chars):
    """Character spans -> [{p, t0, t1, v}] with modifiers, spaces and /h/ folded into neighbours."""
    phones = []
    pending = None  # time from stress marks, waiting to be given to the next phoneme
    for i, (ch, a, b) in enumerate(chars):
        if ch in MODIFIERS:
            if ch == "ː" and phones:
                phones[-1]["t1"] = b
            else:
                pending = a if pending is None else pending
            continue
        if ch == " ":
            if phones:
                phones[-1]["t1"] = b
            continue
        start = a if pending is None else pending
        pending = None
        if ch in PUNCT:
            phones.append({"p": ch, "t0": start, "t1": b, "v": "rest"})
        elif ch in DIPH:
            v1, v2 = DIPH[ch]
            mid = start + (b - start) * 0.55
            phones.append({"p": ch, "t0": start, "t1": mid, "v": v1})
            phones.append({"p": ch, "t0": mid, "t1": b, "v": v2})
        elif ch == "h":
            phones.append({"p": ch, "t0": start, "t1": b, "v": None})  # takes the next vowel's shape
        else:
            phones.append({"p": ch, "t0": start, "t1": b, "v": PHONE.get(ch, "etc")})
    for i, ph in enumerate(phones):
        if ph["v"] is None:
            nxt = next((q["v"] for q in phones[i + 1:] if q["v"] in VOWEL_SHAPES), "etc")
            ph["v"] = nxt
    return phones


def to_cues(phones, end, lead, min_dur=0.05):
    cues = []
    for ph in phones:
        a, b = max(0.0, ph["t0"] - lead), max(0.0, ph["t1"] - lead)
        if b <= a:
            continue
        if cues and cues[-1]["v"] == ph["v"]:
            cues[-1]["t1"] = b
        else:
            cues.append({"t0": a, "t1": b, "v": ph["v"]})
    # A short pause inside a sentence still reads as speech; only real pauses close the mouth.
    # Then absorb flickers shorter than min_dur into the longer neighbour, but never drop a
    # lip closure (MBP) or a lip bite (FV): those are what make lip-sync read as real.
    changed = True
    while changed:
        changed = False
        for i, c in enumerate(cues):
            if c["t1"] - c["t0"] >= min_dur or c["v"] in ("MBP", "FV"):
                continue
            if len(cues) == 1:
                break
            left = cues[i - 1] if i > 0 else None
            right = cues[i + 1] if i + 1 < len(cues) else None
            tgt = left if (right is None or (left and (left["t1"] - left["t0"]) >= (right["t1"] - right["t0"]))) else right
            if tgt is left:
                left["t1"] = c["t1"]
            else:
                right["t0"] = c["t0"]
            cues.pop(i)
            changed = True
            break
    # Closures need to be visible for at least ~2 video frames.
    for i, c in enumerate(cues):
        if c["v"] in ("MBP", "FV") and c["t1"] - c["t0"] < 0.066:
            need = 0.066 - (c["t1"] - c["t0"])
            if i > 0 and cues[i - 1]["t1"] - cues[i - 1]["t0"] > need + 0.03:
                c["t0"] -= need / 2; cues[i - 1]["t1"] = c["t0"]
            if i + 1 < len(cues) and cues[i + 1]["t1"] - cues[i + 1]["t0"] > need + 0.03:
                c["t1"] += need / 2; cues[i + 1]["t0"] = c["t1"]
    # merge again after edits, then make sure the timeline starts and ends at rest
    merged = []
    for c in cues:
        if merged and merged[-1]["v"] == c["v"]:
            merged[-1]["t1"] = c["t1"]
        else:
            merged.append(dict(c))
    if merged and merged[0]["t0"] > 0:
        merged.insert(0, {"t0": 0.0, "t1": merged[0]["t0"], "v": "rest"})
    if merged and merged[-1]["t1"] < end:
        if merged[-1]["v"] == "rest":
            merged[-1]["t1"] = end
        else:
            merged.append({"t0": merged[-1]["t1"], "t1": end, "v": "rest"})
    for c in merged:
        c["t0"], c["t1"] = round(c["t0"], 3), round(c["t1"], 3)
    return merged


def rms_envelope(pcm, fps):
    import numpy as np
    hop = SR // fps
    n = int(np.ceil(len(pcm) / hop))
    env = np.array([float(np.sqrt(np.mean(pcm[i * hop:(i + 1) * hop] ** 2) + 1e-12)) for i in range(n)])
    peak = float(np.percentile(env, 95)) or 1.0
    return [round(min(1.0, max(0.0, (e / peak - 0.08) / 0.92)), 3) for e in env]


def main():
    if Path(sys.prefix).resolve() != VENV.resolve():
        if not VENV_PY.exists():
            sys.exit("[visemes] no skill venv yet. Run scripts/tts.py once first (it builds .venv/).")
        os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

    tts = load_tts()
    args = tts.parse_args(sys.argv[1:])
    if not args["_"]:
        sys.exit(__doc__)
    scenes_path = Path(args["_"][0]).resolve()
    voice_dir = Path(args.get("voice-dir") or scenes_path.parent / "voice").resolve()
    timings = json.loads((voice_dir / "timings.json").read_text())
    lead = float(args.get("lead") or 0.04)
    fps = int(args.get("fps") or 30)
    amplitude_only = bool(args.get("amplitude"))
    voice, speed = timings["voice"], float(timings["speed"])

    import warnings
    warnings.filterwarnings("ignore")
    import numpy as np
    import soundfile as sf
    import torch

    pipeline = None
    out_scenes = []
    method = "amplitude" if amplitude_only else "kokoro-phoneme-durations"
    for s in timings["scenes"]:
        wav, sr = sf.read(str(voice_dir / s["file"]), dtype="float32")
        row = {"id": s["id"], "file": s["file"], "start": s["start"], "duration": s["duration"],
               "open": rms_envelope(wav, fps)}
        if not amplitude_only:
            if pipeline is None:
                from kokoro import KPipeline
                print(f"[visemes] loading Kokoro, voice {voice}, speed {speed}", file=sys.stderr)
                pipeline = KPipeline(lang_code=voice[0], repo_id=tts.MODEL_REPO)
            torch.manual_seed(0)  # same seed as tts.py, so the vocoder reproduces the WAV
            chars, audio, words, t = [], [], [], 0.0
            ok = True
            for r in pipeline(s["text"], voice=voice, speed=speed, split_pattern=r"\n+"):
                if r.audio is None or r.pred_dur is None:
                    ok = False
                    break
                a = r.audio.detach().cpu().numpy()
                # Model vocab drops unknown characters; keep the string aligned with pred_dur.
                ph = "".join(c for c in r.phonemes if c in pipeline.model.vocab)
                if len(ph) + 2 != len(r.pred_dur):
                    ok = False
                    break
                cs, _ = phones_from_chunk(ph, r.pred_dur.tolist(), t)
                chars += cs
                for tok in (r.tokens or []):
                    if tok.phonemes and tok.start_ts is not None and any(ch.isalnum() for ch in tok.text):
                        words.append({"text": tok.text, "t0": t + tok.start_ts, "t1": t + tok.end_ts})
                audio.append(a)
                t += len(a) / SR
            if not ok or not chars:
                print(f"[visemes] {s['id']}: no phoneme alignment, falling back to amplitude", file=sys.stderr)
                method = "mixed"
            else:
                full = np.concatenate(audio)
                off = trim_offset(full, SR) / SR
                trimmed = full[int(round(off * SR)):int(round(off * SR)) + len(wav)]
                n = min(len(trimmed), len(wav))
                corr = float(np.corrcoef(trimmed[:n], wav[:n])[0, 1]) if n > 100 else 0.0
                if corr < 0.98:
                    # Re-synthesis differs from the WAV (different seed or model): align by envelope.
                    hop = 240
                    e1 = np.array([np.abs(full[i:i + hop]).mean() for i in range(0, len(full), hop)])
                    e2 = np.array([np.abs(wav[i:i + hop]).mean() for i in range(0, len(wav), hop)])
                    best = max(range(0, max(1, len(e1) - len(e2) + 1)), key=lambda k: float(np.dot(e1[k:k + len(e2)], e2)))
                    off = best * hop / SR
                    print(f"[visemes] {s['id']}: re-synthesis correlation {corr:.3f}; aligned by envelope (offset {off:.3f}s)", file=sys.stderr)
                phones = to_visemes([(c, a - off, b - off) for c, a, b in chars])
                row["words"] = [{"text": w["text"], "t0": round(w["t0"] - off, 3), "t1": round(w["t1"] - off, 3)} for w in words]
                row["phones"] = [{"p": p["p"], "t0": round(p["t0"], 3), "t1": round(p["t1"], 3), "v": p["v"]} for p in phones]
                row["cues"] = to_cues(phones, s["duration"], lead)
                row["match"] = round(corr, 4)
                closes = sum(1 for c in row["cues"] if c["v"] == "MBP")
                print(f"[visemes] {s['id']}: {len(row['words'])} words, {len(row['cues'])} cues, "
                      f"{closes} lip closures, WAV match r={corr:.3f}", file=sys.stderr)
        out_scenes.append(row)

    data = {"method": method, "fps": fps, "lead": lead, "shapes": SHAPES, "voice": voice, "speed": speed,
            "scenes": out_scenes}
    (voice_dir / "visemes.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    (voice_dir / "visemes.js").write_text("window.VIDEO_VISEMES = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"visemes: {voice_dir / 'visemes.json'} ({method})")


if __name__ == "__main__":
    main()
