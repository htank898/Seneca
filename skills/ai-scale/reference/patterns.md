# Scale patterns

How to make a number felt. Each pattern has a **ruler** (something the viewer already knows in their body), a **camera move**, and a **payoff** (the stop that makes people say "wait, what?").

## Principles
1. **Start at human scale.** Open with something the viewer can see next to themselves: their own height, today's date, one sheet of paper. The anchor ("You") stays on screen even when it shrinks to a dot.
2. **One ruler per piece.** Don't switch from bills to football fields mid-story. Landmarks are signposts along one ruler, not new rulers.
3. **Powers of ten, held long enough.** Each stop is ×10 (or a meaningful jump). The *camera* zooms smoothly in log steps, but every frame is drawn to a true linear scale, so distances on screen are honest. Hold each stop at least 1.6 s so the caption can be read.
4. **Compare to the neighbors.** "Taller than X, short of Y" beats a bare number. The calculator writes these captions. Keep the structure when you reword them.
5. **Linear in the thing you measure.** Show quantity as length (stack height, time distance). Never scale an icon's *area* or *volume* by the number, because people read area as ×10 when it's ×100.
6. **Say the assumptions.** Bill thickness, 365.25-day years, "approximate". Put them in `note`.
7. **Payoff last, then reset.** End on the most absurd stop. The loop resets with a fast zoom back to the start, which also works as a "rewind" for the viewer.
8. **Nothing overlaps, ever.** Each stop shows only what it compares (the nearest landmark below and above), in fixed lanes, crossfading between stops. Anything that would still collide fades out before it touches. The engine enforces this, and `check-overlaps.mjs` verifies it.
9. **Stable positions in motion.** An element's lane or row is assigned once and never recomputed from its neighbors frame to frame. Reflowing is what makes icons jitter and clip.
10. **Correct the premise kindly.** If the user's intuition is off ("$1T gets you to the dinosaurs"), show the real answer and add a stop that reaches their target (about $2.1 quadrillion for the dinosaurs). The surprise *is* the content.

## Patterns

### Stack it (tower)
Use for money, debt, budgets, market caps, counts of flat things.
- **Ruler:** a physical unit (a $100 bill is 0.11 mm thick, so $1M is 1.09 m). Use `--unit`.
- **Camera:** zooms out on a log scale as the stack grows. Landmarks fade in as they enter the frame and fade out as they shrink to nothing.
- **Payoff:** the stack passes the sky, then space. $1T ≈ 1,090 km, past the Space Station.
- **Variants:** the US national debt (`--amounts 1e6,1e9,1e12,3.6e13`; one number alone has no journey, so lead up to it from human scale), a company's revenue against yours, population as a stack of people (add a unit: 0.25 m per person lying down).

### Walk it back (timeline)
Use for any amount that can be turned into time: $1 per second, heartbeats, seconds alive, page views per second.
- **Ruler:** seconds → dates. The calculator writes the date and "Before X. After Y."
- **Camera:** a *linear* time axis with "Now" pinned at the right. Each leg is two beats: the camera zooms out until the last trip is a sliver next to Now, then the traveler runs the new leg at that scale. A bracket labels the leg's length. Never use a log time axis for this pattern, because it makes every leg look like the same walk and hides the point. Events light up as the traveler passes them, and fade when they crowd near Now.
- **Pace: feel the time, don't just read it.** The traveler runs at a set pace shown on screen ("Pace: 1 second = 461 years"), so a longer leg takes longer to *watch*. Each leg starts at the previous leg's pace, says what waiting would cost ("At this pace, this leg would take 62 seconds"), then visibly speeds up ("Speeding up ×7"). Leg run time grows from `pace.first` by `pace.growth` per leg up to `pace.max` seconds, so a ×10 jump always *feels* longer than the one before, while staying watchable. The wait is the point, so don't shorten it into a quick hop. To make a shorter cut, drop stops instead.
- **Payoff:** a deep-time event (Ice Age, dinosaurs, Earth forming). Add a step that reaches it if the user's numbers fall short.
- **Variants:** "your lifetime in seconds", "how long to count to a billion", "a trillion seconds".

### Double it (doubling)
Use for exponential growth: folding paper, compound interest, viral spread, rice on a chessboard, Moore's law.
- **Ruler:** the starting size, doubled each step. `--start-m`, `--target`, `--label` ("Fold", "Day", "Year").
- **Camera:** fast through dull steps (0.2 s), pausing only when a landmark is crossed. The rhythm *is* the lesson: slow, slow, slow, then suddenly past the Moon.
- **Payoff:** how *few* steps it takes (42 folds to the Moon).
- **Variants:** money at 7% doubling roughly every 10 years (label "Decade"), a lily pad covering a pond (custom heights), viral reach (use a unit of people).

### Compare two magnitudes (tower with two scenes, or one scene's steps)
For "how much bigger is A than B" (a billionaire vs the median household, the Sun vs the Earth), make one stop per item on the same ruler. If the ratio is extreme (over 10⁴), let the camera do the work. Don't draw them side by side at one scale, because the small one disappears.

### Odds and fractions (custom)
For "1 in a million": a grid of dots where one is highlighted, with the camera zooming out from one dot to the full field. Build it as a custom scene with the same conventions as the engine (a pure `renderFrame(t)`, a HUD with headline, sub and caption, a log camera). For areas, compare *side length* (the square root), labeled as such.

### Speed and rates (timeline or custom)
"Light reaches the Moon in 1.3 s, the Sun in 8.3 min": a race on a log distance axis with runners for sound, a jet, a bullet, and light. Turn rates into time-to-cover-a-distance, then use the timeline conventions.

## Formats
| Output | When | How |
|---|---|---|
| MP4 (1080×1350 or 1080×1920) | LinkedIn, Reels, Shorts, Slack | `ai-gif` renderer with `--mp4 --mp4-loops 1` |
| GIF (half size) | README, chat, email | `--scale 0.5 --fps 20 --colors 128` |
| Interactive HTML | Teaching or exploring, sent as a file | `build.mjs` output, as-is |
| PNG stills | Slides, docs, a carousel post | `render-steps.mjs`, then put them in `ai-slide-deck` (one stop per slide) |

For a narrated version, pair it with `ai-video` (if installed). Each stop's caption is the voice-over line.
