#!/usr/bin/env node
// Render one PNG per stop (the held steps) of a built scale page, for slides and docs.
//   node render-steps.mjs scene.html [--out-dir dir] [--scale 1]
import { mkdirSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) { console.error("usage: render-steps.mjs <scene.html> [--out-dir dir] [--scale 2]"); process.exit(1); }
const inputPath = resolve(input);
const outDir = resolve(args["out-dir"] || dirname(inputPath));
const name = basename(inputPath).replace(/\.html?$/i, "");
mkdirSync(outDir, { recursive: true });

const browser = await launch();
const context = await browser.newContext({ deviceScaleFactor: +(args.scale || 1) });
const page = await context.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);
const { width, height } = await page.evaluate(() => window.MOTION);
await page.setViewportSize({ width, height });
const stops = await page.evaluate(() => window.SCENE_STOPS);
await page.evaluate(() => window.renderFrame(0));
await page.waitForTimeout(150); // let the resized viewport settle before the first capture
for (let i = 0; i < stops.length; i++) {
  await page.evaluate((t) => window.renderFrame(t), stops[i].t);
  const file = join(outDir, `${name}.step-${i + 1}.png`);
  await page.screenshot({ path: file, clip: { x: 0, y: 0, width, height } });
  console.log(`step: ${file}`);
}
await browser.close();
