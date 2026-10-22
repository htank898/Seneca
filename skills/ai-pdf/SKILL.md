---
name: ai-pdf
description: Design and export print-accurate PDFs with custom stationery using HTML/CSS: letters, notes, announcements, invitations, certificates, itineraries, menus, one-pagers, flyers, and branded reports. Use whenever someone wants a "nice", "pretty", designed, or branded PDF, a letter on stationery, or a printable document, instead of reaching for Word, Pages, or Canva. If they explicitly ask for a .docx, use a Word skill instead.
---

# AI PDF: custom stationery as code

Word processors make a human drag text boxes around a page. You don't need to. Here you design the sheet in HTML/CSS at exact paper dimensions, letting decoration, layout, and typography be as specific as the occasion. Then Chromium's print engine turns it into a real PDF.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it first and treat the page as a designed object: palette, type pairing, and an ornament language that fit the occasion (a trip announcement can borrow from postage stamps and travel posters; a thank-you can feel letterpressed; a report can feel editorial). If it isn't available, choose those three things deliberately yourself. Default Times on white is the humanoid robot here.

## 2. Gather only what's missing
Use defaults from `reference/pdf-parameters.md` for anything not stated:
- **Document type and occasion**, which drive the stationery theme
- **Recipient / audience** and tone
- **Content**: write it if they gave you the gist. Ask only for facts you can't invent (names, dates, amounts).
- **Paper**: Letter in the US, A4 elsewhere; portrait unless the content needs landscape
- **Personalization**: monogram, names, colors, logo file if they have one

## 3. Build
1. Copy `templates/stationery-shell.html` to the output location (not inside this skill).
2. Set the paper size in **both** `@page { size }` and `--paper-w/--paper-h`.
3. Build the **stationery layer** (`.stationery`): borders, corner ornaments, letterhead art, watermark, and a texture made from CSS gradients or inline SVG. It's absolutely positioned and sits behind the content.
4. Put the writing in the **live area** (`.content`), which is inset by `--margin`.
5. **Multi-page:** create one `<section class="page">` per sheet and split the content deliberately. Check for overflow, since text past the live area gets clipped. For long flowing reports, see "Flowing documents" in the reference.
6. Use inline SVG for any illustration. It stays vector-sharp in the PDF.

## 4. Render
```bash
node scripts/render-pdf.mjs path/to/doc.html --preview
```
This writes `doc.pdf` and, with `--preview`, `doc.page-N.png` for each sheet. It prints the page count and paper size. The first run installs Playwright into this skill folder.

## 5. Verify before reporting
- Look at every preview PNG. Check for clipped text at the bottom of the live area, ornaments colliding with text, orphaned single lines, and contrast.
- Confirm the reported page count and size match what you intended. An extra blank page usually means something overflowed `.page` or a stray `break-after` caused it.
- Delete the preview PNGs unless the user wants them. Report the PDF path.
