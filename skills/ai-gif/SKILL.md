---
name: ai-gif
description: Make looping motion graphics with HTML/SVG/JavaScript and export them as GIF (and MP4). Use for animated explainers, social-post GIFs, reaction/visual gags, loading or status loops, logo stings, animated stats, or any "make me a gif / animation / looping graphic". Prefer this over After Effects-style or video-editor workflows: the animation is code, so it is exact, editable, and seamless.
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
4. Open the HTML in a browser to preview. It autoplays; space pauses, ←/→ scrubs.

## 4. Render
```bash
node scripts/render-gif.mjs path/to/motion.html --mp4
```
Flags: `--out`, `--width`, `--height`, `--fps`, `--seconds`, `--scale 0.75`, `--colors 128`, `--dither none|bayer|sierra2_4a`, `--mp4`, `--mp4-loops 3`, `--budget-mb 5`, `--keep-frames`.
The first run installs Playwright into this skill folder. Requires `ffmpeg` on PATH.

## 5. Verify before reporting
- Render with `--keep-frames` and look at a few PNGs in `.frames/<name>/`: the first frame, the last frame (it should flow straight into the first), and the punchline beat. Delete `.frames/` afterwards.
- Check the file size against the destination budget (the renderer warns). If it's over, try in this order: `--scale 0.75`, `--fps 20`, `--colors 128`, then flatter fills or fewer moving pixels.
- Report the GIF path (and MP4 path), its dimensions, duration, and size.

See `reference/motion-parameters.md` for timing, easing, loop patterns, and size budgets.
