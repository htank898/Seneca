# Prompt recipes (Nano Banana + Omni Flash)

These are briefs for an art department, not final frames. Keep each prompt concrete:
- **subject:** silhouette, materials, colors;
- **world:** place, time of day, weather;
- **camera:** lens, height, framing;
- **what must not change.**

Describe genres and materials. Never use brand or character names, or a real person's likeness.

Fill in `<…>`. `{palette}` means 3–5 named colors, such as "oxblood red, brass, gunmetal, cyan eye-glow".

## Restage a frame (hero concept)
Refs: the hero frame from `frames/`.
> Redraw this exact shot as a still from a stylized 3D animated film. Keep the camera angle, framing, lens and the subject's exact pose and position. Replace the person with <character brief: e.g. a biomechanical masked warrior built from interlocking armour shells over a visible dark-metal skeleton, ball joints at shoulders, elbows, knees, a faceplate mask with two glowing slit eyes, crest fins>. Replace the location with <world brief>. Lighting: <sun direction, time of day>. Palette: {palette}. Clean hard-surface shapes that could be modelled from simple solids: bevelled plates, cylinders, spheres. No text, no logos, no extra characters.

Ask for `--n 3` and let the user pick.

## Character turnaround sheet
Refs: the chosen `concept/restaged.png`.
> Character model sheet of the character in this image: three full-body views side by side (front, side, back) in a neutral T-pose, arms straight out, feet shoulder-width, orthographic, evenly lit on a flat light-grey background, the same scale in all three views. Show every armour piece, joint and colour clearly. Palette: {palette}. No text, no labels, no shadows on the background.

## Environment plate
Refs: the chosen `concept/restaged.png`.
> The same location as this image with no characters in it: a wide establishing view at eye level from the same direction, <time of day>, <weather>. Keep the lighting direction and palette. Matte-painting quality, no text.

## Insert our model into the original footage
Use this once the Blender character exists. Refs: a frame from `ref.mp4` and a render of the character in a similar pose (`renders/f1.png`).
> Put the character from the second image into the first image in place of the person, matching the person's pose, position, scale, lighting and camera exactly. Keep the original background untouched. Keep the character's design exactly as in the second image: same pieces, same colours.

This shows how the composite mode should look. Use it to judge lighting and contact shadows.

## Paint-over critique
Refs: a render frame (first) and `concept/restaged.png` (second).
> The first image is a 3D render; the second is the art direction. Repaint the first image to match the art direction's quality and mood while keeping its exact composition, camera, pose and every object's position. Improve materials, lighting, colour and small details only.

Then compare the paint-over with the render yourself, list the concrete differences (for example: "rim light from back-left", "armour has panel lines", "ground has tufts"), and fix the code.

## Omni Flash reference video
Inputs: `--image concept/restaged.png`, plus `--ref-video ref.mp4 --ref-start <s>` to borrow the original motion feel (3 s maximum).
> Animate this still as a <duration> shot from a stylized 3D film. The character moves like the person in the reference clip: <describe the action>. Camera: <e.g. slow dolly alongside at hip height / static / slow push-in>. Keep the character's design and the world consistent. No cuts.

Mine it for **beats**: camera path, timing, effects such as dust, sparks, or light changes. Ignore its anatomy.
