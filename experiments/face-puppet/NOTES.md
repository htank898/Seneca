# Face puppet: notes

This is a proof of concept. Face tracking from real footage drives a 2D SVG puppet, and the puppet renders through the ai-gif `renderFrame(t)` renderer. No generative video is involved.

## Pipeline

```bash
node experiments/face-puppet/track.mjs                       # source.mp4 -> track.json + track.js (~10 s)
node skills/ai-gif/scripts/render-gif.mjs experiments/face-puppet/puppet.html --mp4 --mp4-loops 1
cd experiments/face-puppet
mv puppet.mp4 .cache/puppet-silent.mp4
ffmpeg -i .cache/puppet-silent.mp4 -i source.mp4 -map 0:v -map 1:a -c:v copy -c:a aac -shortest puppet.mp4
ffmpeg -i source.mp4 -i puppet.mp4 -filter_complex "[0:v][1:v]hstack=2,scale=1920:-2[v]" \
  -map "[v]" -map 0:a -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -shortest compare.mp4
```

- **Footage.** `source.mp4` is 9.0 s of Chris Anderson from the TED video "TED's secret to great public speaking" (YouTube `-FOCpMAww28`, 4:46.3–4:55.4). It is one continuous frontal close-up, normalised to 30 fps at 720p. The source is 24 fps, so about 1 in 5 frames is a duplicate. Swap in Harrison's own clip by replacing `source.mp4` and re-running.
- **Tracking.** MediaPipe Face Landmarker (`@mediapipe/tasks-vision` 1.1.1, CPU delegate) runs in headless Chromium through `_browser.mjs`. A tiny local HTTP server serves the wasm, the model and the video. The script seeks the `<video>` to each frame's midpoint and calls `detectForVideo`. Output is 52 blendshapes, yaw/pitch/roll from the facial transformation matrix, and the nose position (for camera-follow). Each channel then goes through a One Euro filter with its own settings.
- **Puppet.** `puppet.html` is built from `motion-shell.html`. It loads `track.js`, because a file:// page can't `fetch` `track.json`. `renderFrame(t)` reads frame `floor(t * frames)`. `MOTION.seconds` is `frames / fps`, so the render's frame count matches the track exactly. Calibration is computed once from the whole track, so each frame is still a pure function of `t`.

## What worked

- **MediaPipe in Playwright Chromium is fast.** The tracking pass takes about 10 s for 271 frames, including the VP9 transcode. A face was found in every frame.
- **Seeking `<video>` is deterministic.** Seeking to frame midpoints with `runningMode: "VIDEO"` and synthetic monotonic timestamps gives repeatable results.
- **Per-performance auto-calibration is the important retargeting move.** Each channel has its rest (10th percentile or median) and peak (97th percentile) taken from this performance. The rig then reacts to change, not absolute scores. Raw MediaPipe values are too timid and biased per person to use directly.
- **Parallax by depth layer sells the turns cheaply.** The layers are back hair and ears, skull, the face plane, and the nose. The near ear grows, the far ear and far eye foreshorten, and the head rolls around the neck.
- **Frame 1:1 sync holds.** The rendered frame `i` is tracked frame `i`, and the compare video stays in lockstep with the audio.

## Jitter

The jitter metric is the mean absolute second difference per frame, stored in `track.json.jitter`:

| channel | raw | One Euro |
|---|---|---|
| eyeBlinkLeft | 0.078 | 0.039 (light smoothing on purpose, or blinks never fully close) |
| jawOpen | 0.045 | 0.017 |
| browOuterUpLeft | 0.045 | 0.011 |
| yaw (deg) | 0.35 | 0.10 |
| pitch (deg) | 0.58 | 0.17 |

- **Pitch is the noisiest pose axis.** Its scale and depth cues are weak from one camera. The One Euro settings for pose (`minCutoff 0.8, beta 0.02`) remove the visible shimmer. They add a little lag on fast nods.
- **Blink and mouth are a trade-off.** Smoothing them hard makes blinks half-close and syllables blur together. They get a high `minCutoff` and rely on the rig's smoothstep remap to look decisive.
- **Duplicate frames at 24 → 30 fps make tiny stair-steps.** These show on slow channels. Tracking at the native 24 fps and resampling the track would be cleaner.

