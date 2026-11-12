---
name: graphic
description: Design static graphics in HTML/CSS/SVG and export them as pixel-exact PNG (or JPG) at any size, such as LinkedIn/X/YouTube banners, social posts, link-preview (OG) images, thumbnails, avatars, headers, wallpapers, app icons, emoji, stickers, and one-off graphics in any aspect ratio. Can export several sizes of one design at once and supports transparent backgrounds. Use whenever someone wants a "banner", "header", "cover image", "graphic", "image for a post", "thumbnail", "PNG of X", or "make me a graphic", instead of reaching for Canva or Photoshop. Use ai-gif if it should move, and ai-pdf if it's a printable document.
---

# AI graphic: static images as code

A design tool makes a human nudge layers around a canvas. You don't need to. Here you lay out the graphic in HTML/CSS/SVG on an artboard of exact pixel size, with platform crop and overlay guides built in. Then Chromium screenshots it to a PNG.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it first: one bold idea, a deliberate palette, a type pairing, and a shape language that fits the person or brand. If it isn't available, choose those yourself. Stock gradients, generic icons, and centered-text-on-a-blur are the "humanoid robot" here.

## 2. Gather only what's missing
Infer what you can and use the defaults in `reference/graphic-parameters.md`:
- **Destination**, which sets the size. Pick a preset (`linkedin-banner`, `og-image`, `youtube-thumbnail`, `avatar`, …) or use any custom size.
- **Message**: the one thing someone should take in at a glance. Write the copy if they gave you the gist.
- **Assets**: the logo, headshot, or brand colors, if they have them. Ask only for facts and files you can't invent.
- **Variants**: if the same design is going to several places, make one artboard per size in the same file.

## 3. Build
1. Copy `templates/graphic-shell.html` to the output location (not inside this skill).
2. Make one `<section class="artboard">` per image, with `data-preset="…"` or `data-w`/`data-h`, plus `data-name` for the filename. Add `data-transparent` for a transparent background.
3. Design inside the artboard in its own pixel coordinates: absolutely positioned DOM, inline SVG, CSS gradients/masks, or `<img>` for the user's assets (relative paths). Don't edit the harness script or the preset table. Add custom sizes with `data-w`/`data-h`.
4. Open the HTML in a browser to preview. Every artboard is shown scaled to fit, with a size label. Press **g** to toggle the platform guides: the green dashed box is where content should stay, and red marks what the platform covers or crops.

## 4. Render
```bash
node scripts/render-png.mjs path/to/graphic.html --scale 2 --guides
```
This writes `<name>.png` for each artboard and, with `--guides`, `<name>.guides.png` with the overlays drawn on for checking.
Flags: `--out-dir`, `--only name1,name2`, `--scale 2` (retina; the default is 1), `--jpg`, `--quality 90`, `--guides`, `--budget-mb 5`.
The first run installs Playwright into this skill folder.

## 5. Verify before reporting
- **Nothing overlaps.** No text sits on other text or on an icon, and no element clips another or the frame edge. When things crowd, fade the less important one out or move it to the side. Never let them collide. Check every PNG, including the `.guides.png`, for this before reporting.
- Look at every `.guides.png`. No text, face, or logo should sit under a red area or outside the green box. Then look at the clean PNG for clipping, contrast, misaligned elements, and fonts that didn't load (a fallback system font is the giveaway).
- Look at the image at small size too (how it shows in a feed or link preview). The headline should still read.
- Delete the `.guides.png` files unless the user wants them. Report each image path, its pixel size, and its file size.
