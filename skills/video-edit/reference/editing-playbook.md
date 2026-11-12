# Editing playbook: deciding what goes on screen

The user recorded themselves talking and handed you the file. They are not an editor and should not have to become one. Your job is the editor's judgment: watch (read) the take, decide the handful of moments where a graphic helps the viewer, and leave everything else as the speaker's face. A good edit here looks like a person with taste did it, not like every keyword set off a pop-up.

## 1. Read the take before deciding anything

Run `node scripts/cues.mjs video.transcript.json` and read the whole worksheet:

- **The transcript first, top to bottom.** Decide what the video *is* before looking at cues: a quote walkthrough, a proposal follow-up, an intro, a thank-you, a test take full of directions to you. Note who it's for (a client by name? a team?) and the one thing the viewer should walk away with.
- **Then the candidate table.** Each row is a moment the scanner thinks *might* deserve something: `direction`, `intro`, `money`, `number`, `list`, `quote`, `cta`, `signoff`, `pause`. It over-reports on purpose. Most rows end up as "nothing". The `say` column is the exact phrase to key to, and `context` shows the words around it.
- **Pauses are structure.** A silence over ~0.8 s is where a thought ends. Full-screen moments start and end best inside pauses, and they are where a hold costs the least.
- **Low-confidence words** (printed by `transcribe.py`) are where names and numbers get misheard. Never key to one, or print one on screen, without checking it against what the user told you.

## 2. Spoken directions are commands

When the speaker talks to *you* ("put the logo here", "throw up the price", "and then come back", "do a thank-you slide at the end", "freeze on this"), do exactly that, at exactly that moment:

