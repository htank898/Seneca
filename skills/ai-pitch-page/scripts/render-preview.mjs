#!/usr/bin/env node
// Render a pitch page's link-preview image from its #preview-card block.
//
//   node scripts/render-preview.mjs path/to/index.html [--out preview.png]
//
// Loads the page in preview mode (?preview plus a data-preview attribute on <html>) at a
// 1200x627 viewport, waits for fonts, and screenshots exactly the #preview-card element.
// Default output: preview.png beside the page.
import { statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const W = 1200, H = 627;
const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-preview.mjs <index.html> [--out preview.png]");
  process.exit(1);
}
const inputPath = resolve(input);
try { statSync(inputPath); } catch { console.error(`no such file: ${inputPath}`); process.exit(1); }
const out = resolve(typeof args.out === "string" ? args.out : join(dirname(inputPath), "preview.png"));

const browser = await launch();
let code = 0;
try {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.error("[page error]", e.message));
  await page.goto(fileUrl(inputPath) + "?preview", { waitUntil: "load" });
  await page.evaluate(() => document.documentElement.setAttribute("data-preview", ""));
  await page.evaluate(() => document.fonts.ready);

  const card = await page.$("#preview-card");
  if (!card) {
    console.error(`error: ${inputPath} has no #preview-card element. Add one (see templates/pitch-shell.html).`);
    code = 2;
  } else {
    const box = await card.boundingBox();
    if (!box || box.width < 1 || box.height < 1) {
      console.error("error: #preview-card is not visible in preview mode. Check the html[data-preview] CSS rules.");
      code = 2;
    } else {
      if (Math.round(box.width) !== W || Math.round(box.height) !== H) {
        console.warn(`warning: #preview-card is ${Math.round(box.width)}x${Math.round(box.height)}, expected ${W}x${H}.`);
      }
      await card.screenshot({ path: out });
      const kb = (statSync(out).size / 1024).toFixed(0);
      console.log(`preview: ${out} (${Math.round(box.width)}x${Math.round(box.height)}, ${kb} KB)`);
    }
  }
} finally {
  await browser.close();
}
process.exit(code);
