---
name: seneca
description: The front door to Seneca. Takes a communication need in plain words ("I have a meeting with the execs, summarize this for them", "announce the reorg", "get the team up to speed on the new CRM", "pitch this to a partner") and decides which formats fit the audience and moment: a slide deck, a PDF, a graphic or banner, a GIF, a math animation, an interactive guide, a narrated or edited video, or a 3D render, character, or animation. Then it builds them as one consistent package. Use when someone describes a situation, audience, or goal rather than a specific format, or asks "what's the best way to communicate this?". If they name one format ("make a deck"), use that skill directly.
---

# Seneca: pick the right formats, then build them

The person tells you what they need to communicate and to whom. Your job is to choose the formats and then build them. Don't hand them a menu of options. A good communications lead would say "you need a 5-slide deck for the meeting and a one-page pre-read to send the day before", and then make both.

## 1. Read the situation
Pull these from the request and any attached files, links, or pasted notes. Infer what you can.
- **Audience:** who they are, what they already know, what they care about, and what decision or action you want from them. There may be several stakeholder groups with different needs.
- **Moment:** a live meeting (presented or discussed), something read on their own time (email, doc, Slack), a public post, teaching or onboarding, a formal occasion.
- **Content:** the source material. Read all of it. Note the numbers, decisions, risks, and dates.
- **Constraints:** a deadline, the channel it goes out on, brand or colors, length limits.

Ask a question only if the answer would change *which formats* you build, and you can't infer it. Ask at most one or two, in a single message. Otherwise proceed.

## 2. Write the message spine first
Before any format, write the core message once. Every format is built from this, so they all say the same thing.
- **The answer:** one sentence. The decision, recommendation, or headline.
- **Three supporting points:** each with its strongest piece of evidence (a number, an example, a quote).
- **The ask:** what you want this audience to do, decide, or remember.
- **Per-stakeholder angle:** if there are several groups, one line each on what they care about and which point leads for them.

Save it as `spine.md` in the output folder. It's also a useful artifact on its own.

## 3. Choose the package
Pick the **smallest set of formats where each one has a distinct job**. That's usually 1–2 and at most 3, unless asked for more. Never make two formats that say the same thing to the same person in the same moment.

| Situation | Primary | Add when it earns its place |
|---|---|---|
| Live meeting, executives or decision-makers | **Deck** (answer first, 5–8 slides) | **PDF** one-page pre-read or leave-behind, if they should read before or after the meeting |
| Live meeting, working team | **Deck** with the detail | **Graphic** summary card for the team channel afterwards |
| Read on their own time (email, Slack, doc) | **PDF** one-pager or memo | **Graphic** to make the email or post stop the scroll |
| Quick update or announcement | **Graphic** (summary card, stat card) | **GIF** if a before/after or a process explains it better in motion |
| Teaching a tool or process | **Interactive guide** | **GIF** walkthrough for people who won't click through, plus a **PDF** cheat sheet |
| Public or social (LinkedIn, launch, hiring) | **Graphic** sized for the platform | **GIF** or **video** for motion, plus a **banner** or link-preview image |
| Explaining a concept to a broad audience | **Video** (narrated) or **GIF** | **Graphic** thumbnail and a **PDF** handout |
| Formal or personal occasion | **PDF** on stationery | **Graphic** invitation or announcement card |
| Outreach to one specific person or role | **PDF** one-pager tailored to them | **Graphic** link-preview image or card to send with it |
| Numbers-heavy (results, QBR, metrics) | **Deck** with charts | **Graphic** with the 1–3 numbers that matter |
| A number too big (or small) to feel: budgets, debt, market size, time spans, growth rates | **GIF** that builds the comparison in motion (MP4 for social) | A **graphic** of the payoff comparison, or a slide in the **deck** |
| Formulas, proofs, or quantitative derivations to explain | **Math animation** (MP4 for video and social, GIF to embed) | **PDF** with the full derivation, or typeset equations on the **deck** or **guide** that carries it |
| A paper, problem set, or formal derivation | **LaTeX PDF** | **Math animation** of the one step that's hard to see on paper |
| A talking-head or selfie recording that needs graphics, captions, or callouts | **Edited video** (MP4) | **Graphic** thumbnail, or a **GIF** of the key moment |
| Real footage restaged as an animated 3D scene ("me as a robot in this clip") | **Adapted 3D shot** (MP4) | **Graphic** still of the hero frame, or a **GIF** loop of the best beat |
| Animate a character or model: walk, gaits, sports motion ("make my model walk", "a pitcher from the windup") | **Animated 3D clip** (MP4) | **GIF** loop of one cycle, or a **graphic** still |
| A character (from AI image art or a drawing) that should become a 3D model to animate | **Rigged 3D character** (`.blend` + `.glb`) | A **3D render** turntable via `blender`, or an **adapted shot** driving it with real footage |

