---
name: ai-video
description: Make narrated videos where the visuals are HTML/SVG/JavaScript animation and the voice-over is generated locally with Kokoro (open-source TTS, no API keys). Outputs a portable MP4 (H.264 + AAC) with WebVTT and SRT captions. Use for "make a video", "narrated video", "explainer video with voiceover", "turn this into a video", "video for LinkedIn", product intros, announcement videos, short how-it-works clips, and any animated piece that needs a spoken track.
---

# AI Video: narrated motion graphics as code

You are building a short narrated video the way a machine should: a **script split into scenes**, a **local voice** that speaks each scene, and an **animation that is a pure function of time** keyed to that voice. A headless browser renders every frame, ffmpeg joins frames and voice into an MP4, and captions are generated from the same script. Everything runs on this machine. No editor timeline, no API keys, no paid services.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it before writing any markup so the piece has a deliberate aesthetic direction (palette, type, shape language). If it isn't, commit to a direction yourself: one bold idea, 2–4 flat colors, one display face. If the project already has a visual identity (an existing GIF, deck, or brand sheet), reuse it rather than inventing a new one.

## 2. Write the script as scenes
Infer what you can and use `reference/video-parameters.md` for defaults (size per destination, pacing). Then write `scenes.json` next to where the video should live (the user's project, not inside this skill):

```json
{
  "voice": "af_heart", "speed": 1.0, "gap": 0.35, "leadIn": 0.6, "tail": 1.2,
  "scenes": [
    { "id": "hook", "say": "Every message lands with people who take things in differently.",
      "show": { "kicker": "One message", "head": "Many audiences." } }
  ]
}
```

- **`say` is the spoken line.** Write it to be heard: conversational, one idea per scene, **8–20 words**. Contractions are good. Spell out what should be pronounced ("twenty twenty-seven", "A P I" if needed). Read it aloud in your head; if you'd stumble, rewrite it.
- **`show` is the on-screen content**, any shape your animation needs. Keep on-screen text short: a headline of a few words, labels, a number. **Never put the transcript on screen**; captions already carry the words.
- 4–8 scenes is typical for 30–60 s. Scenes run 3–8 s each. Open with the payoff or the tension, close with the one line you want remembered.
- Keep the tone forward-looking: sell what's possible; don't mock other tools or older ways of working.

## 3. Synthesize the voice
```bash
python3 scripts/tts.py path/to/scenes.json            # writes path/to/voice/
python3 scripts/tts.py --list-voices
```
Flags: `--voice af_heart`, `--speed 0.9`, `--gap 0.35`, `--lead-in 0.6`, `--tail 1.2`, `--out dir`, `--force`.

**First run sets itself up:** it creates a Python 3.12 virtualenv at `.venv/` inside this skill with `uv` (any system Python can launch the script), installs Kokoro, soundfile, and the English spaCy model there, smoke-tests the phonemizer, then re-runs itself inside the venv. Kokoro's weights (~330 MB, `hexgrad/Kokoro-82M`) download once into the Hugging Face cache. `espeak-ng` is not needed for English (Kokoro's phonemizer ships its own copy); if a setup ever reports it missing, it prints the exact `brew install espeak-ng` command to run. `uv` is required; if it's missing, the script prints its one-line installer.

It writes one WAV per scene (`01-hook.wav`, 24 kHz mono, edge silence trimmed), plus `timings.json` and `timings.js` with every scene's `start`/`end`/`duration` (the spoken line) and `from`/`to` (the scene's time on screen; cuts land in the middle of the gap between lines). Re-runs are cached: a scene is only re-synthesized when its text, voice, or speed changes, so editing `show` or one line is fast. The script prints the pace in words per minute; aim for ~150 overall (see the reference).

Kokoro voices are fixed presets (no cloning), and **English is best supported** (American `a*_` and British `b*_` voices). A paid voice such as ElevenLabs or OpenAI could be swapped in later by writing the same WAVs + `timings.json`, but that is not part of this skill.

