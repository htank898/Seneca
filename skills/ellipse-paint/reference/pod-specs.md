# Print-on-demand specs and Etsy rules

All files are 300 DPI. Pixel sizes are what `pod_export.py` writes. Provider templates change and differ between blank products, so **check mug, hoodie, tote, and any product not listed here against the provider's own template** before uploading. Use `--size WxH` to match a template exactly.

## Wall art (`wall-art` set, JPG)
| Preset | Pixels | Prints sharply at |
|---|---|---|
| poster-2x3 | 7200×10800 | 24×36 in., and every 2:3 down from it: 4×6, 8×12, 12×18, 16×24, 20×30 |
| poster-3x4 | 5400×7200 | 18×24 in.; 6×8, 9×12, 12×16 |
| poster-4x5 | 4800×6000 | 16×20 in.; 8×10, 4×5 |
| poster-11x14 | 3300×4200 | 11×14 in. |
| poster-iso | 7016×9933 | A1; A2–A5 by scaling |

- **Digital downloads:** Etsy allows up to 5 files per digital listing, at 20 MB each. These five ratios cover almost every frame a buyer owns. The exporter steps JPG quality down until each file fits under 20 MB.
- **Physical posters through a provider:** upload the ratio that matches the product. Full-bleed products need about 0.125 in. of bleed, which the cover crop already provides, but keep important content away from the outer ~2% of each edge.

## Apparel (`apparel` set, transparent PNG)
- **tee / hoodie: 4500×5400** (15×18 in.). This is Printify's common front-print file. Printful's standard front area is 12×16 in. (3600×4800): export with `--size 3600x4800 --fit contain` or let Printful scale it down.
- **DTG printing:**
  - Semi-transparent pixels get dithered, so use `--flatten-alpha` if the warning fires.
  - Near-black disappears on black garments and near-white on white ones. The exporter measures both.
  - Hoodies have a pocket zone, so keep the lower third light or empty on hoodie fronts.

## Mugs (`mug` set)
- **mug-11oz: 2700×1050** (a 9×3.5 in. wrap). The art is placed twice, centred on each side of the handle. Printify and Printful templates vary slightly by blank, so check the template and use `--size` if it differs.

## Stickers (`stickers` set)
- **sticker-3in / 4in / 5.5in:** 900 / 1200 / 1650 px squares. Transparent, with a white die-cut outline about 3% of the width.
- The cut line follows the outline. Very thin parts such as antennae or tails get bridged by the outline, which is intended.

## Etsy listing rules that affect this work (re-check Etsy's current policy pages before launch)
- **AI disclosure:** Etsy's Creativity Standards allow seller-designed items made with the help of AI tools. Say in the description that the design was created with AI tools. The Gemini `log.json` and the `art.json` meta show the process if Etsy ever asks.
- **Production partner:** for physical POD items, the provider (Printify, Printful, Gelato, ...) must be added as a production partner on the listing.
- **Listing limits:**
  - Title: up to 140 characters
  - Tags: 13, each up to 20 characters
  - Video: 5–15 s, played without sound
  - Photos: up to 20, with at least 2000 px on the shortest side recommended
- **Intellectual property:** no trademarks, brands, franchise characters, sports teams, celebrities' likenesses, or song lyrics. Prompting "in the style of" a living artist is also risky. Takedowns for these can close a shop.
