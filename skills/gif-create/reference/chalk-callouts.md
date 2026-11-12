# Chalk callouts

A chalk callout pauses the scene, hand-writes a word or two, sketches a doodle, holds for a beat, and lets the scene carry on. Think of a teacher stopping mid-sentence to turn to the board. `templates/chalk.js` does the drawing. `templates/chalk-talk.html` does the pause-draw-resume choreography for footage or for your own scene.

## When to add one (do this without being asked)
When a script, transcript, or brief names something a viewer would picture, add a callout on that word by default:

| The words mention… | Write | Doodle |
|---|---|---|
| A place ("I'm from St. Louis, Missouri") | The place name, script | Its best-known landmark or shape: the Gateway Arch, a state outline, a skyline, a mountain line |
| A person or name | The name, script | Underline or circle it. Add a small portrait or emblem only if one is obvious |
| A number or stat ("cut costs 38%") | The number, print | Arrow up or down, a tiny bar pair, or a circle around it |
| A named thing (a product, company, or concept) | The name | A simple icon of what it does (gear, chat bubble, lightbulb) |
| A contrast ("not X, but Y") | X, then Y | Strike through X, check next to Y |
| A list of three | The three words | Numbers or checkmarks |

Rules of thumb:
- **One idea per callout.** At most one every 8 to 10 seconds of scene time, so it stays a punctuation mark rather than the whole video. If the user asked for "lots" or "every place", go denser.
- **Pause after the word, not during it.** With footage, `at` is the word's *end* time from `words.txt`. Pausing mid-word sounds broken.
- **Say what you added.** List each callout (word, time, what you drew) in your report so the user can veto any.

## Timing
| Beat | Length |
|---|---|
| Board slides in, scene dims | 0.6–0.8 s |
| Writing | about 0.12 s per letter, 1.2–2 s total |
| Doodle | 1.2–2 s (by stroke length) |
| Flourish (underline, circle, star) | 0.3–0.5 s |
| Hold, finished board | ≥ 0.6 s |
| Board leaves | 0.5 s |

A callout is 4–6 s. With audio, the pause is silent (`Chalk.timeline(...).audioSegments()`), so keep it under about 6 s or it feels like a glitch.

## Drawing good doodles
Doodles are SVG path data. In `chalk-talk.html` they sit in a **400 × 260 box** (origin at top-left, ground line around y = 250) that's scaled onto the board.
- **3–6 strokes.** Each absolute `M` starts a stroke, and strokes draw in order, so order them the way a person would: outline first, then details, then the ground line.
- **Recognizable silhouette over detail.** The Arch is two nested curves plus a ground line. A skyline is one zig-zag with rectangles. A state is its outline, simplified to 10–20 points.
- Use `C`/`Q` curves for organic shapes. `rough` (default 2) adds the hand wobble, so draw your paths clean.
- Built-in shapes: `Chalk.shape.underline / loop / arrow / strike / box / check / star`, and on a board `board.underline(mark)`, `board.circle(mark)`, `board.arrow(x1, y1, x2, y2)`.

The Gateway Arch, as a weighted catenary that fills the box:
```js
const arch = (w, h, base = 250, cx = 200) => "M " + Array.from({ length: 41 }, (_, i) => {
  const u = -1 + i / 20, a = 2.2;
  return `${(cx + u * w).toFixed(1)} ${(base - h * (Math.cosh(a) - Math.cosh(a * u)) / (Math.cosh(a) - 1)).toFixed(1)}`;
}).join(" L ");
doodle: [arch(95, 230), arch(68, 195), "M 30 254 Q 200 246 370 256"]
```

## chalk.js API
```js
const board = Chalk.board(svg, { look: "chalk" | "marker" | "pen", color, width, parent, seed });
board.panel(x, y, w, h, { kind: "slate" | "paper", frame: 22, smudge: 0.3 }); // the board itself
const m = board.write("St. Louis", { x, y, size: 120, font: "script" | "print", anchor: "start" | "middle" | "end",
                                    maxWidth, lineHeight: 1.05, jitter: 1, slant: 0 });   // y is the baseline
const d = board.doodle(pathOrPaths, { rough: 2, width, color, parent });
m.draw(p);          // 0..1, pure: call it from renderFrame with seg(...)
m.erase(p);         // fade out
m.play(ms);         // live playback (decks, guides), returns a promise
m.box;              // { x, y, w, h, cx, cy } of the finished mark
Chalk.measure(text, { size, font });     // width before you place it
Chalk.timeline(sceneSeconds, [{ at, dur, name }]);  // .seconds, .at(sec) -> { scene, hold, p }, .audioSegments()
Chalk.footage(imgOrSvgImage, FOOTAGE).show(sceneSec); // returns a promise; return it from renderFrame
Chalk.auto(root);   // declarative mode: <text data-chalk> and <path data-chalk> inside an <svg>
```
- `size` is the font's em size. The script face reads small for its em, so 120–200 on a 720p board is normal. Let `maxWidth` fit it.
- Looks: **chalk** (light on slate, grain texture), **marker** (dark on paper, clean), **pen** (thin and dark). Pass `color` to match the piece's palette, for example the accent color on a whiteboard.
- The chalk grain is static noise, so it costs some GIF size. For GIFs, keep boards a fraction of the frame, or use `look: "marker"`, which is flat.

## Footage
```bash
node scripts/prepare-footage.mjs talk.mp4 --words   # frames, audio, footage.js, words.txt
```
Copy `templates/chalk-talk.html` and `templates/chalk.js` next to `talk.mp4`, uncomment the `footage.js` script tag, read `talk.footage/words.txt`, and write `CALLOUTS`. Render with `--video` to get an MP4 with sound where the audio pauses with the picture (written as `talk.chalk.mp4`, so it never overwrites `talk.mp4`).
- `--words` runs faster-whisper locally through `uv`. The first run downloads a model of about 500 MB. Without `--words`, ask the user for rough times or listen for them yourself.
- Long videos: use `--width 1280` and `--fps 24` to keep frame folders reasonable (about 1 MB per second of footage).
- The footage folder holds every frame. Delete it after the final render unless the user will iterate.