## Retargeting issues seen

- **Rest pose isn't neutral.** He's angled toward an off-camera interviewer, so yaw rests near −14° and gaze rests to the left. Pose and gaze are relative to the performance median, so the puppet "faces camera" while he faces the interviewer. That's right for a puppet, but it means big head turns read smaller than they look in the source.
- **Looking down leaks into blink.** `eyeBlink*` rises to about 0.4–0.6 whenever he looks down. The blink signal is discounted by excess `eyeLookDown*` before a smoothstep window (0.36 → 0.62). False closes during the long downward glance (frames 90–112) are mostly gone. Real blinks still close fully.
- **Gaze was mirrored in the first render (fixed).** I assumed MediaPipe's `Left` eye channels were image-left. They're the performer's own left, so `eyeLookOutLeft` means looking toward the viewer's right. With the wrong sign, every glance played backwards. It was worst on head turns: he turns his head left and swings his eyes back toward camera, while the puppet turned both head and eyes left. Checked against iris crops at frames 75 and 180. The eye channels are relative to the head, so a wrong sign doubles the apparent turn instead of cancelling it. Always verify gaze against a close-up of the irises.
- **Dead channels amplified noise into expressions (fixed).** `browDown*` never goes above 0.04 for this face. Percentile calibration stretched that noise to full strength, so the rig showed a maximum frown at random. The brow tilt was also inverted: the frown raised the inner ends, which is the worried, sad shape. Together with the mirrored gaze, that produced a sad face staring into the distance at frame 180. `norm()` now uses a minimum span (`MIN_SPAN = 0.25`), so channels with almost no range stay quiet, and the frown drops the inner ends.
- **Speech reads as a smile.** Wide, open vowels push `mouthSmile*` to about 0.5. On the puppet that's a grin, so big-mouth moments look happier than he is. A smile weight gated by jaw opening (or real visemes) would fix it.
- **`mouthPucker` spikes on some vowels.** It peaks at 0.87, which sometimes over-rounds the mouth. Its gain needs a per-channel ceiling, not a percentile.
- **Some channels are always near zero for this face and camera:** `cheekSquint*` (0), `browDown*` and `eyeWide*`. Frown and surprise have little dynamic range, so with the minimum span in place, brow-down is now barely visible. That's honest, but a frown will need a better signal, for example brow-to-eye landmark distance.

## Lip sync (Rhubarb)

I downloaded Rhubarb Lip Sync 1.14.0 for macOS with Harrison's OK. It went into the scratchpad, not the repo. It **segfaults** (exit 139) at the "speech recognition" step with both the `pocketSphinx` and `phonetic` recognizers, at 16 kHz and 44.1 kHz, and with one thread. It's an x86_64 binary running under Rosetta on Apple Silicon. Voice-activity detection runs, so the crash is inside its recogniser. The mouth is therefore driven from blendshapes:
- `jawOpen` plus `mouthLowerDown` give the opening.
- `mouthPucker`/`mouthFunnel` give rounding.
- `mouthPress` gives M/B/P closure.
- `mouthSmile` sets width and corners.

That's good enough to read as speech. It isn't crisp visemes. To retry, build Rhubarb from source for arm64 or run the Linux build in Docker, then mix its cues with `jawOpen`. Rhubarb owns the shape and the blendshape owns the amount.

## Next steps

- **Body pose.** MediaPipe Pose Landmarker in the same tracking page gives shoulders, arms and hands. The puppet's body would then lean with the torso and the hands could gesture. He talks with his hands a lot here.
- **3/4-view swaps.** Past about 25° of yaw, parallax runs out. Draw a 3/4 head and switch to it (with a two-frame crossfade) when the yaw gets past a threshold, as cut-out animation does.
- **3D/VRM.** Feed the same blendshapes into a VRM avatar with three-vrm (ARKit names map almost 1:1 to VRM's perfect-sync blendshapes). It would render through the same `renderFrame(t)` contract with a WebGL canvas. Most of the retargeting layer carries over unchanged.
- **Tools.** Add a calibration pass from a few seconds of neutral face, and a JSON-editable `RIG_SPEC` so gains can be tuned without touching code.
