---
name: video-edit
description: Edit a talking-head video by what the speaker says, with no editing experience needed. Transcribes a selfie, phone, or webcam recording locally with open-source Whisper (word timestamps), decides the edit from the content, and lays branded HTML animations over the footage on cue. It follows spoken directions ("put the logo here", "then come back") literally, and otherwise adds name tags, stat callouts, bullet lists, price/quote cards, CTAs, end cards, and captions where they help. It can briefly pause the video when something needs reading time. Use for "edit my video", "add graphics / overlays / captions to my recording", "put my logo / a quote / the price over my video", "add a thank-you slide at the end", sales videos, proposal or quote walkthroughs, prospecting and follow-up videos, personal updates, or any video the user recorded of themselves talking.
---

# AI Video Edit: edit a talking-head video by what's said

The user records themselves talking, like a salesperson walking a client through a quote, and hands you the file. You transcribe it locally, read it like an editor, decide the few moments where a graphic helps, and render those graphics over the footage at the exact words. The user never opens a timeline. The edit is a small JSON file keyed to their own words, so it's easy to read, change, and re-render.

**You make the editorial calls.** Don't ask the user what to put where. Read `reference/editing-playbook.md`, make the edit, show the plan, and render. Ask only when a fact you need is missing.

Paths below are relative to this skill's base directory. Write the user's files next to their video, not inside this skill.

## 1. Transcribe
```bash
python3 scripts/transcribe.py path/to/video.mov [--prompt "Acme, Jordan Lee, Seneca"]
```
- Uses **faster-whisper** (MIT) running OpenAI's Whisper `large-v3-turbo` model (MIT) on this machine. Nothing is uploaded, and no keys are needed.
- The model downloads once (about 1.6 GB). It transcribes about 20 s of speech in roughly 15 s on Apple silicon. Use `--model small.en` for speed on long videos.
- `--prompt` takes names, companies, and jargon so they're spelled right. Pass any the user mentioned.
- **First run sets itself up:** it builds a Python 3.12 venv at `.venv/` with `uv`. Audio is decoded with the system `ffmpeg`, so any format ffmpeg reads works.
- Writes `video.transcript.json` (every word with `start`, `end`, and confidence `p`, plus segments), `video.srt`, and `video.vtt` next to the video.
- Prints low-confidence words. Names and numbers among them must be checked before they go on screen.

## 2. Read the worksheet
```bash
node scripts/cues.mjs path/to/video.transcript.json
```
It prints the transcript by segment, then a table of candidate moments with exact times and the phrase to key to:
- `direction`: the speaker talking to the editor ("put the logo here", "come back")
- `intro`: a self-introduction
- `money`: prices and amounts
- `number`: stats
- `list`: enumerations
- `quote`: the offer or proposal
- `cta`: an ask
- `signoff`: a closing line
- `pause`: a silence over 0.8 s

It over-reports on purpose. Read the transcript top to bottom first and decide what the video is and who it's for, then go through the candidates.

## 3. Make the edit
Follow `reference/editing-playbook.md`. In short:
- **Spoken directions are commands.** Follow them literally, at the words. Don't caption the speaker's meta-talk to you.
- **Otherwise choose from content:**
  - a name → lowerthird
  - the stat that is the point → callout
  - an enumeration → bullets
  - prices → quote card
  - an ask → cta
  - the sign-off → endcard
  - a likely-muted destination → captions
- **Be sparse.** One overlay at a time (captions excepted). Keep the first ~1 s and most of the runtime on the face. Keep full-screen moments to 2–5 s. Enter on the keyword (`offset` −0.1 to −0.2), hold for at least 1.5 s, and return to the face just before they speak to camera.
- **Hold (pause the video) only if you must**: something has to be read that the speaker rushed. Keep each hold to 3 s or less, with at most 2 per video.
- **Never invent** a name, title, price, date, stat, or URL. Everything on screen was said or given to you.

