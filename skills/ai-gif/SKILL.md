---
name: ai-gif
description: Make looping motion graphics and short videos with HTML/SVG/JavaScript and export them as GIF and MP4 (optionally with synthesized sound effects), including hand-drawn chalkboard callouts that pause a scene or real footage to write a word and sketch a doodle, then carry on. Use for animated explainers, social-post GIFs, reaction/visual gags, loading or status loops, logo stings, animated stats, "draw/scribble/doodle over my video", "add sound effects", chalk talk or whiteboard-style animation, or any "make me a gif / animation / looping graphic". Prefer this over After Effects-style or video-editor workflows, because the animation is code, so it is exact, editable, and seamless.
---

# AI GIF: motion graphics as code

You are building a motion graphic the way a machine should: a **pure function of time** written in HTML/SVG/JS, rendered frame-by-frame in a headless browser, then encoded with ffmpeg. You never touch a timeline editor.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it before writing any markup so the piece has a deliberate aesthetic direction (palette, type, shape language). If it isn't, commit to a direction yourself: one bold idea, 2–4 flat colors, one display face. Generic gradients and stock-looking emoji are the "humanoid robot" of motion design. Avoid them.

## 2. Gather only what's missing
Infer what you can from the request and use the defaults in `reference/motion-parameters.md` for the rest. Ask only when a choice can't be guessed and would change the piece substantially:
- **Purpose**: explainer, gag, status loop, logo sting, data animation, social post
- **Destination** (sets size): LinkedIn / X feed → 1080×1080; link-card / blog → 1200×628; Slack / docs → 800×450; story → 1080×1920
- **Message**: the one thing a viewer should get in ≤ 2 seconds of watching

