#!/usr/bin/env node
// Render each figure of a finance page (built by finance.mjs) as a PNG still, fully built, for slides and posts.
//   node render-stills.mjs page.html [--out-dir dir] [--only payback,field] [--scale 2]
// Writes <page>-<fig>-<view>.png. For the looping GIF/MP4 use ai-gif's render-gif.mjs on the same page.
import { mkdirSync, statSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) { console.error("usage: render-stills.mjs <page.html> [--out-dir dir] [--only view,view] [--scale 2]"); process.exit(1); }
const inputPath = resolve(input);
const outDir = resolve(args["out-dir"] || dirname(inputPath));
const only = args.only ? String(args.only).split(",") : null;
const scale = +(args.scale || 1);
mkdirSync(outDir, { recursive: true });

const browser = await launch();
const page = await (await browser.newContext({ deviceScaleFactor: scale })).newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);
const info = await page.evaluate(() => ({ motion: window.MOTION, beats: window.FIN && window.FIN.beats }));
if (!info.beats) { console.error("page has no window.FIN; build it with finance.mjs"); await browser.close(); process.exit(1); }
await page.setViewportSize({ width: info.motion.width, height: info.motion.height });
// Let Chromium repaint at the new size before the first screenshot (otherwise it can capture stale tiles).
const settle = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
await settle();
const stem = basename(inputPath).replace(/\.html?$/i, "");
for (const b of info.beats) {
  if (only && !only.includes(b.view)) continue;
  await page.evaluate((t) => window.renderFrame(t), b.t);
  await settle();
  const out = join(outDir, `${stem}-${b.fig}-${b.view}.png`);
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: info.motion.width, height: info.motion.height } });
  console.log(`png: ${out} (${info.motion.width * scale}×${info.motion.height * scale}, ${(statSync(out).size / 1024).toFixed(0)} KB)`);
}
await browser.close();
