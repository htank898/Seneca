#!/usr/bin/env node
// Screenshot every step of a guide (built on templates/guide-shell.html) for QA,
// thumbnails, or a README.  Optionally stitch the steps into a GIF walkthrough.
//   node render-steps.mjs guide.html [--out-dir dir] [--width 1440] [--height 900] [--gif] [--seconds-per-step 2.5]
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-steps.mjs <guide.html> [--out-dir dir] [--width 1440] [--height 900] [--gif]");
  process.exit(1);
}
const inputPath = resolve(input);
const name = basename(inputPath).replace(/\.html?$/i, "");
const outDir = resolve(args["out-dir"] || join(dirname(inputPath), name + "-steps"));
mkdirSync(outDir, { recursive: true });

const width = +(args.width || 1440), height = +(args.height || 900);
const browser = await launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
await page.emulateMedia({ reducedMotion: "reduce" });
await page.goto(fileUrl(inputPath), { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const count = await page.evaluate(() => window.guide?.count);
if (!count) {
  console.error("no window.guide found: is this built on guide-shell.html?");
  await browser.close();
  process.exit(1);
}
const files = [];
for (let i = 0; i < count; i++) {
  await page.evaluate((i) => window.guide.go(i), i);
  await page.waitForTimeout(150);
  const p = join(outDir, `step-${String(i + 1).padStart(2, "0")}.png`);
  await page.screenshot({ path: p });
  files.push(p);
}
await browser.close();
console.log(`steps: ${count} screenshots in ${outDir}`);

if (args.gif) {
  const sps = +(args["seconds-per-step"] || 2.5);
  const gif = join(dirname(inputPath), name + "-walkthrough.gif");
  execFileSync("ffmpeg", [
    "-y", "-loglevel", "error", "-framerate", String(1 / sps), "-i", join(outDir, "step-%02d.png"),
    "-vf", "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
    "-loop", "0", gif,
  ], { stdio: "inherit" });
  console.log(`gif: ${gif}`);
}
