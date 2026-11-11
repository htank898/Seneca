# Banner parameters

The things a designer checks before making a banner. Platforms change their layouts often, so treat the safe areas as approximate and confirm against the platform's current help page when it matters.

## Sizes and limits

| Preset | Upload size | Ratio | File limit | What covers or crops it |
|---|---|---|---|---|
| `linkedin-profile` | 1584 × 396 | 4:1 | 8 MB, PNG/JPG | Profile photo overlaps the bottom-left. The mobile app shows a little less on the left and right. |
| `linkedin-company` | 1128 × 191 | ~6:1 | 3 MB | Page logo overlaps the bottom-left. |
| `x-header` | 1500 × 500 | 3:1 | 2 MB | Avatar overlaps the bottom-left. Some views crop about 60 px off the top and bottom. |
| `youtube-channel` | 2560 × 1440 | 16:9 | 6 MB | TVs show the whole image. Phones and desktops show only the centered 1546 × 423 strip. |
| `github-social` | 1280 × 640 | 2:1 | 1 MB | Keep about 40 px of border around content. |
| `og-card` | 1200 × 630 | 1.91:1 | ~5 MB | Some apps crop to a centered square. |

## Output density
- Render at `--scale 2` by default. Platforms recompress uploads, and starting from 2× keeps text edges clean. A 2× LinkedIn banner (3168 × 792) is usually under 1 MB with flat fills.
- Drop to `--scale 1` if a platform rejects the size or the file goes over the limit.
- Prefer PNG. Flat colors and text compress well and stay crisp. Photographic backgrounds are the exception: they're smaller as JPG.

## Composition
- **One idea.** Name, a role, and at most one short line. A banner is glanced at, not read.
- **Mind the avatar.** On LinkedIn and X the person's photo sits over the bottom-left. Keep that corner quiet; it's a good place for empty field color.
- **Type sizes at 1584 wide:** name 72–96 px, role 26–32 px, supporting line 22–26 px. Anything under about 18 px won't survive the mobile view.
- **Contrast:** body text against the field at 4.5:1 or better, large display text at 3:1 or better.
- **Ambiguous letters:** in many grotesks a capital I matches a lowercase l, so "AI" can read as "Al". Check the rendered PNG. If it reads wrong, use a face with a serifed I, a font feature that enables one (if the loaded font has it), or a little extra tracking.

## Color
- Keep every color in a token and build colorways with `[data-theme]`. Showing a person two or three palettes from one source beats asking them to describe a palette.
- A personal banner should look like the person, not their employer. Steer clear of employer brand colors unless asked.
- Four to six colors is plenty: a field, an ink, a muted ink, one accent, and a soft tint of the accent.
