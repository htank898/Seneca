# Prompting Gemini (Nano Banana) for ellipse-paint

Gemini is the concept artist. The ellipse fit decides how the artwork finally looks, so prompt for **strong shapes, clear value contrast and a readable silhouette** rather than fine texture, which the fit will simplify anyway.

Client: `node ../adapt/scripts/gemini.mjs image --prompt "..." --aspect 2:3 --size 4K --out work/concept.png [--n 3] [--ref img.png]`
The default model is set in that script (`gemini-nano-banana-2.1`). Pass `--model` only when Google has moved on. Add `--dry-run` to see the request without sending it.

## Recipes

**Cut-out subject (tees, stickers, mugs).** The knockout needs a flat background:
> A single [subject], [pose/angle], centred, whole subject in frame with a little margin. Bold, simple shapes with strong light/dark contrast and a clear silhouette, [palette: 3–5 named colours]. Isolated on a perfectly flat, solid pale grey background, no shadow, no ground plane, no text, no border.

**Full-bleed scene (posters, mugs).**
> [Scene], composed for a vertical 2:3 poster, focal point slightly above centre, large simple masses of colour, strong value structure, [time of day / light], palette of [colours]. No text, no signature, no frame, no border.

**Variation of a chosen concept.** Pass it as `--ref`:
> Same subject and composition as the reference, but [change]. Keep the flat solid background.

**Collection.** Keep everything constant except the subject:
> [Fixed style sentence]. Subject: [fox | owl | hare | deer]. [Fixed background sentence].

## Rules
- Use no text in the image. Set type later with the `graphic` skill.
- Name colours or give a palette. The fit preserves colour well, so the palette is the brand.
- Don't use brand names, franchise characters, celebrities, or "in the style of <living artist>". Describe the visual qualities instead: "flat gouache, chunky shapes, limited palette".
- Prefer `--size 4K` for concepts headed to `fit --work 400`. 2K is plenty for `--work 200`.
- If the knockout leaves a halo or floor shadow, the fix is a cleaner prompt ("no shadow, perfectly flat background"), not a looser `--tol`.
