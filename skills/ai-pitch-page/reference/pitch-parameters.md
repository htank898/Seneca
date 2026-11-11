# Pitch page parameters

## Structure that works
| Section | Job | Length |
|---|---|---|
| Hero | Name the reader and role; one-sentence fit built on the strongest evidence | ≤ 30 words |
| You asked / I've done | Requirements in the posting's words → evidence | 3–5 rows, ≤ 2 lines each |
| Demo | Show the core skill working on a problem shaped like the role | One screen; usable in 30 seconds |
| First 90 days (optional) | Modest, concrete plan grounded in the posting | 3 steps |
| Contact | Email (copyable), LinkedIn, resume PDF | One row |

Whole page readable in under two minutes. If a section doesn't earn its place for this role, drop it.

## Writing rules
- Mirror the posting's vocabulary for requirements (it's how the reader scans), keep the candidate's real titles verbatim.
- Evidence lines follow the resume shape: action + what + measurable result, numbers only from the evidence source.
- Specific beats grand: "Cut weekly pipeline reporting from 4 hours to 20 minutes" beats "Transformed reporting".
- No clichés, no first-person filler ("I believe", "I'm passionate"), no flattery of the company.
- Never criticize the company's current tools, team, or process.

## Link preview (the card LinkedIn shows)
LinkedIn reads Open Graph tags when someone pastes the link:
```html
<meta property="og:title" content="For the RevOps team at Acme: routing that explains itself">
<meta property="og:description" content="A one-page answer to the Revenue Operations Automation Lead posting.">
<meta property="og:image" content="https://<your-host>/<folder>/preview.png">
<meta property="og:url" content="https://<your-host>/<folder>/">
<meta name="robots" content="noindex, nofollow">
```
- `og:image` must be an **absolute https URL**, so it only works once the folder is hosted. Recommended size **1200×627**; keep text large (it shows small in the feed and in chat).
- LinkedIn caches previews. If you change the image after sharing, refresh it with LinkedIn's Post Inspector (linkedin.com/post-inspector).
- Opened as a file (no host), the page still works; there's just no preview card.

## Hosting (static, no account needed by the reader)
- **Netlify Drop** (drag the folder onto app.netlify.com/drop) or **Cloudflare Pages**: free static hosting, gives an https URL.
- Use a folder name that isn't guessable (e.g. `acme-revops-7f3k`), keep `noindex`, and take the page down after the process ends.
- Don't put the pitch in a public GitHub repo if it contains personal details beyond what's already on the candidate's LinkedIn.

## LinkedIn message limits (verify against current LinkedIn behavior; these change)
- Connection request note: keep ≤ 200 characters to be safe on free accounts.
- InMail: short subject naming the role; body under ~400 characters gets read on a phone without expanding.
- Regular messages to connections can carry a PDF attachment; the link is the reliable option everywhere.

## Demo ideas by role
| Role family | Demo |
|---|---|
| RevOps / Sales Ops | Lead or opportunity routing simulator: enter attributes, see which rule fires and why |
| Salesforce admin / dev | Validation-rule or flow explainer: step through a record change and watch automation fire |
| QA / test automation | A tiny test runner on a sample form: run checks, see a pass/fail report |
| Data / BI | A what-if or drill-down on sample data the reader can manipulate |
| Sales engineering | A mini discovery-to-solution walkthrough (reuse `ai-interactive-guide`) |
| Marketing / content | A looping GIF from `ai-gif` that tells the role's story in 6 seconds |
All demos use sample data and say so.
