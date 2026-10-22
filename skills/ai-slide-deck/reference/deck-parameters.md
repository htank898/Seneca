# Deck parameters

## Form factors
| Ratio | `data-width × data-height` | When |
|---|---|---|
| 16:9 | 1920 × 1080 | Default: screens, projectors, video calls |
| 4:3 | 1600 × 1200 | Older rooms and projectors, print handouts |
| 9:16 | 1080 × 1920 | Phone-first viewing, stories |
| 1:1 | 1080 × 1080 | LinkedIn document carousels (export the PDF and upload it as a document) |
| 4:5 | 1080 × 1350 | Instagram/LinkedIn portrait carousels |

## Safe area and spacing (16:9 at 1920)
- **Edge padding (`--pad`):** 6% of width (about 115px). Never place text closer than 4%.
- Leave the bottom 60px clear on live decks, since the progress bar and counter sit there.
- **Vertical rhythm:** spacing in multiples of 8px; generous section gaps (64–120px).
- **Grid:** a 12-column grid with about 40px gutters. Two-column layouts use 5/7 or 6/6, not 50/50 with a skinny gap.

## Type scale (at 1920 wide; scale proportionally for other sizes)
| Role | Size | Notes |
|---|---|---|
| Display (title, statement) | 96–160px | A tight leading of 0.95–1.05 |
| Slide headline | 60–80px | Write it as a sentence that states the takeaway |
| Subhead | 40–48px | |
| Body / bullets | 32–40px | **Minimum 28px.** If it doesn't fit at 28px, split the slide. |
| Caption / source | 22–24px | |
- Readable from the back of a room is about 28px at 1080p. For async decks you can go down to 24px for body text.
- Use at most 2 typefaces. Display faces with personality, plus a highly legible sans for body text.

## Density
- **One idea per slide.** The headline states the takeaway, and the body supports it.
- **Live decks:** ≤ 25 words on screen, with the rest in speaker notes.
- **Async (send-ahead) decks:** ≤ 60 words, and headlines must tell the whole story when read in sequence.
- Bullets: max 4, max 2 lines each. Prefer a diagram, number, or comparison over a bullet list.
- Don't let any layout repeat more than twice in a row.

## Layout archetypes
`title`, `section` break, `statement` (one big sentence), `split` (text + visual), `number` (one huge stat), `quote`, `comparison` (before/after, us/them), `timeline`, `grid` (3–6 cards), `chart`, `diagram`, `agenda`, `closing / CTA`. Build new ones as needed and give each a `layout-*` class.

## Transitions and builds
- **Default `fade`** (600ms). Use `slide` for sequential narrative, `zoom` to dive into a detail, `rise` for statements, and `none` for rapid-fire sequences.
- At most 2 transition types per deck. Motion should signal structure, not decorate.
- **Builds (`data-build`):** use them for reveals that the speaker talks through: lists, step-by-step diagrams, and the punchline of a comparison. Don't build every slide.
- `prefers-reduced-motion` is respected automatically.
- **Custom animation:** CSS keyframes on `.slide.active .thing` run each time the slide is entered.

## Communication modes
| Mode | Slides | Structure | Notes |
|---|---|---|---|
| Pitch / proposal | 8–12 | Problem, why now, solution, how it works, proof, plan, ask | End on a concrete ask with owner and date |
| Training / workshop | 12–30 | Objectives, concept, example, practice, recap, resources | Use builds for step-by-step work; include a recap slide per module |
| Status update | 4–7 | Headline status (RAG), progress vs plan, risks and asks, next steps | Put the answer first. Busy readers stop after slide 2. |
| Narrative keynote | 15–40 | Hook, tension, turn, resolution, call to action | Mostly statement and number slides; heavy speaker notes |
| Data readout | 6–12 | Key finding, supporting charts, so-what, recommendation | One chart per slide, annotated with the insight in the headline |

## Charts and diagrams
- Draw charts from the actual numbers with inline SVG (or CSS for simple bars). Label data directly; skip legends when possible.
- Highlight the one series or bar that carries the message in the accent color, and mute everything else.
- Diagrams: boxes and arrows in SVG with consistent stroke widths. Give each step its own `data-build` to walk through it.

## Accessibility
- Text contrast ≥ 4.5:1 (≥ 3:1 for text 48px and up).
- Don't use color as the only signal. Pair it with labels or icons.
- Keep the DOM in reading order. Headings use `h1`/`h2`.
- Speaker notes double as a transcript for people who receive the deck async.

## Sharing
- **Live:** open the HTML in a browser and press `F`.
- **Send:** attach the PDF, or host the HTML (any static host works), since it's one file.
- **LinkedIn carousel:** build at 1:1 or 4:5, export the PDF, and upload it as a document post.
