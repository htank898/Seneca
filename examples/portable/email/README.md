# Inbox-ready email: Pro pricing update

Many corporate mail systems block or flag `.html` attachments. This example puts the message in the email itself, so it renders in the inbox with nothing to open.

Sample scenario: Lumen Desk is fictional. See `../SCENARIO.md`.

## Files

| File | What it is |
|---|---|
| `pricing-update-email.html` | The HTML email body. Subject line and preheader are in the comment at the top. |
| `pricing-update-email.txt` | The plain-text alternative, with the same content. |
| `pricing-update.eml` | A complete message (multipart/alternative, UTF-8, quoted-printable) built from the two files above. |
| `build-eml.mjs` | Rebuilds the `.eml` from the `.html` and `.txt`. No dependencies: `node build-eml.mjs` (set `EML_DATE` to pin the Date header). |

## How to send it

- **Email service (HubSpot, Mailchimp, Braze, SendGrid and others):** create a custom-HTML or code-your-own email, paste in `pricing-update-email.html`, and paste `pricing-update-email.txt` into the plain-text version. Use the subject and preheader from the comment at the top.
- **Outlook desktop / Apple Mail:** open `pricing-update.eml`. It opens as a received message that you can read, forward or turn into a template.
- **Edit and resend:** change the `.html` and `.txt`, then run `node build-eml.mjs`.

## Email-client behavior it accounts for

- **Layout:** tables only, with `role="presentation"`. Fluid up to 600px and down to about 320px. Outlook for Windows gets an MSO conditional "ghost" table, because it ignores `max-width`.
- **Styles stripped:** all important CSS is inline. The `<style>` block only adds the mobile tweaks and dark mode, so the email still reads well when a client removes it.
- **Images blocked:** there are no images. The brand bar, accent rules and highlight panel are colored table cells. The button is a bulletproof button: VML `v:roundrect` for Outlook and a padded link everywhere else.
- **Dark mode:** `color-scheme` and `supported-color-schemes` meta tags, `prefers-color-scheme` rules (Apple Mail, iOS, Outlook for Mac), and `[data-ogsc]`/`[data-ogsb]` hooks (Outlook.com). Gmail's forced color inversion can't be fully controlled. The palette was chosen so inverted colors stay readable.
- **Gmail clipping:** the HTML is about 18 KB, well under Gmail's 102 KB clipping limit.
- **Safe content:** no JavaScript, forms, external fonts, or background images. System fonts only. Apple data detectors are neutralized so dates and addresses keep their styling.
- **Accessibility:** `lang="en"`, real `<h1>`/`<h2>` headings, 16px body text, and a hidden preheader.
- **Deliverability basics:** a plain-text part, a `Reply-To` header, a `List-Unsubscribe` header, a manage-preferences link, and a postal address in the footer (all fictional).
