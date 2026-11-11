---
name: ai-pitch-page
description: Build a one-page personal pitch for one specific role or person, with the posting's requirements mapped to the candidate's real evidence, one small interactive demo of the skill in action, a custom link-preview image, and short LinkedIn message drafts (connection note, InMail, message). Use when someone wants to stand out in outreach to a recruiter, hiring manager, prospect, or partner: "make a pitch page for this job", "help me stand out to this hiring manager", "personalized page for my LinkedIn message", "why-me page for this posting".
---

# AI pitch page: outreach that shows instead of tells

LinkedIn messages are plain text, so the message itself can't carry design. What it can carry is one link to a page built for exactly one reader. That page answers the posting point by point with evidence, shows the skill working, and arrives with a preview card that already names the reader.

Paths below are relative to this skill's base directory.

## Ground rules (non-negotiable)
- **Never fabricate.** Every claim, number, title, and date comes from the evidence source the user points you to (a resume source file, a master resume, a brag doc). If the posting asks for something the evidence doesn't support, say so to the user and leave it out of the page. Do not stretch.
- **Forward-looking and specific.** Write what the candidate did and what they'd do. No clichés ("results-driven", "passionate about", "team player"), no knocking the company's current tools or team.
- **Public information only about the recipient and company.** Never put a recipient's personal details on the page beyond their name and role.
- **The user sends the message.** Draft it; never automate sending, connection requests, or scraping. LinkedIn's terms prohibit automation and accounts get restricted for it.
- **Portable.** The page opens for anyone with a browser: one self-contained HTML file, no login, no tracking, works offline.

## 1. Design pass
If the `frontend-design` skill is available, invoke it. The page should feel built for this company: borrow the subject of the role (a RevOps role's page can feel like a well-made dashboard; a design role's like a portfolio), never the company's logo or trademarked branding.

## 2. Gather
- **The posting** (URL or pasted text) and **the recipient** (name, title; optional).
- **The evidence source.** Ask where it lives if not given. Read it; don't rely on memory.
- **Contact links** the candidate wants shown (email, LinkedIn URL, resume PDF filename).
- **Where it will be hosted** (decides whether the preview image works; see `reference/pitch-parameters.md`).

## 3. Map before you write
Make a requirements table in your working notes first: each posting requirement, ranked by how high it appears in the posting and how often → the strongest matching evidence (quote it) → or "no evidence". Pick the top 3–5 rows with real evidence. That table *is* the page's spine. Show the user the gaps you found.

## 4. Build
1. Copy `templates/pitch-shell.html` into a new folder for this pitch (e.g. `pitch/<company>-<role>/index.html`), not inside this skill.
2. Fill the sections (the template marks each one):
   - **Hero**: who it's for, the role, and one sentence on why this candidate fits, built on the single strongest piece of evidence.
   - **You asked / I've done**: the 3–5 mapped rows. Each: the requirement in the posting's own words, then 1–2 evidence lines with numbers where the evidence has them.
   - **Demo**: one small interactive piece that performs the core skill on a problem shaped like the role (a routing simulator for RevOps, a mini what-if for finance, a guided walkthrough for enablement, a looping GIF from `ai-gif`). Built from scratch with sample data, labeled as a sample. Never use the company's real data or impersonate their product.
   - **First 90 days** (optional): 3 concrete, modest steps grounded in the posting. Frame as listening and learning first.
   - **Contact**: email as selectable text with a copy button, LinkedIn URL, resume PDF link (relative, shipped in the same folder).
3. Set the preview metadata in `<head>` (see reference): title, description, `og:image`, `noindex`.
4. Render the preview image:
   ```bash
   node scripts/render-preview.mjs pitch/<folder>/index.html
   ```
   This screenshots the page's `#preview-card` block at 1200×627 into `preview.png` beside the page.

## 5. Draft the messages
Write all three in `messages.md` beside the page, each with the link placeholder `{link}`:
- **Connection note**: ≤ 200 characters (free LinkedIn accounts have a lower limit and a monthly cap on personalized invites). One specific line plus the link.
- **InMail**: subject ≤ 60 characters that names the role; body ≤ 400 characters: a specific opener tied to the posting, what the page shows, one low-effort ask (a 15-minute call).
- **Message to a connection**: same as the InMail body, slightly warmer.
Count characters and print the counts.

## 6. Verify before reporting
- Every number and title on the page appears in the evidence source (grep for each one). List any that don't, and fix them.
- No cliché phrases (reuse the user's resume audit word list if they have one).
- Render at desktop and phone width, light and dark; open `preview.png` and check it reads at thumbnail size.
- No network requests from the page.
- Report: the folder path, the requirements table with gaps, the three message drafts with character counts, and hosting next steps.