When stakeholder groups differ a lot, tailor rather than add formats. For example, execs get the deck and the working team gets the PDF with the appendix.

Then state the plan in two or three lines: which formats, the job of each, and the order to use them in. **Then keep going.** Don't wait for approval unless the request was ambiguous about something that changes the plan.

## 4. Build
Use the matching skill for each format. Load it with the Skill tool (it may have a `seneca:` prefix) and follow its full process, including its design and verification steps:

| Format | Skill |
|---|---|
| Slide deck | `slides` |
| PDF (memo, one-pager, letter, handout, cheat sheet) | `pdf` |
| Graphic, social image, thumbnail, card | `graphic` |
| Profile or page banner (LinkedIn, X, YouTube, GitHub) | `banner` |
| Looping animation, including big-number comparisons | `gif-create` |
| Animated math explainer (proof, formula, derivation) | `math` (Manim route) |
| Equations inside a deck, PDF, or guide | `math` (`typeset.mjs` route) |
| Paper, problem set, or LaTeX document | `math` (LaTeX → PDF route) |
| Interactive click-through guide | `interactive-guide` |
| Narrated video | `video-create` |
| Edit a talking-head recording | `video-edit` |
| 3D render, product shot, turntable | `blender` |
| Footage restaged as a 3D animated scene (pose capture + Blender) | `adapt` |
| Animate a character or model: walk, gaits, sports motion, mocap/BVH retarget | `animate` |
| Character image to a rigged 3D model (local image-to-3D + Rigify) | `character-3d` |

If a format's skill isn't installed, pick the next-best format from the ones that are and say so.

Package rules:
- **One visual identity.** Do the design pass once and reuse it: the same palette, type, and motif across every format, with CSS variables copied verbatim. The pieces should obviously belong together.
- **Build in order.** The primary format comes first, then the supporting ones, reusing its wording and visuals.
- **One folder.** Put everything in `<short-slug>/` in the current project (or where the person asked), with the spine, each source HTML, and each rendered file.
- **Portable.** Every deliverable must open for someone with no Claude and no special software. That means self-contained HTML, PDF, PNG, GIF, or MP4. Many email systems block `.html` attachments, so when an HTML deliverable is meant to be sent, also render its PDF, GIF, or PNG fallback.
- **Clean in every frame.** No overlapping or clipped text or icons in any format or frame: crowded things fade out or move aside. Positions stay stable during motion, and anything showing magnitude uses an honest linear scale. Each skill's verify step checks this, so don't skip it.
- **Math is typeset, never faked.** Any equation in any format goes through `math`: `typeset.mjs` for HTML pieces, Manim for motion. A Manim `--clip` is a transparent layer that can be composited into a `video-create` or `gif-create` piece, so a video or GIF can carry a math beat without switching style.
- **Don't invent facts.** Use only the numbers, names, and dates from the source material. If something important is missing, put a clearly marked placeholder in and list it at the end.

## 5. Hand off
After each format has passed its own skill's checks, reply with:
- The plan in one line, for example "Deck for Thursday's meeting, a one-page pre-read to send Wednesday, and a summary card for #leadership afterwards."
- Each file path, with what it's for and when to use it.
- Any placeholders or facts they need to confirm.
