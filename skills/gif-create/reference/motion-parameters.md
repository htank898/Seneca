# Motion parameters

## Destinations and sizes
| Destination | Size | Notes |
|---|---|---|
| LinkedIn / X / Instagram feed | 1080×1080 | Square takes the most feed space. LinkedIn also accepts MP4, which is sharper and smaller. |
| Link card, blog header | 1200×628 | |
| Slack, Notion, docs, README | 800×450 or 960×540 | Keep under about 3 MB so it autoplays inline. |
| Story / Reels / TikTok | 1080×1920 | Usually better as MP4. |
| Email | 600 wide | Under 1 MB. Many clients show only the first frame, so make frame 0 meaningful. |

**Size budgets:** social uploads 5 MB, chat 3 MB, email 1 MB. GIF size grows with *changing pixels × frames × colors*.

## Timing
- **Duration:** 3–4 s for a status loop or gag, 5–8 s for an explainer with one punchline. Longer than 10 s is better as MP4.
- **FPS:** 24 is the default. 30 for fast motion. 15–20 is fine for flat, slow, illustrative pieces and roughly halves the size.
- **Hold times:** text ≥ 1.2 s on screen; the final message ≥ 25% of the loop.
- **Beats:** structure every loop as setup, action, payoff, reset. The reset should feel like part of the motion, not a cut.

## Seamless loop patterns
- **Cycles:** `wave(t, n)` and `Math.sin(TAU * t * n)` with integer `n` always loop.
- **Ping-pong:** `pingpong(t)` goes out and back.
- **Sequenced beats:** `seg(t, a, b)` gives local 0..1 progress. End the last beat in the starting pose.
- **Conveyor/marquee:** offset = `t * period`; the content must repeat every `period`.
- **Rotation:** `angle = 360 * t * n` for integer `n`.
- **Particle fields:** precompute positions from a seeded PRNG once, then derive each particle's phase from `t`.

## Easing
- `outCubic` for things arriving, `inCubic` for things leaving, `inOutCubic` for moves.
- `outBack` for UI pops and labels (a small overshoot).
- `outElastic` for comic timing. Use it once per piece at most.
- `linear` only for continuous motion (rotation, conveyors).
- Squash and stretch on impacts, anticipation before a big move, and secondary motion (shadows, wobble) are what make it feel alive.

## Visual rules for GIF
- **Flat color compresses well.** Gradients, blur, glows, photos, and noise cause banding and inflate size. If you need a gradient, keep it subtle and static.
- **Keep the background static.** Moving backgrounds change every pixel on every frame.
- A **256-color palette** applies to the whole GIF. Too many hues will posterize, so design with 3–6 colors.
- **Thin lines (< 2 px)** flicker under dithering. Use ≥ 3 px strokes at 1080.
- **Type:** heavy display weights read best when small. Avoid hairline serifs.
- **Contrast:** assume the feed is in dark *or* light mode. Give the stage its own background.

## Purposes and patterns
- **Explainer:** before/after, or a split-screen comparison. One idea; the payoff is a text line.
- **Visual gag:** setup, then subversion. The joke lands at about 70% of the loop, then a beat to breathe.
- **Status/loading:** 1–2 s, a purely cyclical motion with no text.
- **Logo sting:** build-in, hold, gentle idle motion back to the start.
- **Data animation:** numbers count up with `outCubic`, bars grow in staggered order, and the final state is held for at least 40% of the loop.

## Accessibility
- No flashing more than 3 times per second, and no full-screen strobes.
- Put the message in the post text too, since GIFs have no alt text in many places.
