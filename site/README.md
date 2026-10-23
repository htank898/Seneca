# Seneca capabilities site

A local showcase of every Seneca skill, with live demos (decks, guides, explorers, live docs run inside the page) and the real rendered outputs (GIFs, MP4s, PDFs, PNGs).

```bash
python3 -m http.server 4321 --directory site
```

Then open http://localhost:4321.

`media/` holds copies of example outputs gathered from the skill branches (ai-scale, ai-graphic, ai-math, ai-finance-viz, ai-video, ai-pitch-page, portable docs). `js/sfx-engine.js` is the ai-gif sound engine, extracted so the sound pad can play it live. When those branches merge, these copies can point at `examples/` instead.
