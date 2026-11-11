# Third-party notices

This repository's own code is MIT licensed (see `LICENSE`). The skills install and run the open-source tools below on your machine. None of them are copied into this repository. Each is free to use commercially.

| Component | Used by | License | Source |
|---|---|---|---|
| Playwright | every skill (headless Chromium) | Apache-2.0 | https://github.com/microsoft/playwright |
| FFmpeg | ai-gif, ai-math, ai-interactive-guide, ai-video-edit | LGPL-2.1+ (GPL in some builds) | https://ffmpeg.org |
| Manim Community | ai-math | MIT | https://github.com/ManimCommunity/manim |
| ManimPango | ai-math (via Manim) | MIT; its bundled Pango/Cairo binaries are LGPL | https://github.com/ManimCommunity/ManimPango |
| pycairo | ai-math (via Manim) | LGPL-2.1 or MPL-1.1 | https://github.com/pygobject/pycairo |
| PyAV | ai-math (via Manim) | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| Typst (Python package) | ai-math (Manim equations) | Apache-2.0 | https://github.com/messense/typst-py |
| KaTeX | ai-math (`typeset.mjs`) | MIT | https://github.com/KaTeX/KaTeX |
| Tectonic | ai-math (`latex-pdf.mjs`) | MIT | https://github.com/tectonic-typesetting/tectonic |
| TeX Live packages fetched by Tectonic | ai-math (`latex-pdf.mjs`) | LPPL and other free licenses, per package | https://tug.org/texlive |
| faster-whisper | ai-video-edit (`transcribe.py`) | MIT | https://github.com/SYSTRAN/faster-whisper |
| Whisper model weights (`large-v3-turbo`, via the Hugging Face Hub) | ai-video-edit (`transcribe.py`) | MIT | https://github.com/openai/whisper |
| CTranslate2, ONNX Runtime, Hugging Face tokenizers (installed by faster-whisper) | ai-video-edit (via faster-whisper) | MIT; MIT; Apache-2.0 | https://github.com/OpenNMT/CTranslate2 |

**Embedded in outputs:** `ai-math/scripts/typeset.mjs` inlines KaTeX's CSS and fonts into the HTML it writes. KaTeX is MIT licensed, Copyright (c) 2013-2020 Khan Academy and other contributors. The inlined stylesheet keeps that notice in a comment. No other third-party code is embedded in generated files.
