# PDF parameters

## Paper sizes
| Paper | `@page size` | CSS width × height | Use |
|---|---|---|---|
| US Letter | `8.5in 11in` | 8.5in × 11in | Default in the US |
| A4 | `210mm 297mm` | 210mm × 297mm | Default elsewhere |
| US Legal | `8.5in 14in` | | Contracts |
| A5 | `148mm 210mm` | | Notes, invitations, menus |
| Half Letter | `5.5in 8.5in` | | Cards, booklets |
| 5×7 card | `5in 7in` | | Invitations, thank-you cards |
| Landscape | swap width/height | | Certificates, itineraries, timelines |

Always set `@page { margin: 0 }` and handle margins inside `.page`. That's how stationery bleeds to the edge.

## Margins and live area
- Body text inset: 0.75–1in (19–25mm). Cards: 0.4–0.5in.
- Keep the stationery art at least 0.25in from the trim edge if it might be printed at home, since most printers can't print the last few millimeters. For PDFs that are only viewed on screen, art can run to the edge.
- **Measure:** 55–75 characters per line for letters and reports. On wide pages, narrow the column rather than shrinking the type.

## Typography for print
- Body: 10.5–12pt with line-height 1.45–1.65. Captions and footers: 8–9pt.
- Use `pt`/`in`/`mm` units, not `px`, so sizes map exactly to paper.
- Fonts: Google Fonts embed in the PDF automatically. Wait for `document.fonts.ready` (the renderer does).
- Pairings that work: a display serif with a humanist sans; a script for one line only (names, salutations), never for body text.
- `hyphens: auto` with `lang` set gives cleaner justified text. Ragged-right is usually safer.

## Stationery elements
- **Letterhead:** a monogram or wordmark, plus a small-caps contact or date line and a hairline rule.
- **Frames:** a double rule (thick plus hairline), a rounded inset, a deckled edge (SVG path), or an Art Deco corner fan.
- **Corner ornaments:** an inline SVG flourish rotated and repeated for each corner.
- **Watermark:** a big faint glyph, crest, or illustration at 4–8% opacity behind the text.
- **Texture:** `radial-gradient` paper grain, a subtle linen pattern made with `repeating-linear-gradient`, or an SVG `feTurbulence` noise filter. Keep it subtle.
- **Theme motifs:** postage stamps and postmarks for travel; tickets and stubs for events; pressed-flower borders for weddings; blueprint grids for technical work; letterpress offsets for formal notes.
- **Color:** 1 paper tone, 1 ink, 1–2 accents. A paper tone tied to the theme (blush plaster, linen, pale stone) usually beats pure white.

## Document types
| Type | Shape |
|---|---|
| Personal letter / announcement | Letterhead, salutation, 3–6 short paragraphs, sign-off, themed stationery |
| Invitation | Centered, a typographic hierarchy (who, what, when, where), RSVP line, generous whitespace |
| Certificate | Landscape, framed border, seal/crest, recipient name in display type, signature lines |
| Itinerary | Timeline or day-by-day table, map or route motif, key info boxed |
| One-pager / flyer | Headline, 3 benefit blocks, a proof point, CTA, contact |
| Menu | Sections, item–description–price alignment with leaders or columns |
| Report | Cover sheet, running header/footer, section numbering; usually flowing (see below) |

## Pagination
- **Designed sheets (default):** one `<section class="page">` per sheet. You control exactly what goes on each page.
- Avoid widows: never leave a heading alone at the bottom of a page.
- `break-inside: avoid` on figures, tables, and cards.

## Flowing documents (long reports)
For content too long to split by hand, drop the fixed `.page` height:
```css
@page { size: 8.5in 11in; margin: 0.9in 0.85in 1in; }
@page :first { margin: 0; }            /* full-bleed cover */
h2 { break-before: page; }             /* each section on a new page */
figure, table, .card { break-inside: avoid; }
```
Stationery art doesn't repeat per page in flow mode, except through `position: fixed` elements, which Chromium repeats on every printed page. Use that for running borders, headers, and footers.

## Output budget
- Text-and-vector PDFs should be under 1 MB. Large embedded photos drive size up, so scale images to their display size first.
- Always render with `printBackground: true`. The renderer sets it, and without it the stationery disappears.
