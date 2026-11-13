# Third-party notices

This repository's own code is MIT licensed (see `LICENSE`). The skills install and run the open-source tools below on your machine. None of them are copied into this repository. Each is free to use commercially, except where noted below (DINOv3, used by `character-3d`, has its own license).

| Component | Used by | License | Source |
|---|---|---|---|
| Playwright | every skill (headless Chromium) | Apache-2.0 | https://github.com/microsoft/playwright |
| FFmpeg | gif-create, math, interactive-guide, video-edit | LGPL-2.1+ (GPL in some builds) | https://ffmpeg.org |
| Manim Community | math | MIT | https://github.com/ManimCommunity/manim |
| ManimPango | math (via Manim) | MIT; its bundled Pango/Cairo binaries are LGPL | https://github.com/ManimCommunity/ManimPango |
| pycairo | math (via Manim) | LGPL-2.1 or MPL-1.1 | https://github.com/pygobject/pycairo |
| PyAV | math (via Manim) | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| Typst (Python package) | math (Manim equations) | Apache-2.0 | https://github.com/messense/typst-py |
| KaTeX | math (`typeset.mjs`) | MIT | https://github.com/KaTeX/KaTeX |
| Tectonic | math (`latex-pdf.mjs`) | MIT | https://github.com/tectonic-typesetting/tectonic |
| TeX Live packages fetched by Tectonic | math (`latex-pdf.mjs`) | LPPL and other free licenses, per package | https://tug.org/texlive |
| faster-whisper | video-edit (`transcribe.py`) | MIT | https://github.com/SYSTRAN/faster-whisper |
| Whisper model weights (`large-v3-turbo`, via the Hugging Face Hub) | video-edit (`transcribe.py`) | MIT | https://github.com/openai/whisper |
| CTranslate2, ONNX Runtime, Hugging Face tokenizers (installed by faster-whisper) | video-edit (via faster-whisper) | MIT; MIT; Apache-2.0 | https://github.com/OpenNMT/CTranslate2 |
| MediaPipe + Pose Landmarker model | animate (`pose.py`) | Apache-2.0 | https://github.com/google-ai-edge/mediapipe |
| OpenCV (`opencv-python-headless`), NumPy | animate (`pose.py`) | Apache-2.0; BSD-3-Clause | https://github.com/opencv/opencv-python |
| CMU Graphics Lab Motion Capture Database (BVH conversion by B. Hahne, mirrored by una-dinosauria/cmu-mocap) | animate (`gait.py`, fetched on demand) | Free for any use; CMU asks for the acknowledgement "The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217." | http://mocap.cs.cmu.edu |
| 100STYLE locomotion dataset (Ian Mason) | animate (`gait.py`, downloaded on request) | CC BY 4.0: credit "The 100STYLE Dataset - Ian Mason" in any work that uses it | https://www.ianxmason.com/100style/ |
| resvg (via the `resvg-py` binding), NumPy, Pillow | ellipse-paint (SVG rendering and raster export) | resvg: Apache-2.0 OR MIT; resvg-py: MIT; NumPy: BSD-3-Clause; Pillow: MIT-CMU | https://github.com/linebender/resvg |

**character-3d** installs these into `~/.cache/seneca/char3d/`, outside the repository:

| Component | Used by | License | Source |
|---|---|---|---|
| TRELLIS.2 (code and `TRELLIS.2-4B` / `TRELLIS-image-large` weights) | character-3d (`generate.py`) | MIT | https://github.com/microsoft/TRELLIS.2 |
| trellis-silicon (Apple Silicon port of TRELLIS.2) | character-3d (`setup.sh`, pinned commit) | MIT | https://github.com/sanchez-kim/trellis-silicon |
| mtlbvh, mtldiffrast, mtlmesh, mtlgemm, trellis2-apple (Metal backends, installed by trellis-silicon) | character-3d (via trellis-silicon) | MIT | https://github.com/pedronaugusto |
| utils3d | character-3d (via trellis-silicon) | MIT | https://github.com/EasternJournalist/utils3d |
| BiRefNet (code and weights) | character-3d (`prep.py`, and TRELLIS.2's background remover) | MIT | https://github.com/ZhengPeng7/BiRefNet |
| DINOv3 ViT-L/16 weights (gated on the Hugging Face Hub) | character-3d (TRELLIS.2 image encoder) | Meta DINOv3 License: a custom license, **not** MIT. Review its terms before commercial use | https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m |
| PyTorch, Hugging Face transformers / hub (installed by trellis-silicon) | character-3d | BSD-3-Clause; Apache-2.0 | https://github.com/pytorch/pytorch |
| Rigify (bundled with Blender) | character-3d (`rig_character.py`) | GPL-2.0+; the license covers Rigify itself, not the rigs it generates | https://projects.blender.org/blender/blender |

TRELLIS.2's default background remover, BRIA **RMBG-2.0**, is CC BY-NC 4.0 (non-commercial). `character-3d` never downloads it: `generate.py` replaces it with BiRefNet before the pipeline loads.

**Embedded in outputs:** `math/scripts/typeset.mjs` inlines KaTeX's CSS and fonts into the HTML it writes. KaTeX is MIT licensed, Copyright (c) 2013-2020 Khan Academy and other contributors. The inlined stylesheet keeps that notice in a comment. No other third-party code is embedded in generated files.

**Opt-in, not commercial:** `animate` documents ExMR (https://github.com/twehrbein/ExMR) as an optional high-fidelity motion-capture backend. ExMR's code is for educational, research and non-profit use only, and it depends on SMPL-X (Max Planck Institute, non-commercial licence), SAM 3D Body (SAM License) and Ultralytics YOLO (AGPL-3.0). It is never installed or run by default; a BVH it exports is imported like any other.

**Opt-in, not commercial:** `animate`'s `gvhmr.py` runs GVHMR (https://github.com/zju3dv/GVHMR, Shen et al., SIGGRAPH Asia 2024) on a rented RunPod GPU. GVHMR is (c) Zhejiang University 3D Vision Group, licensed for educational, research and non-profit use only; derivatives must stay open-source and non-commercial. Seneca does not include any GVHMR code: the pod clones it from upstream at run time, together with its checkpoints (HMR2.0, ViTPose, Ultralytics YOLOv8 under AGPL-3.0, DPVO) from the authors' download links. It needs the SMPL and SMPL-X body models (Max Planck Institute, non-commercial licences), which each user must download after registering and which Seneca never redistributes. Cite the GVHMR paper in work that uses its output.

**Attribution in outputs:** a video animated from a 100STYLE clip must credit "The 100STYLE Dataset - Ian Mason"; `animate` reminds you in its hand-off. CMU clips need no credit in the video, though CMU appreciates the acknowledgement above.