- "Here" means the word they just said. Enter on the end of the phrase that names the thing ("logo here" → start at the end of "here", `offset -0.2`).
- "Come back", "now it's just me again", "back to me" means end the graphic. Return a beat *before* they resume speaking to camera (`offset -0.1` on the next sentence's first word), so their first word is on their face.
- "At the end" means it runs to `"end"`.
- A direction overrides the defaults below. If they ask for a full-screen logo for 4 s, they get it, even though you'd normally keep full-screen moments short.
- If a direction is impossible or ambiguous ("show the chart", with no chart provided), do the closest honest thing (a title card naming it) and say so in your report, or ask if it's central.

**Meta-talk is not content.** The words the speaker says to the editor ("so like run the logo here", "I want to see if you can…") are instructions, not message. Don't caption them, don't pull quotes from them, and don't put graphics over them unless the graphic is the thing they asked for. The exception is when the meta-talk is the charm of the video (a playful "uh, edit that out" in a casual update). Then a wink is fine: see Tone.

## 3. What goes on screen, by what is said

When there's no direction, choose from the content. Each template has a job. Use it only when the speech actually does that job.

| They say… | Use | Notes |
|---|---|---|
| Their name / who they are: "Hi, I'm Jordan from Acme", "Jordan here" | **lowerthird** (name + role) | Once per video, in the first ~10 s. Enter just after the name is said and hold 3–4 s. Only use a title or company they said or gave you. |
| A stat or a number that is the point: "cut onboarding time by 40%", "3x faster", "200 reps use it" | **callout** (`text` = the number, `sub` = what it measures) | Only the number that is the argument. Not every number: "a couple of weeks" or "two quick things" is not a callout. |
| An enumeration: "three things", "first… second… finally", "number one" | **bullets**, each item cued to the word that introduces it (`at: { say }`) | 2–5 short items in the speaker's words, trimmed to 2–5 words each. The card goes up on the list announcement and items land as each is spoken. |
| The offer: prices, line items, a total: "the platform is twelve thousand, onboarding is thirty-five hundred" | **quote** card, rows cued to the words, total counts up | The money moment in a sales video, so it's worth getting exactly right. Amounts only as said or as given in writing. `client` and `date` only if known. Rows only appear as they're said. Use `side: "right"` (a compact corner card) when the speaker keeps talking to camera through the price, and the full-width bottom card when it's the main event. |
| An ask: "book a time", "reply to this email", "sign by Friday", "check the link" | **cta** (the verb as the button, the how/where as `sub`) | Usually the last overlay before the sign-off. Put a URL or email in `sub` only if the user provided it. |
| A section change in a longer video: "okay, pricing", "next, the timeline" | **title** card (full screen, short) | Only in videos long enough to have sections (~90 s+). In a 30 s pitch it's an interruption. |
| A sign-off: "thanks", "talk soon", "thank you" at the end | **endcard** (from the sign-off to `"end"`) | Name + one contact line. If they keep talking after "thanks" for more than a second, start it on their last word instead. |
| Their brand, at an intro or outro or when asked | **logo** sting | Full screen, 2–4 s. Never in the middle of a sentence unless they asked. |
| Anything, for a muted feed (LinkedIn, Instagram, a sales email with autoplay) | **captions** | See section 6. |

Things that are *not* triggers: filler ("so, like, basically"), restarts and stumbles, numbers inside small talk ("I've been here two years" at most earns a lower-third role, not a callout), and the client's own name repeated (show it once on the quote card, not as a pop-up).

## 4. Timing

- **Enter on, or just before, the keyword.** `offset` −0.1 to −0.2 s on the phrase start makes the graphic land *with* the word instead of chasing it. Full-screen stings enter at the end of the phrase that names them.
- **Readable means at least ~1.5 s on screen**, plus ~0.3 s per extra line of text. A callout with a number and a short sub: 1.8–2.5 s. A lower-third: 3–4 s. A four-row quote card: as long as the speaker spends on the price, and never under 4 s.
- **Exit before the next thought.** End the overlay on the last word of the sentence it belongs to, or inside the pause after it. Don't let a graphic hang over an unrelated sentence.
- **Return to the face before they speak to camera.** After any full-screen moment, cut back `offset -0.1` before their next sentence. A viewer who hears a voice over a card wonders what they're missing.
- **Cue parts to words.** Bullets and quote rows take `at: { "say": "…" }`, so each item appears on the word that introduces it. The renderer resolves these to output time (holds included).
- **Use the phrase, not the clock.** Key every time to a phrase so the plan can't drift from the recording. Use seconds only when there is no word nearby, such as the very start.

## 5. Restraint

The speaker's face is the content. A sales video is a person talking to a person. Defaults:

- **One overlay at a time** (captions don't count). If two moments collide, keep the one closer to the video's point and drop the other.
- **Leave the first ~1 s clean**, so the video opens on a face, not a graphic. Leave the face uncovered for most of the runtime: a typical 30–60 s take gets 2–4 overlays, not ten.
- **Full-screen moments** (logo, title, endcard, full quote) are short: 2–5 s, unless it's the endcard running out the clock or a hold is buying the time.
- **Over-the-speaker overlays** (lowerthird, callout, bullets, quote card, cta) sit in the lower or upper third, never across the eyes, and come down when they've been read.
- **Same colors and type throughout.** Use the brand palette (`"brand"`) everywhere or nowhere.
- When unsure whether a moment deserves a graphic, it doesn't.

## 6. Captions

- Add them when the video will likely autoplay muted (social feeds, LinkedIn DMs, embedded in an email) or when the user asks. Skip them for a one-to-one video the recipient will watch with sound, unless asked.
- Cover the content, not the meta-talk. Split the `captions` overlay into ranges that skip the directions to you.
- Keep `maxWords` at 3–4 for phone-vertical video and 5–6 for landscape.
- Captions sit at the bottom. The lower-third sits above them, so the two can share the screen. Avoid bottom callouts (`position: "bottom"`) and the cta while captions are up, or end the captions range before them.
- Check the transcript spelling of names and brand words before burning them in (re-transcribe with `--prompt "Acme, Jordan Lee"` if Whisper got them wrong).

## 7. Holds (pausing the video)

`"hold": N` freezes the frame and silences the audio for N seconds where that overlay starts, then the video resumes exactly where it was. It changes the speaker's pacing, so it's a last resort:

- **Justified:** the viewer has to *read* something the speaker rushed past, such as a price breakdown said in two seconds, a quote they need to see before the next sentence, or a URL. Also when the user asks ("pause on the price").
- **Not justified:** decoration, a logo, a callout that fits in the time the speaker already gave, or anything you could time into an existing pause instead. Look for a natural pause first, and stretch the overlay across it.
- **Limits:** about 3 s or less each, and at most 2 per video. Start a hold at a pause between sentences (the frame freezes on a neutral face, not mid-word with the mouth open). Check the frozen frame in a preview.
- Everything after a hold shifts automatically (later overlays, caption words, `at` cues), so keep keying to phrases.

## 8. Tone

Match the delivery:

- **Polished pitch or proposal:** clean and quiet. Brand colors, a quote card that's exactly right, a CTA, an endcard. No jokes.
- **Casual update or a playful speaker**, or when the user asks for fun: the edit can play along, and the shell has a kit for it (SKILL.md, "Playful templates"):
  - **They correct themselves** ("this Ford— no, it's a Chevy Silverado"): use `correction`. The wrong take gets scribbled out on the word that corrects it, and the right one lands highlighted, optionally with a "Corrected" stamp. For a full-screen version of a renamed thing, use `scratchout` (old name struck, new name slams in).
  - **They admit numbers are made up, or say "don't quote me"**: use a `stamp` ("Made-up numbers", "Not legal advice").
  - **A long pause while they think**: use `thinking` ("loading thought…").
  - **A run of "um, so, like, you know"**: use `meter`, the waffle-o-meter that counts them.
  - **They swear on a casual take**: bleep the caption (`captions` `bleep`), or gag the logo tag (`logo` `tagGag`: "and sh#t" scribbled out, corrected to "and stuff").
  - **"Imagine a picture here"**: use `photo` with a labelled placeholder (or their image, if they gave one).
  - Key every gag to the exact words that set it up, and land the punchline (strike, stamp, boom) on the word that delivers it.
  - Two or three gags in a casual minute is the ceiling. A gag never covers the face for long: keep it in a corner and short.
- Never mock the speaker, and never make a gag out of the client or the price.

## 9. Facts

- **Never invent** a name, title, company, price, date, statistic, URL, or email address. Everything on screen was said in the recording or given to you by the user. Paraphrase only to shorten ("we'll cut your onboarding time roughly in half" → callout `~50%`, sub `faster onboarding` is fine. Adding "in 30 days" is not).
- **Check arithmetic.** If line items are shown, the total must equal what was said. If the spoken total and the items disagree, show the spoken numbers and flag the mismatch to the user.
- **Ask only when a needed fact is missing**: the spelling of a name Whisper mangled, a price said vaguely ("about fifteen"), the URL for a "link below" CTA. Otherwise proceed without waiting, and list your choices in the timeline you show the user.

## 10. Worked example: a test take

The transcript (22 s), from `cues.mjs`:

```
  0.82–6.20   I want to see if I can do a take where you'll throw a video over mine.
  7.10–11.44  So like run the Seneca logo here and then come back.
 12.78–14.24  So like now it's just me again.
 15.14–16.28  And then we can do a sign off.
 17.10–18.16  Like a thank you slide.
 19.00–20.74  And do like a little animation.
```

**What the video is:** a test take. Almost every sentence is a direction to the editor. There's no client, price, or list, so the content templates have nothing to do. The directions decide the edit.

| Moment | Decision | Why |
|---|---|---|
| 0.82–6.20 "throw a video over mine" | nothing | meta-talk about the whole edit, not a cue for a moment |
| 8.10 "logo here" | **logo** from end of "logo here" −0.2 s (8.44) | literal direction, landing on "here" |
| 10.96 "then come back" … 12.78 "So like now" | end the logo at "so like now" −0.1 s (12.68) | "come back" is the end. Return just before they speak to camera, so "now it's just me again" is on their face. |
| 15.90 "sign off", 17.58 "thank you slide" | **endcard** from "thank you slide" (17.58) to `"end"` | literal direction. "Sign off" announces it, and "thank you slide" names it, so start on the name. |
| 19.78 "a little animation" | nothing extra | the endcard is already animated. A second overlay would stack on the first. |
| captions | none | the whole take is meta-talk, so captioning instructions adds nothing |
| holds | none | nothing on screen needs reading time |

The resulting `edit.json`:

```json
{
  "video": "pitch.mov",
  "transcript": "pitch.transcript.json",
  "out": "pitch.edited.mp4",
  "output": { "height": 1440, "fps": 30 },
  "overlays": [
    { "id": "logo", "type": "logo",
      "from": { "say": "logo here", "at": "end", "offset": -0.2 },
      "to":   { "say": "so like now", "at": "start", "offset": -0.1 },
      "props": { "word": "Seneca", "tag": "AI-first communication" } },
    { "id": "thanks", "type": "endcard",
      "from": { "say": "thank you slide", "at": "start" },
      "to": "end",
      "props": { "title": "Thank you", "name": "Jordan Lee", "line": "Made with Seneca · AI-first communication" } }
  ]
}
```

The same take as a real pitch would be edited differently. Suppose it said "Hi, I'm Jordan from Acme. Your quote comes to twelve thousand for the platform and thirty-five hundred for onboarding. Grab a time on my calendar. Thanks!" That edit gets:

- a lowerthird after "Jordan from Acme";
- a quote card from "your quote", with rows on "twelve thousand" and "thirty-five hundred" and the total counting to $15,500 (a hold of ~2 s only if the price sentence ends straight into the CTA);
- a cta "Book a time" from "grab a time", with the calendar link in `sub` only if the user gave it;
- an endcard from "Thanks".

That's four overlays, never two at once, with the face clear between them.