Write `edit.json` next to the video. Show the user the planned timeline as a table (time range, overlay, what it shows, the phrase it's keyed to, and why), then **proceed without waiting**. Stop and ask only when a needed fact is missing: a name's spelling, a vague price, the link for a "link below".

### edit.json
```json
{
  "video": "pitch.mov",
  "transcript": "pitch.transcript.json",
  "out": "pitch.edited.mp4",
  "output": { "height": 1440, "fps": 30, "crf": 20 },
  "brand": { "signal": "#2f6bff", "ink": "#0e1630", "paper": "#f4f6fb" },
  "overlays": [
    { "type": "lowerthird", "from": { "say": "Jordan from Acme", "at": "end" }, "to": { "say": "Jordan from Acme", "at": "end", "offset": 3.5 },
      "props": { "name": "Jordan Lee", "title": "Account Executive, Acme" } },
    { "type": "quote", "from": { "say": "your quote", "offset": -0.15 }, "to": { "say": "grab a time", "offset": -0.1 }, "hold": 2,
      "props": { "client": "Northwind", "items": [
        { "label": "Platform", "amount": 12000, "at": { "say": "twelve thousand" } },
        { "label": "Onboarding", "amount": 3500, "at": { "say": "thirty five hundred" } } ] } },
    { "type": "endcard", "from": { "say": "thanks" }, "to": "end", "props": { "name": "Jordan Lee", "line": "jordan@acme.com" } }
  ]
}
```
- **Paths** are relative to edit.json. `transcript` defaults to `<video>.transcript.json`, and `out` defaults to `<video>.edited.mp4`.
- **Times** (`from`, `to`) can be any of these:
  - a phrase: `{ "say": "…", "at": "start" | "end", "offset": seconds, "nth": 2 }`
  - seconds of the source video
  - `"start"` or `"end"`

  Phrases match whole words, ignoring case and punctuation. Write numbers the way Whisper wrote them: check the transcript for "$12,000" versus "twelve thousand". A phrase that isn't in the transcript stops the render and prints what was said, so a plan can't drift from the recording. `to` defaults to `"end"`.
- **Cues inside props:** any object in `props` with a `"say"` key is resolved to an output time the same way. That's how bullets and quote rows land on their words.
- **`"hold": N`** freezes the frame and silences the audio for N seconds where that overlay starts, then resumes. The overlay stays up through the freeze. Everything later (overlays, cues, caption words) shifts by N automatically, so keep keying to phrases.
- **`"brand"`** overrides the palette tokens `paper` (light background), `ink` (dark), `ink2`, `steel` (secondary text), `signal` (accent), `led`, `red` (gag marks), and `font` (a CSS font stack). Use the user's brand colors if they gave them or they're in their project.
- **`"id"`** (optional) names an overlay in the log.
- **`output`** sets `height` (default: the source height or 1080, whichever is larger; width follows the source aspect), `fps` (default 30), and `crf` (default 20).

### Templates (`templates/overlay-shell.html`)
Sizes scale with the frame's short side, so every template works in 9:16, 3:4, 1:1, and 16:9.

| type | what it is | props |
|---|---|---|
| `lowerthird` | name tag, lower left, above the caption line | `name`, `title` (role, company) |
| `callout` | big stat or keyword pill | `text` (the number), `sub` (what it measures), `position`: `top` (default), `middle`, or `bottom` |
| `bullets` | numbered card, lower part of the frame. Items appear as they're said | `title`, `items`: strings or `{ "text", "at": { "say" } }` (uncued items stagger in) |
| `quote` | price card. Rows appear (and take space) only once they're said, and the total counts up | `title` (default "Your quote"), `client`, `date`, `items`: `[{ "label", "amount", "at"? }]`, `total` (default: sum of items), `totalLabel` (default "Total"), `totalAt` (a cue), `currency` (default "USD"), `note` (e.g. "Valid for 30 days"), `noteAt` (a cue). Placement: the default is full width at the bottom. `side: "right"` or `"left"` gives a compact card in the top corner that keeps the face clear (prefer it over a centered face). `full: true` centers it over a dimmed frame. |
| `cta` | pill button, bottom center, gentle pulse | `text` (the verb: "Book a call"), `sub` (where/how) |
| `captions` | burned-in captions from the transcript, current word highlighted | `maxWords` (default 4), `bleep`: `{ "word": "w#rd" }` (replaces a word, ignoring case). The overlay's `from`/`to` choose which speech is captioned. Use several ranges to skip meta-talk. Whisper's split tokens ("20" ",000", "20" "%", "AI" "-driven") are glued back together. |
| `logo` | **full-screen** brand sting, circle wipe in and out | `image` (the user's logo file; replaces the Seneca disc mark), `word` (wordmark text, default "Seneca", or none with `image`), `tag` (small line under it), `tagGag`: `{ "text", "at", "strikeAt"?, "fix" }` (extra words on the tag that get scribbled out and corrected, a playful option) |
| `endcard` | **full-screen** thank-you card that slides up | `title` (default "Thank you"), `name`, `line` (contact line), `image` (logo file), `disc: false` (hide the Seneca mark) |
| `title` | **full-screen** section card, wipe in | `kicker` (small label above), `text` |

Captions sit at the bottom and the lowerthird sits above them, so they can share the screen. Avoid `cta` and bottom callouts while captions are up.

**Playful templates.** Use these only when the delivery is casual or the user asks for fun (playbook §8). Never use them in a polished client pitch.

| type | what it is | props |
|---|---|---|
| `correction` | sticky note in a top corner. Wrong versions get a red scribble, and the final one gets highlighted | `side` (`left`/`right`), `label` (e.g. "Vehicle"), `lines`: `[{ "text", "at", "strikeAt"?, "final"? }]`, `stamp`: `{ "text", "at", "color"? }` |
| `stamp` | rubber stamp slammed onto the frame | `text`, `sub`, `x`/`y` (% of frame, default 50), `rotate` (deg, default −8), `color` (default `var(--red)`) |
| `thinking` | "loading thought…" pill with a stalling progress bar, for a long pause | `text`, `side` |
| `meter` | waffle-o-meter gauge that ticks up on each filler word spoken while it's up | `label`, `max` (count that pins the needle), `fillers` (default um, uh, like, "you know"), `side` |
| `scratchout` | **full-screen**: a name, scratched out, then the new one slams in with a BOOM | `kicker`, `from`, `to`, `strikeAt`, `boomAt` (cues), `boom` (default "BOOM!") |
| `photo` | floating polaroid in the top-left corner (the user's photo, or a labelled placeholder) | `image` (file), `caption`, `note`, `placeholder`, `stamp`: `{ "text", "sub", "at" }` |

### Custom templates
For anything the shell doesn't cover (a chart, a client's logo wall, a one-off gag):
1. Copy `templates/overlay-shell.html` next to the video and set `"page": "overlays.html"` in edit.json.
2. Add a `TEMPLATES.<name> = { build(el, o), draw(el, k, o) }` entry:
   - `build` runs once and writes the markup.
   - `draw` runs every frame and must be a pure function of `k`. `k.t` is seconds since the overlay started, `k.left` is seconds until it ends, `k.dur` is its length, `k.p` is progress 0..1, and `k.abs` is output time. Cued prop times in `o.props` are absolute output seconds, so compare them with `k.abs` or subtract `o.from`.
   - No CSS animations, timers, or unseeded randomness.
3. Use the palette tokens (`var(--signal)` etc.) and the `--u` unit (1% of the short side).
4. `window.EDIT.words` has every transcript word on the output timeline.

Opening the page directly in a browser plays the edit over a checkerboard: space pauses, ←/→ scrubs.

## 4. Preview stills, and look at them
```bash
node scripts/render-edit.mjs path/to/edit.json --preview 1.4,8.6,12.0,18.2
```
- Preview times are **output** seconds (holds included). The renderer logs each overlay's output `from → to` first, so pick a moment inside each one.
- Each still is saved as `<out>.preview-<t>s.png`. Read every one and check:
  - text is readable at phone size and nothing is clipped;
  - the face isn't covered by anything that stays up;
  - names and numbers are exactly right;
  - a held frame isn't caught mid-blink or with the mouth wide open.
- Fix edit.json and repeat until they're right. Delete the preview PNGs when done.

## 5. Render
```bash
node scripts/render-edit.mjs path/to/edit.json [--out final.mp4] [--keep-frames]
```
- Finds the source's real size (phone rotation included) and scales it to `output.height`.
- Draws only the frames where something is on screen, as transparent PNGs in headless Chromium, and lays them over the footage with ffmpeg. With holds, it first cuts the freezes into the footage, then composites.
- Output is H.264 `yuv420p` + AAC with `+faststart`, ready for email, LinkedIn, or a CRM.
- Working frames go in `.overlay-frames/` next to the output and are deleted afterwards (`--keep-frames` keeps them).
- The first run installs Playwright into this skill folder. Requires `ffmpeg`. A 25 s clip with captions throughout (every frame drawn) renders in about a minute on Apple silicon. Without captions it's faster.

## 6. Verify before reporting
- **Frames:** pull a frame just before, during, and just after each overlay (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`) and look at them. Each overlay should start and end on the words it's keyed to.
- **Holds:** check a frame inside each hold. Measure the audio there: `ffmpeg -ss A -t D -i out.mp4 -af volumedetect -vn -f null -` should report `max_volume` around −90 dB. Check that captions after the hold still match the speech.
- **Durations:** `ffprobe` the video and audio stream durations. They must match each other and equal the source duration plus the total hold time. The renderer stops with an error if they differ by more than 0.1 s.
- **Words:** recheck any low-confidence words that appear on screen.
- **Report:** the overlay timeline (output `from → to`, what it shows, the phrase it's keyed to), any facts you assumed or still need, and the output path, size, and duration.

## Privacy
The recording is the user's face and voice. Everything here runs locally. Ask before committing a recording or rendered video to a repo, or uploading it anywhere. The transcript and edit.json contain what they said, so treat them the same way.

See `reference/editing-playbook.md` for the editorial rules: what to show, when, how much, when a hold is justified, tone, and a worked example.