## 4. Build the animation keyed to the timings
1. Copy `templates/video-shell.html` next to `scenes.json` (so `voice/` sits beside it).
2. Set `CONFIG = { width, height, fps }` for previews. The renderer injects the real `window.VIDEO = { width, height, fps, duration, scenes: [{ id, index, start, end, from, to, text, show }] }` before any page script runs.
3. Replace the scene markup and the body of `window.renderFrame(t, info)`. Rules:
   - **`t` is in seconds** from the start of the video. **Every visual property is computed from `t`.** No CSS animations, `setTimeout`, `Date.now()`, or unseeded randomness. The renderer may jump to any `t`.
   - Use the helpers: `sceneAt(t)` gives the scene on screen plus `local` (seconds since it appeared), `left` (seconds until it leaves), `p` (0..1 across its window), and `speak` (0..1 across its spoken line). `enter(sc, delay, dur)` and `exit(sc, dur)` give eased entrances and exits; `wordTime(s, "chart")` estimates when a word is spoken, so a visual can land on it with `enterAt(t, wordTime(s, "chart"))`.
   - **Read from `s.show`**, not hard-coded copy, so the script stays the single source of truth.
   - Entrances: `outCubic`/`outBack`, 0.4–0.6 s. Exits: `inCubic`, ~0.35 s before `s.to`. Let the last scene hold; don't exit it.
   - Make **frame 0 meaningful**; many feeds use it as the poster.
   - Keep the bottom ~15% of the frame free of essential content in case captions are burned in or overlaid by the player.
   - Text ≥ 36 px at 1080 wide, and on screen for ≥ 1.5 s.
4. Preview: `node scripts/render-video.mjs path/to/animation.html --audio-only` writes `voice/narration.wav`; then open the HTML in a browser. Space plays with sound, ←/→ steps a frame, shift+←/→ jumps a scene, and a click on the stage toggles play.

## 5. Render
```bash
node scripts/render-video.mjs path/to/animation.html --out path/to/name.mp4
```
Flags: `--timings voice/timings.json` (default: `voice/` next to the HTML), `--width 1080 --height 1080 --fps 30` (also 1920×1080, 1080×1920, 1080×1350), `--burn-captions` (off by default), `--keep-frames`, `--lufs -16`, `--true-peak -1.5`, `--crf 20`, `--audio-bitrate 128k`, `--budget-mb 10`, `--audio-only`, `--captions-only`.

It joins the scene WAVs at their exact sample offsets, applies two-pass EBU R128 loudness normalization (`loudnorm`, linear gain) to the target, renders every frame with Playwright, encodes H.264 `yuv420p` + AAC 48 kHz with `+faststart`, and cuts video and audio to the same length. It always writes `name.vtt` and `name.srt` (≤ 2 lines of ≤ 42 characters, cues ≤ ~6 s, split at sentence and clause boundaries and timed by character share). `--burn-captions` draws them into the frames as well. The first run installs Playwright into this skill folder. Requires `ffmpeg` on PATH.

## 6. Verify before reporting
You can't watch or listen the way a viewer does, so check what you can measure and look at what you can see:
- **Frames at every scene boundary:** render with `--keep-frames`, then view the frame just before and just after each scene's `from` (frame = `floor(from × fps)`), plus one at each scene's `end`. Confirm the new layout starts at the cut, nothing is clipped or overlapping, and text is legible. Delete `.frames/` afterwards.
- **A/V sync:** `ffprobe` the MP4; video and audio stream durations should match within 50 ms, and each scene's speech (`start`..`end` in `timings.json`) should sit inside its on-screen window (`from`..`to`).
- **Captions:** the VTT/SRT parse, cues don't overlap, and together they cover every spoken line.
- **Loudness:** the renderer reports integrated LUFS and true peak via `ebur128`; expect about −16 LUFS and a peak at or below −1.5 dBTP, with no clipping.
- **Format:** `h264` + `aac`, `yuv420p`, `moov` before `mdat` (faststart), size within budget.
- Tell the user plainly that you couldn't listen to the voice, and report the measured stats: duration, size, LUFS, peak, words per minute. Ask them to listen for mispronunciations; fix those by respelling the word in `say` and re-running `tts.py` (only that scene re-synthesizes).
- Report the MP4, VTT, and SRT paths, dimensions, duration, and size.

See `reference/video-parameters.md` for sizes, pacing, captions, loudness, voices, and file-size notes.
