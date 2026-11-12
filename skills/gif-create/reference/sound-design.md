# Sound design

Sound is synthesized in code with the browser's Web Audio API. There are no audio files, downloads, or licenses, so it works on locked-down corporate machines and networks. GIFs are always silent; sound goes into the MP4.

## How it works
- The template's `sfx-engine` script defines `window.SFX`. Don't edit it.
- The page declares `window.SOUND = { volume, cues: [...] }`. Each cue fires at loop time `t` in `[0, 1)`, the same timeline as `renderFrame(t)`.
- **Preview:** press **M** to turn sound on. Browsers block audio until a key press or click, so it starts muted.
- **Render:** `render-gif.mjs --mp4` renders the cues offline with `OfflineAudioContext`. This works headless and doesn't need speakers or a sound card. The soundtrack covers all `--mp4-loops` loops, so sound tails and early-starting cues carry across the loop seam. `--no-audio` skips it.

## Cues
```js
window.SOUND = {
  volume: 0.8,                                          // master level; a limiter prevents clipping
  cues: [
    { t: 0.15, sfx: "whoosh" },                         // title slides in
    { t: 0.30, sfx: "pop", pitch: 1.2, pan: -0.3 },     // left badge appears
    { t: 0.70, sfx: "riser", dur: 0.8, delay: -0.8 },   // builds up and ends exactly on the punchline
    { t: 0.70, sfx: "impact" },                         // punchline lands
  ],
};
```
| Option | Meaning |
|---|---|
| `t` | Loop time in `[0, 1)`. Use the same numbers as your `seg(t, a, b)` beat boundaries. |
| `sfx` | A preset name, or a custom function (see below). |
| `gain` | Per-cue level, default 1. |
| `pitch` | Frequency multiplier, default 1. 0.5 is an octave down, 2 an octave up. |
| `pan` | -1 (left) to 1 (right). |
| `delay` | Seconds added to the start time. A negative value starts the sound early, so a riser or whoosh can *finish* on the beat. |
| `dur` | Length for `whoosh` and `riser`. |
| `count`, `gap`, `seed` | For `type` and `sparkle`: number of hits, spacing, and the seeded variation. |
| `dir` | `whoosh` only: `"up"` (default) or `"down"`. |

## Presets
| Name | Sounds like | Use for |
|---|---|---|
| `pop` | Short falling blip | Element appears, badge, bubble |
| `bloop` | Short rising blip | Toggle on, item added |
| `click` | Crisp noise click | Button press, cursor click |
| `tick` | Tiny high blip | Counters, list items, clock |
| `type` | Burst of key taps | Text typing on |
| `whoosh` | Filtered-noise sweep | Slides, transitions, things flying in or out |
| `impact` | Low thump | Big reveal, a word landing, a collision |
| `riser` | Rising saw tone and hiss | Build-up into a reveal. Pair it with a negative `delay`. |
| `ding` | Clean bell | Done, correct |
| `chime` | Richer bell | Payoff, logo sting |
| `notify` | Two-note alert | Message or notification arrives |
| `success` | Four-note rising arpeggio | Goal reached |
| `error` | Two low buzzes | Wrong answer, failure |
| `sparkle` | Scattered high tinkles | Magic, shine, celebration |

## Custom sounds
`sfx` can be a function `(ctx, out, at, opts)`. Connect everything to `out` and start at time `at`. The building blocks are exposed:
```js
{ t: 0.5, sfx: (ctx, out, at, o) => {
  SFX.tone(ctx, out, at, { type: "triangle", f0: 440 * o.p, f1: 220 * o.p, glide: 0.2, peak: 0.4, d: 0.3 });
  SFX.hiss(ctx, out, at, { filter: "highpass", f0: 4000, peak: 0.2, d: 0.05 });
} }
```
`tone` options: `type`, `f0`, `f1`, `glide`, `peak`, `a` (attack), `d` (decay), `lowpass`. `hiss` options: `filter`, `f0`, `f1`, `glide`, `q`, `peak`, `a`, `d`, `offset`. Use `SFX.rng(seed)` for any randomness so every render sounds the same.

## Taste
- **Sound the motion, not the frame.** Put a cue only where something visibly happens: an arrival, a hit, a reveal. If every element gets a cue, it turns into noise.
- **One family per piece.** Pick 2–4 presets and keep using them, the same way you keep to a few colors. Vary them with `pitch` rather than adding more presets.
- **Land on the beat.** Hits (`pop`, `impact`, `click`) go exactly at the visual contact frame. Sweeps (`whoosh`, `riser`) should *end* on it, so use a negative `delay`.
- **Rising pitch reads as progress.** For a staggered list, step `pitch` up by 1.06–1.12 per item.
- **Leave silence.** The payoff lands harder after a quiet beat.
- **Many people watch with the sound off** (feeds autoplay muted, offices), so the piece must still work silently. Sound is a bonus.
- **Keep it quiet.** The default `volume: 0.8` with a limiter is plenty. If a cue sounds harsh, lower its `gain` or `pitch` before adding effects.
