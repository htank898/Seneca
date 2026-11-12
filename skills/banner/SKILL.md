---
name: banner
description: Design static profile and page banners as HTML/CSS and export them as sharp PNGs, such as LinkedIn profile backgrounds, LinkedIn company covers, X/Twitter headers, YouTube channel art, GitHub social previews, and Open Graph link cards. Use whenever someone wants a banner, header image, cover image, or profile background, or wants to update the text or colors on one. Output is a still image, not a GIF; use gif-create only if they explicitly want motion.
---

# AI Banner: profile banners as code

Banner tools hand a human a canvas and a stack of templates. You don't need either. Here you lay the banner out in HTML/CSS at the platform's exact upload size, check it against where the platform covers or crops it, and Chromium screenshots it to a PNG at 2× so it survives the platform's recompression.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it first. A banner is seen for about a second behind someone's photo, so it needs **one idea**: a name and a single line, plus one visual motif that says something specific about the person (their field, their city, their hobbies, the way they work). Stock gradients and generic "tech" line art are the humanoid robot here.

**Personal vs. employer:** a profile banner belongs to the person. Don't borrow an employer's brand colors or logo unless they ask for it; a job title can name the company in plain text.

## 2. Gather only what's missing
Use the defaults in `reference/banner-parameters.md` for anything not stated:
- **Platform**, which sets the size and safe areas. Default: LinkedIn profile.
- **Words**: name, a role or title, and at most one short line. Write the line if they gave you the gist.
- **Motif and palette**: infer from what you know about them. If they have an existing banner, keep what they like about it and change only what they asked for.

## 3. Build
1. Copy `templates/banner-shell.html` to where the output should live (the user's project or the current folder, not inside this skill).
2. Set `window.BANNER` to a preset from `PRESETS` (or a custom `{ width, height, safe }`).
3. Replace the scene CSS and markup inside `#banner`. Author in the platform's upload pixels; the renderer handles the 2× output.
4. Put **every color in a token** on `:root`. Add colorways as `[data-theme="name"]` blocks that redefine only those tokens, so you can show the person a few palettes from one source.
5. Use inline SVG for icons and art. For pixel art, draw `<rect>`s with `shape-rendering: crispEdges`.
6. Open the HTML in a browser to preview (`?theme=name` previews a colorway).

## 4. Render
```bash
node scripts/render-banner.mjs path/to/banner.html --guides
node scripts/render-banner.mjs path/to/banner.html --theme dusk,legal-pad --guides
```
Flags: `--out file.png`, `--scale 2` (output density), `--theme a,b` (one PNG per colorway: `banner.<theme>.png`), `--guides` (also writes `*.guides.png` with the safe areas drawn on top). The first run installs Playwright into this skill folder.

## 5. Verify before reporting
- Look at every `*.guides.png`. Nothing important may sit in a red "keep clear" zone (the avatar covers it), and all text must sit inside the green "keep inside" box.
- Look at the plain PNG at full size: check text contrast against the field, letters that read ambiguously in the chosen face (capital I vs. lowercase l in "AI"), and crowding near edges.
- Check the reported size against the platform limit (the renderer warns).
- Delete the guides PNGs unless the user wants them. Report the PNG path, its pixel size, and which file to upload.
