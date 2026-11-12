# Seneca

[Claude Code](https://claude.com/claude-code) skills that build communication artifacts in HTML, CSS, and JavaScript (and Blender, for 3D), then render them to PDF, PNG, GIF, or MP4. A front door, `/seneca`, reads the audience and the moment, picks the formats that fit, and builds them as one package in one visual style.

## Skills

| Skill | What it makes | Output |
|---|---|---|
| **seneca** | Reads the audience and moment, picks the formats, builds them in one visual style | Any of the below |
| **slides** | Presentation decks with transitions, builds, speaker notes, and an overview grid | `.html` + `.pdf` |
| **pdf** | Letters, invitations, itineraries, one-pagers, and reports on custom stationery | `.pdf` |
| **graphic** | Static graphics at any size: social posts, OG images, thumbnails, avatars, stickers | `.png` / `.jpg` |
| **banner** | Profile and page banners (LinkedIn, X, YouTube, GitHub) checked against avatar and crop zones | `.png` at 2× |
| **gif-create** | Looping motion graphics, with optional sound effects and chalkboard callouts over scenes or real footage | `.gif` + `.mp4` |
| **interactive-guide** | Click-through software walkthroughs on a rebuilt replica of the app | `.html` + `.gif` |
| **math** | Manim animations, KaTeX equations inside any other format, and LaTeX documents | `.mp4` / `.gif` / `.html` / `.pdf` |
| **video-create** | Narrated videos with a local Kokoro voice-over and captions | `.mp4` + `.vtt` / `.srt` |
| **video-edit** | Talking-head edits with overlays timed to what's said (local Whisper transcription) | `.mp4` + `edit.json` |
| **blender** | 3D scenes from headless Blender scripts: product shots, logo renders, turntables | `.png` / `.mp4` / `.blend` / `.glb` |
| **character-3d** | A character image (plus optional back and side views) turned into a textured, Rigify-rigged 3D model, all local | `.blend` + `.glb` |
| **animate** | Bodies that move: ready-made clips chained into a performance (Quaternius CC0, your Mixamo downloads), mocap/BVH retargeting, a gait library (CMU, 100STYLE), motion capture from video, statistical motion models, sports actions | `.mp4` + `.bvh` |
| **adapt** | Real footage restaged in 3D: the captured performance drives a character and world built in Blender, with Gemini concept art as the target | `.mp4` + `.blend` |

Each skill gives Claude a reference sheet of the parameters a professional would think about (form factors, safe areas, type scales, paper sizes, loop timing, file-size budgets) and a render script that turns the source into the final file.

## Install

As a plugin:

```
/plugin marketplace add https://github.com/htank898/Seneca.git
/plugin install seneca@seneca
```

Plugin skills are namespaced (`/seneca:seneca`, `/seneca:slides`, …). For a bare `/seneca`, copy `shortcut/seneca` into `~/.claude/skills/`. Or skip the plugin and copy `skills/*` into `~/.claude/skills/`.

## Requirements

- **Everything:** Node 18+ and `ffmpeg`. Each skill installs its own Playwright on first render.
- **Python tools:** [`uv`](https://docs.astral.sh/uv/) for Manim (`math`), Whisper (`video-edit`), Kokoro (`video-create`), and MediaPipe pose capture (`animate`, `adapt`). Each builds a private Python env on first use.
- **LaTeX PDFs:** `tectonic` (`math`).
- **3D:** Blender for `blender`, `character-3d`, `animate`, and `adapt`.
- **`adapt`:** `GEMINI_API_KEY`, used only for the concept-art stages.
- **`character-3d`:** an Apple Silicon Mac, ~17 GB of disk for the one-time engine install (`skills/character-3d/scripts/setup.sh`), and a free Hugging Face login for the gated DINOv3 weights. 24 GB+ of memory is recommended.

## Usage

Describe the situation and let Seneca choose:

> /seneca Budget review with the CFO and two VPs on Thursday. Here are the numbers.

Or name a format and that skill runs directly:

> Make a 6-slide status deck on the Q3 migration, answer first.

Examples made with the skills are in [`examples/`](examples).

## License

MIT. Third-party tools the skills install are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
