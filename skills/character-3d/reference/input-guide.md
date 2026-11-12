# Making character art that becomes a good 3D model

TRELLIS.2 reconstructs what it can see. The rig fitter finds joints from the silhouette. Both reward the same kind of image: a clean, neutral, full-body "model sheet" shot, not a dramatic illustration.

## The front view (required)
- **Full body, head to toe,** with nothing cropped (feet included) and a little space around the figure.
- **A-pose:** arms 30–45° away from the body, palms facing the thighs or forward, fingers together or slightly spread. A T-pose also works. Arms touching the torso, hands in pockets, crossed arms, or held props all fuse limbs together.
- **Feet shoulder-width apart,** both on the ground, toes forward. No crossed legs, no walking pose.
- **Facing the camera squarely,** head level, neutral expression. A 3/4 view loses one side of the body.
- **Flat, even light** with no strong cast shadows or rim glow. Shadows get baked into the texture as paint.
- **Plain background** in one flat colour (white, grey, or green). A real transparent PNG is even better.
- **Camera at chest height with a long lens.** Avoid wide-angle distortion (big head, tiny feet).
- **One character,** no props, no floor details, no text or watermark.

## Back and side views (optional, recommended)
They only fix the texture: the back of the outfit, the hair, the sides. They don't change the shape.
- Generate them **in the same session as the front, or as one character-turnaround sheet**, then crop each view. The outfit, colours, and proportions must match the front.
- Same pose, same scale, same light.
- `--left` is the character's **left** side, so they face image-left. `--right` faces image-right.

## Prompt snippets
Adapt these to whichever image generator you use:

> full-body character reference sheet of <character>, standing in a neutral A-pose, arms slightly away from the body, feet shoulder-width apart, facing the camera, orthographic view, flat even studio lighting, plain light grey background, no shadows, no props, entire figure visible head to toe

> character turnaround of <character>: front view, left side view, back view, same character, same outfit, same neutral A-pose, orthographic, flat lighting, plain background, evenly spaced

## Stylized characters
Chibi or cartoon proportions work: landmark detection measures the mesh instead of assuming human ratios. Pass a realistic `--height` (about 1.0 m for chibi) so the rig's IK and physics scale sensibly. Very long hair or a cape should hang clear of the arms, or it will be weighted to them.