## 3. Build
1. Copy `templates/motion-shell.html` next to where the output should live (the user's project or the current folder, not inside this skill).
2. Set `window.MOTION = { width, height, fps, seconds }`.
3. Replace the scene markup and the body of `window.renderFrame(t)`. Rules:
   - `t` is in `[0, 1)`. **Every visual property is computed from `t`.** No CSS animations, `setTimeout`, `Date.now()`, or random numbers without a fixed seed. The renderer jumps to arbitrary `t`, so state that accumulates across frames will break.
   - The loop must be seamless: `renderFrame(0)` and `renderFrame(1)` must look identical. Use the helpers (`wave`, `pingpong`, integer cycle counts) or end each sequence back at its starting pose.
   - Plan the loop as **beats** with `seg(t, a, b)` windows (for example intro 0–0.15, action 0.15–0.7, punchline 0.7–0.9, reset 0.9–1).
   - Keep any text on screen for ≥ 1.2 s and at ≥ 36 px at 1080 wide.
   - **Stable layout:** give each element a fixed position, row, or lane. Never recompute it every frame from where its neighbors are, because that makes things jump. When elements crowd, fade one out smoothly rather than moving or reflowing it.
   - **Nothing overlaps or clips**, in any frame. Fade early so the fade finishes before anything touches. A character deliberately passing in front of scenery is fine. Labels colliding with labels or icons is not.
   - **Honest scale:** when the piece shows magnitude, draw every frame to a true linear scale. The camera may zoom in log steps, but the axis must not be logarithmic, or equal-looking distances will lie about unequal amounts.
4. **Sound (MP4 only).** If the MP4 is the deliverable, or the user asks for sound, add cues to `window.SOUND`, timed to the same beat boundaries as your `seg()` windows. The template's engine synthesizes them with the Web Audio API, so there are no audio files or downloads. For a GIF-only piece, set `cues: []`. See `reference/sound-design.md` for presets, options, and taste rules.
5. Open the HTML in a browser to preview. It autoplays; space pauses, ←/→ scrubs, M turns sound on.

## 4. Chalk callouts (hand-drawn writing and doodles)
`templates/chalk.js` writes text stroke by stroke in single-stroke handwriting fonts and draws any SVG path as a hand-drawn doodle, in chalk, marker, or pen. Every mark is `mark.draw(p)` with `p` in 0..1, so it follows the same pure-function rules as everything else.

**Add callouts on your own** whenever the script, transcript, or brief names a place, person, number, or named thing a viewer would picture: pause right after the word, write it on a board, doodle its most recognizable shape (St. Louis gets the Gateway Arch), hold a beat, and resume. Keep to about one every 8–10 s unless the user wants more, and list what you added in your report. The full rules, timing, doodle tips, and API are in `reference/chalk-callouts.md`.

- **Over your own scene:** copy `chalk.js` next to the HTML, add `<script src="chalk.js"></script>`, and use `Chalk.timeline(sceneSeconds, [{ at, dur }])` so the scene freezes during each callout (see `examples/gif/chalk-callout.html` in the repo).
- **Over real footage:** run `node scripts/prepare-footage.mjs talk.mp4 --words` (frames, audio, and a word-timed transcript). Copy `templates/chalk-talk.html` and `templates/chalk.js` next to the video, load `talk.footage/footage.js`, read `talk.footage/words.txt`, and fill in `CALLOUTS`. The audio goes silent while the picture is paused.
- A piece with a story (footage, narration, a sentence that plays out) is a **video**, not a loop. It doesn't need `renderFrame(0) == renderFrame(1)`. Render it with `--video`.

## 5. Render
```bash
node scripts/render-gif.mjs path/to/motion.html --mp4
node scripts/render-gif.mjs path/to/talk.html --video      # one-pass MP4 with the page's audio
```
Flags: `--out`, `--width`, `--height`, `--fps`, `--seconds`, `--scale 0.75`, `--colors 128`, `--dither none|bayer|sierra2_4a`, `--mp4`, `--mp4-loops 3`, `--video`, `--no-audio`, `--budget-mb 5`, `--keep-frames`.
If the page has `SOUND` cues, the MP4 gets a soundtrack rendered offline in the headless browser and merged in by ffmpeg (mixed with the footage audio when there is one).
The first run installs Playwright into this skill folder. Requires `ffmpeg` on PATH.

**Math:** for static equations in the page, typeset it first with `node ../ai-math/scripts/typeset.mjs motion.src.html --out motion.html`. For animated math (terms moving, proofs, graphs), render a Manim clip with ai-math (`render-math.mjs … --clip`) and draw it from `renderFrame(t)` with its `clip-player.js`.

## 6. Verify before reporting
- **Check every frame for overlaps**, not just the keyframes: render with `--keep-frames` and step through the transitions, which is where collisions happen. If the page publishes `window.__boxes` (name, box, opacity per element, as ai-scale does), use an automated pass like `ai-scale/scripts/check-overlaps.mjs`.
- Render with `--keep-frames` and look at a few PNGs in `.frames/<name>/`: the first frame, the last frame (it should flow straight into the first), and the punchline beat. Delete `.frames/` afterwards.
- Check the file size against the destination budget (the renderer warns). If it's over, try in this order: `--scale 0.75`, `--fps 20`, `--colors 128`, then flatter fills or fewer moving pixels.
- For callouts, look at a frame mid-write, one with the doodle finished, and the first frame after the board leaves. With footage, confirm the picture is frozen during the pause and the audio picks up where it stopped.
- If there's sound, check that the cues land where you meant: `ffmpeg -i out.mp4 -af silencedetect=n=-45dB:d=0.1 -f null - 2>&1 | grep silence_end` lists where each sound starts. Compare that against `t × seconds`.
- Report the GIF path (and MP4 path), its dimensions, duration, and size, and whether the MP4 has sound.

See `reference/motion-parameters.md` for timing, easing, loop patterns, and size budgets, `reference/chalk-callouts.md` for drawing animations, and `reference/sound-design.md` for sound effects.
