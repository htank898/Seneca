#!/usr/bin/env node
// QA: step through a built finance page and fail if any visible labels or shapes overlap, or run off the frame.
// The engine publishes window.__boxes ({ name, box: [x0,y0,x1,y1], op }) for every label and named shape each frame.
// Boxes named "actor:…" (something meant to move in front of the scene) are skipped.
//   node check-overlaps.mjs page.html [--samples 600] [--min-op 0.3]
import { resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) { console.error("usage: check-overlaps.mjs <page.html> [--samples 600]"); process.exit(1); }
const samples = +(args.samples || 600), minOp = +(args["min-op"] || 0.3);

const browser = await launch();
const page = await browser.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(resolve(input)));
await page.evaluate(() => document.fonts.ready);
const { hits, edges, n } = await page.evaluate(({ samples, minOp }) => {
  const { width: W, height: H } = window.MOTION;
  const ts = [...Array(samples).keys()].map((i) => i / samples).concat(((window.FIN && window.FIN.beats) || []).map((b) => b.t));
  const found = new Map(), edge = new Map();
  for (const t of ts) {
    window.renderFrame(t);
    const bs = (window.__boxes || []).filter((b) => b.op >= minOp && !b.name.startsWith("actor:"));
    for (const b of bs) {
      const [x0, y0, x1, y1] = b.box;
      if (x0 < -1 || y0 < -1 || x1 > W + 1 || y1 > H + 1) edge.set(b.name, edge.get(b.name) ?? +t.toFixed(3));
    }
    for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
      const a = bs[i].box, b = bs[j].box;
      const ix = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), iy = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
      if (ix > 2 && iy > 2) {
        const key = [bs[i].name, bs[j].name].sort().join("  ×  "), prev = found.get(key);
        found.set(key, { t: prev ? prev.t : +t.toFixed(3), frames: (prev ? prev.frames : 0) + 1, area: Math.max(prev ? prev.area : 0, ix * iy) });
      }
    }
  }
  return { hits: [...found.entries()].map(([pair, v]) => ({ pair, ...v })), edges: [...edge.entries()], n: ts.length };
}, { samples, minOp });
await browser.close();

if (!hits.length && !edges.length) { console.log(`overlaps: none, clipping: none (${n} frames incl. every figure's built state)`); process.exit(0); }
if (hits.length) console.log(`overlaps: ${hits.length} pair(s) collide`);
for (const h of hits.sort((a, b) => b.frames - a.frames)) console.log(`  ${h.pair}   first at t=${h.t}, ${h.frames} frame(s), up to ${Math.round(h.area)} px²`);
if (edges.length) console.log(`clipping: ${edges.length} element(s) run past the frame edge`);
for (const [name, t] of edges) console.log(`  ${name}   first at t=${t}`);
process.exit(1);
