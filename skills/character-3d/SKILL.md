---
name: character-3d
description: Turn a character image (AI-generated or drawn, plus optional back/side views) into a detailed, textured, Rigify-rigged 3D character ready to animate in Blender. Runs entirely on this Mac with local models, no external API: TRELLIS.2 (MIT) builds the mesh, BiRefNet (MIT) cuts out the background, and Blender fits and skins the rig. Use for "make this character 3D", "turn my character art into a model", "image to 3D", "rig this character", "I want to animate my character in Blender", or when a GLB from another generator needs cleaning and rigging.
---

# AI Character: image → rigged 3D character, all local

A character image becomes a textured mesh, then a Blender character with a full Rigify rig (IK/FK arms and legs, torso, neck, head). It's ready to pose and animate, or to drive with `animate`.

```
front.png (+ back/left/right) ──prep──▶ cut-outs ──TRELLIS.2──▶ raw.glb ──rig──▶ character.blend
                                    BiRefNet                     (PBR)         + character_rigged.glb
```

Paths below are relative to this skill's base directory. It reuses `../blender/scripts/blender.mjs` to run Blender headless. Requires Blender, Node, `uv`, and an Apple Silicon Mac.

## 0. One-time setup
```bash
bash scripts/setup.sh --check     # report only
bash scripts/setup.sh             # install the engine + prefetch weights (idempotent)
```
- Installs into `~/.cache/seneca/char3d/` (`$SENECA_CHAR3D_HOME`), never into the repo: the TRELLIS.2 Apple-Silicon port (`trellis-silicon`, pinned commit) with its own venv, plus about 11 GB of weights for the 512 pipeline only. Needs about **17 GB free**; if space is short, use the `icloud-offload` skill.
- **Hugging Face login** is needed once, for Meta's gated **DINOv3** image encoder, which TRELLIS.2 conditions on. Create a read token, request access at huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m (usually instant), then run `hf auth login` (install the CLI once with `uv tool install huggingface_hub`). The setup script prints these steps when they're missing. Never ask for the token in chat.
- **Memory:** the 512 pipeline peaks around 17–18 GB of unified memory. On a 16 GB Mac it swaps and slows down. Close browsers and Electron apps before generating, and expect 5–20 minutes. 24 GB or more runs in about 3 minutes.
- **No Metal compiler** (Command Line Tools only, no Xcode): setup continues, and the Metal extensions that fail to build fall back to slower PyTorch/CPU paths.

## 1. Get good input images
How the image was made matters more than anything downstream. Read `reference/input-guide.md` before generating character art. In short: **full body, neutral A-pose** (arms 30–45° out, clear of the torso), feet shoulder-width apart, flat even light, plain background, orthographic-looking camera at chest height. Back and side views should come from the **same** generation session or character sheet, so the outfit matches.

## 2. Build it
```bash
node scripts/char3d.mjs front.png --out <dir> [--back back.png] [--left left.png] [--right right.png]
```
- `--height 1.8`: real-world height in metres. Use about 1.0–1.2 for a chibi or a child, and 2.2 for a giant.
- `--seed N --regen`: generate a different mesh from the same image (the first try isn't always the best).
- `--steps 8`: faster and rougher. `--texture 2048` gives a sharper texture.
- `--mesh some.glb`: skip generation and clean and rig any GLB you already have, from TRELLIS, Hunyuan, a sculpt, and so on.
- Re-runs reuse `raw.glb`, so tweaking the rig never re-generates.

Side views: `--left` is the view of the character's **left** side, so in the image the character faces image-left. `--right` faces image-right. `--back` is from behind. These views are projected onto the surfaces they see head-on and baked into the texture. Turn that off with `--project 0`.

## 3. Look before you hand it over
Open these with the Read tool, every time:
- `check_bones.png`: deform bones drawn over the ghosted mesh. **Elbows and knees at the bends, wrists at the narrowing, shoulders inside the shoulder, hips inside the pelvis, the spine up the middle into the head.**
- `check_pose.png`: arm raised, knee lifted. Look for tearing, a candy-wrapper twist at the wrists or shoulders, a body part dragged by the wrong bone (a hand pulling the thigh, hair pulled by the shoulder).
- `check_front.png`, `check_back.png`, `check_three_quarter.png`: the mesh itself. Look for missing limbs, a mushy back, holes, or a texture painted onto the wrong side.
- Read the `[prep] warning` and `[rig] warning` lines too. They flag a closed pose, joined legs, or failed weights.

| Problem | Fix |
|---|---|
| Character faces backwards or sideways | `--facing +Y` (or `-X`, `+X`): the side the character faces in raw.glb |
| Mesh is a blob, limbs fused | new image in a clearer A-pose; or `--seed 7 --regen` |
| Joints misplaced | check the pose in the image first; `landmarks.json` shows what was found |
| A hand moves the thigh, or hair follows an arm | gaps in the mesh closed up in the weight proxy: `--voxel 0.004` (finer) or `--weights direct` |
| Back texture smeared or wrong | give `--back`; if the back view doesn't match the front, `--project 0` |

## 4. Animate
`character.blend` contains `Character` (the mesh, skinned with an Armature modifier), `rig` (the generated Rigify rig: IK by default, an FK switch on each limb under the rig's Item tab), and a hidden `FrontRef` plane with the source image. Open it in Blender (`--open`) and animate the controls, or script it:
- **Render it:** `blender`'s `bkit` lights, cameras, and turntables work on this file. Use `bpy.ops.wm.open_mainfile`, then add the shot.
- **Motion from video:** `animate` captures a performance. `landmarks.json` records this character's joints in the same frame as `animate`'s `rig.py` (facing -Y, left = +X, metres).
- **Game engines / web:** `character_rigged.glb` carries the deform skeleton and skin weights.

## Limits (say so when they bite)
- The geometry comes from the **front image only**. Back and side views fix colour, not shape.
- Fingers usually come out fused, so each hand is **one bone**, with no finger or face rig. Faces animate with shape keys if needed.
- Long skirts, robes, capes, and tails get no dedicated bones. They follow the legs or spine.
- View projection has no occlusion test: a part hidden behind another in a view can pick up that view's colour.

## Licences
Everything that runs is local. TRELLIS.2 and its Mac port (all MIT), BiRefNet (MIT), and Blender/Rigify (GPL, which doesn't apply to your outputs) are fine for commercial use. **DINOv3** weights are under Meta's own gated licence, not MIT; review it before commercial use. **RMBG-2.0** (non-commercial), which TRELLIS.2 ships with by default, is never downloaded: `generate.py` swaps in BiRefNet. See `THIRD_PARTY_NOTICES.md`.
