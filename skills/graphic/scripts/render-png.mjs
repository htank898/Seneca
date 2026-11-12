#!/usr/bin/env node
// Render every .artboard in an HTML graphic to its own image file.
//
// The page must use templates/graphic-shell.html (it exposes window.ARTBOARDS and window.__solo).
//   node render-png.mjs graphic.html [--out-dir dir] [--only name[,name]] [--scale 2]
//     [--jpg] [--quality 90] [--guides] [--budget-mb 5]
import { mkdirSync, statSync } from "node:fs";
import { dirname, join, resolve, basename } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-png.mjs <graphic.html> [--out-dir dir] [--only name] [--scale 2] [--jpg] [--guides]");
  process.exit(1);
}
const inputPath = resolve(input);
const outDir = resolve(args["out-dir"] || dirname(inputPath));
const scale = +(args.scale || 1);
const jpg = !!args.jpg;
const quality = +(args.quality || 90);
const budget = +(args["budget-mb"] || 5);
const only = args.only ? String(args.only).split(",") : null;
mkdirSync(outDir, { recursive: true });

const browser = await launch();
const context = await browser.newContext({ deviceScaleFactor: scale });
const page = await context.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);
await page.waitForLoadState("networkidle");

const boards = await page.evaluate(() => window.ARTBOARDS);
if (!Array.isArray(boards) || !boards.length) {
  console.error("no artboards found (is the page built from templates/graphic-shell.html?)");
  await browser.close();
  process.exit(1);
}
const names = boards.map((b) => b.name);
const dupes = names.filter((n, i) => names.indexOf(n) !== i);
if (dupes.length) console.warn(`warning: duplicate artboard names ${[...new Set(dupes)].join(", ")}; later ones overwrite earlier`);

// One viewport big enough for every artboard. Resizing between shots at scale > 1 tiles the capture.
await page.setViewportSize({ width: Math.max(...boards.map((b) => b.w)), height: Math.max(...boards.map((b) => b.h)) });

const mb = (p) => (statSync(p).size / 1048576).toFixed(2);
for (const b of boards) {
  if (only && !only.includes(b.name)) continue;
  const passes = [{ guides: false, suffix: "" }];
  if (args.guides) passes.push({ guides: true, suffix: ".guides" });
  for (const { guides, suffix } of passes) {
    await page.evaluate(([n, g]) => window.__solo(n, g), [b.name, guides]);
    const asJpg = jpg && !guides;
    if (asJpg && b.transparent) console.warn(`warning: ${b.name} is transparent; JPG has no alpha, so it gets a white background`);
    const file = join(outDir, `${b.name}${suffix}.${asJpg ? "jpg" : "png"}`);
    await page.screenshot({
      path: file,
      clip: { x: 0, y: 0, width: b.w, height: b.h },
      omitBackground: b.transparent && !asJpg,
      ...(asJpg ? { type: "jpeg", quality } : {}),
    });
    console.log(`${guides ? "guides" : "image "}: ${file} (${b.w * scale}×${b.h * scale}, ${mb(file)} MB)`);
    if (!guides && statSync(file).size > budget * 1048576) {
      console.warn(`warning: ${basename(file)} is over ${budget} MB. Try --jpg, --scale 1, or flatter fills.`);
    }
  }
}
await browser.close();
