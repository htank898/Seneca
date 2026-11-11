#!/usr/bin/env node
// QA: step through a built scale page and fail if any visible labels or icons overlap.
// The engine publishes window.__boxes (name, [x0,y0,x1,y1], opacity) for every element it lays out each frame.
// Boxes named "actor:…" (a character moving through the scene) may pass in front of things and are skipped.
//   node check-overlaps.mjs scene.html [--samples 240] [--min-op 0.3]
import { resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) { console.error("usage: check-overlaps.mjs <scene.html> [--samples 240]"); process.exit(1); }
const samples = +(args.samples || 240), minOp = +(args["min-op"] || 0.3);

const browser = await launch();
const page = await browser.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(resolve(input)));
await page.evaluate(() => document.fonts.ready);
const hits = await page.evaluate(({ samples, minOp }) => {
  const ts = [...Array(samples).keys()].map((i) => i / samples).concat((window.SCENE_STOPS || []).map((s) => s.t));
  const found = new Map();
  for (const t of ts) {
    window.renderFrame(t);
    const bs = (window.__boxes || []).filter((b) => b.op >= minOp);
    for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
      if (bs[i].name.startsWith("actor:") || bs[j].name.startsWith("actor:")) continue; // actors move in front on purpose
      const a = bs[i].box, b = bs[j].box;
      const ix = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), iy = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
      if (ix > 2 && iy > 2) {
        const key = [bs[i].name, bs[j].name].sort().join("  ×  ");
        const prev = found.get(key);
        found.set(key, { t: prev ? prev.t : +t.toFixed(3), frames: (prev ? prev.frames : 0) + 1, area: Math.max(prev ? prev.area : 0, ix * iy) });
      }
    }
  }
  return [...found.entries()].map(([pair, v]) => ({ pair, ...v }));
}, { samples, minOp });
await browser.close();

if (!hits.length) { console.log(`overlaps: none (${samples} frames + stops checked)`); process.exit(0); }
console.log(`overlaps: ${hits.length} pair(s) collide`);
for (const h of hits.sort((a, b) => b.frames - a.frames)) console.log(`  ${h.pair}   first at t=${h.t}, ${h.frames} frame(s), up to ${Math.round(h.area)} px²`);
process.exit(1);
