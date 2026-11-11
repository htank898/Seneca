# Snow, golden hour: notes

An 8-second acting beat, keyframed entirely from a Python script and rendered headless in Blender 5.2 (Cycles). The character is Blender Studio's production rig, not one I built. This tests how far a professional, freely licensed character can be animated with code alone.

**Credit:** Snow Rig (CC) Blender Foundation | studio.blender.org. Licensed CC-BY 4.0, from https://studio.blender.org/characters/snow/ (v4). The sky is `sunset.exr`, which ships with Blender (CC0, Greg Zaal / Poly Haven).

## Run

```bash
# one-time: download + unzip the rig (112 MB) into .cache/Snow/
curl -L -o .cache/snow.zip https://studio.blender.org/download-source/files/ba/0f/ba0fe6d810333b1d73c1c359e4dc03cb-6.zip
unzip .cache/snow.zip -d .cache/

Blender -b -Y .cache/Snow/snow_v4.2.blend -P shot.py -- --stills 20,100,165 --small   # look-dev, ~8 s/frame
Blender -b -Y .cache/Snow/snow_v4.2.blend -P shot.py -- --anim                         # 192 frames, ~10 s/frame
ffmpeg -framerate 24 -i frames/f_%04d.png -c:v libx264 -crf 17 -pix_fmt yuv420p snow-golden-hour.mp4
```

`-Y` stops the bundled `cloudrig.py` from running. That script is only Blender Studio's rig UI panel. All 955 of the rig's drivers are simple expressions, so the rig deforms correctly without it. The `--anim` render skips frames that already exist; re-run it if Blender's Metal shader cache crashes partway, which it does now and then.

## Driving the rig (CloudRig) from code

| Want | Control | Value |
|---|---|---|
| Arms out of the T-pose | `Properties["ik_left_upperarm"] = 0` (and right), then rotate `FK-UpperArm.*` | ±74° about world Y |
| Blink | `MSTR-Eyelid_Upper.*` location Y | −0.025 closes |
| Squint / cheek raise | `MSTR-Eyelid_Lower.*` location Y | +0.007 |
| Brows up | `MSTR-Eyebrow.*` location Y | +0.012 to +0.02 |
| Smile / frown | `ACT-Lips_Corner.*` location Y (X toward the centre widens) | +0.016 smile, −0.015 frown |
| Jaw | `Jaw` rotation X | 4–13° |
| Gaze | `TGT-Eyes`, set via `pose_bone.matrix` to a world point | |
| Head and neck | `FK-Head`, `FK-Neck`, `FK-Chest` | world-axis rotations, converted per bone |

Rotations are written in world axes (the character faces −Y) and converted into each bone's rest frame. That way "turn the head 10° left" means the same thing on every bone.

## Shot

- **Light:** the sky is turned so the hazy sea sits behind him. A warm, soft key from camera left stands in for ground bounce. The implied low sun is a warm rim from behind, with a soft kicker on the other side and a faint cool fill.
- **Camera:** 85 mm at f/2, focused on the eyes. A slow 6% push-in, a little handheld drift, and motion blur.
- **Performance:** he looks down and away, lost in thought, with his lids following the gaze. He blinks, then lifts his eyes to the lens a beat before his head follows. His brows rise, the smile grows into a soft exhale-laugh with a squint and a small jaw drop, and then he looks off to the side, still smiling a little. There are three blinks and small eye drift throughout.
- **Look-dev notes:** EEVEE renders in a third of the time, but the irises go grey and the mouth interior turns pale, so the final render uses Cycles at 96 samples with OpenImageDenoise. A strong backlight makes the ears glow red through subsurface scattering, so the rim light is kept moderate.
