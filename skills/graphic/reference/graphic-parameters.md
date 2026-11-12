# Graphic parameters

## Presets
Every preset is in `PRESETS` in the template. Use `data-preset="<name>"`, or `data-w`/`data-h` for any other size.

| Preset | Size | Guides (shown with `g` / `--guides`) |
|---|---|---|
| `linkedin-banner` | 1584×396 | Profile photo covers the bottom-left on desktop. Mobile crops the sides. Keep text inside the central ~1350×220. |
| `linkedin-company` | 1128×191 | Logo covers the bottom-left. |
| `linkedin-post` | 1200×627 | Link-share / landscape feed image |
| `linkedin-square` | 1200×1200 | Takes the most feed space |
| `x-header` | 1500×500 | Profile photo covers the bottom-left. Top and bottom crop on some screens. |
| `x-post` | 1600×900 | |
| `youtube-banner` | 2560×1440 | Only the central 1546×423 shows on every device. |
| `youtube-thumbnail` | 1280×720 | Duration badge covers the bottom-right corner. |
| `facebook-cover` | 1640×624 | Top and bottom crop on mobile. |
| `og-image` | 1200×630 | Link previews (Slack, iMessage, LinkedIn, X). Some crop to 1.91:1 or square, so keep a margin. |
| `github-social` | 1280×640 | Repo social preview |
| `instagram-square` | 1080×1080 | |
| `instagram-portrait` | 1080×1350 | Grid view crops to the central square. |
| `story` | 1080×1920 | Top 250 px and bottom 330 px sit under UI. |
| `avatar` | 800×800 | Cropped to a circle almost everywhere |
| `email-header` | 1200×400 | Shown at 600 wide. Text must read at half size. |
| `slide-16x9` | 1920×1080 | Title cards and slide images |
| `zoom-background` | 1920×1080 | You cover the center. Put content at the edges and top. |
| `desktop-wallpaper` | 2560×1440 | |
| `phone-wallpaper` | 1170×2532 | Clock covers the top third. Dock covers the bottom. |
| `app-icon` | 1024×1024 | iOS masks the corners. Keep the glyph inside the central ~80%. |
| `emoji` | 128×128 | Slack/Discord. Usually needs a transparent background, and it must read at 22 px. |

Platform crops and overlays change, and third-party guides disagree on exact numbers. The guides are deliberately conservative. They're there to keep important content clear, not to give pixel-exact measurements. When it matters, check the real upload on a phone and on desktop.

Anything else (posters, print-style pieces, diagrams, odd aspect ratios) uses `data-w`/`data-h`. For something that will be printed, set the pixel size from inches × 300 (for example 18×24 in becomes 5400×7200). For a document that's mostly text, use `ai-pdf` instead.

## Resolution and format
- **`--scale 2`** for anything shown on high-density screens: banners, headers, thumbnails, and anything with small text. Platforms re-compress uploads, and starting at 2× keeps edges crisp. LinkedIn caps banner uploads at around 8 MB, so a 2× banner (3168×792) is usually fine as PNG.
- **PNG** (default): text, logos, flat color, and transparency.
- **`--jpg`**: photographic or gradient-heavy pieces where PNG gets large. Quality 85–92.
- **Transparent**: add `data-transparent` to the artboard for stickers, emoji, logos, and overlays. PNG only.

## Design rules
- **One message, read in one second.** A banner or thumbnail is seen at a glance and often small. One headline, at most one supporting line, and one visual idea.
- **Type size:** headline ≥ 6% of the short side (≥ 48 px on a 1584×396 banner, ≥ 72 px on 1080 square). Body ≥ 3%. Thumbnails need to read at 25% size.
- **Contrast:** at least 4.5:1 for text. Feeds are light *and* dark, so give the artboard its own background.
- **Edges:** keep ≥ 4% margin from every edge, more where a guide says so.
- **Balance against the UI.** On profile banners the photo sits at the bottom-left, so weight the composition center-right and let the left side be texture or color.
- **Real assets:** use the user's logo/photo files with `<img src="relative/path">`. Never redraw a real company's logo, and don't imitate another brand's identity.
- **Variants:** put several artboards in one file (for example, a banner, a square post and an OG image with the same art) and share CSS variables so they stay consistent.
