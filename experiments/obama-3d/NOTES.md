# Obama 3D: notes

How far one still photo can be animated with free, local tools: MediaPipe in headless Chromium, numpy and Pillow, and Blender run headless. The result is `obama-3d.mp4`, a 12 s performance with head turns, blinks, a brow raise, a laugh, nods and breathing. No generative model is involved, and no words are put in his mouth.

## Pipeline

```bash
node experiments/obama-3d/track-photo.mjs     # photo -> .cache/landmarks.json + masks.png (~10 s)
python experiments/obama-3d/build.py          # -> .cache/rig.npz + fg.png + bg.png (~2 s)
Blender -b -P experiments/obama-3d/scene.py -- --stills 0,62,134   # test frames
Blender -b -P experiments/obama-3d/scene.py -- --anim               # 288 frames, about 2 s each
ffmpeg -framerate 24 -i experiments/obama-3d/frames/f_%04d.png -c:v libx264 -crf 18 -pix_fmt yuv420p obama-3d.mp4
```

The `.cache/` folder needs `photo.jpg`, `face_landmarker.task` and `segmenter.tflite`. They come from Wikimedia (the 2012 official portrait, public domain) and from `storage.googleapis.com/mediapipe-models`. `Blender` is `/Applications/Blender.app/Contents/MacOS/Blender` (5.2 LTS). The `--save` flag also writes `.cache/obama.blend`, so you can scrub the rig in the UI.

## How it's built

- **Tracking.** MediaPipe Face Landmarker returns 478 3D landmarks. The multiclass selfie segmenter gives soft masks for person, hair and face.
- **Depth.** The geometry is a 4 px grid mesh over the person (132k vertices), pushed toward the camera along camera rays. Because each vertex slides along its ray, the rest pose reproduces the photo pixel-for-pixel. Depth comes from three sources:
  - an ellipsoid skull for the hair and ears;
  - MediaPipe's landmark z for the face, applied as a residual over the skull and spread with a normalised Gaussian splat that fades out off the face;
  - a soft cylinder for the torso.
- **Mouth.** The mesh is split along the bottom edge of the upper teeth. Each mouth column gets two coincident seam vertices: one stays with the upper face, the other rides the jaw. The strips around the seam are zipper-triangulated, so the mesh is closed at rest. A dark, gradient-shaded ellipsoid sits behind the teeth as the cavity and is parented to the head bone.
- **Rig.** One head bone pivots at ear level, behind the face. Its weights are 1 above the jawline and fade to 0 by the collar, so the neck stretches. Six shape keys are computed in numpy from the landmarks:
  - `blinkA` and `blinkB`: the opening collapses onto a lid line and the lid skin stretches down over it;
  - `browUp`;
  - `smileRelax`: the corners move in and down;
  - `jawOpen`: a weighted rotation about the jaw hinge;
  - `breath`.
- **Background.** The person is painted out with a push-pull fill. It only shows at the edges of head turns.
- **Render.** Cycles with emission-only materials and the Standard view transform, so the photo's own lighting passes through unchanged. Motion blur is on, and there's a slow 5% camera push-in.

## Limits seen

- **Head turns hold up to about ±17°.** Past that, the far cheek compresses and the near ear smears, because the photo has no pixels for the side of the head.
- **Lighting is baked in.** The photo's light turns with the head instead of staying put in the room. At these angles it's hard to notice.
- **The mouth interior is invented.** The cavity and tongue gradient read fine in motion. Held as a still, the open mouth looks a little flat, and lower teeth would help.
- **No eye gaze.** The eyes are texture, so they always look where the head points. A UV Warp on the iris region driven by an empty would be the next step.
- **Expressions can only reduce or reshape what the photo shows.** A neutral face, a frown or wider eyes would need content that isn't there. This photo starts at a full smile, which limits the range.
