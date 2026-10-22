#!/usr/bin/env node
// Export an HTML deck (built on templates/deck-shell.html) to a one-slide-per-page PDF.
//   node render-deck-pdf.mjs deck.html [--out deck.pdf] [--png]
// --png also writes deck.slide-N.png (every build revealed) for visual QA or thumbnails.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-deck-pdf.mjs <deck.html> [--out deck.pdf] [--png]");
  process.exit(1);
}
const inputPath = resolve(input);
const base = inputPath.replace(/\.html?$/i, "");
const out = resolve(args.out || base + ".pdf");

const browser = await launch();
const page = await browser.newPage();
await page.goto(fileUrl(inputPath), { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const info = await page.evaluate(() => window.deck && { count: window.deck.count, w: window.deck.width, h: window.deck.height });
if (!info) {
  console.error("no window.deck found: is this built on deck-shell.html?");
  await browser.close();
  process.exit(1);
}
await page.setViewportSize({ width: info.w, height: info.h });
await page.addStyleTag({ content: ":root{--dur:1ms !important} #progress,#counter{display:none!important}" });

if (args.png) {
  for (let i = 0; i < info.count; i++) {
    await page.evaluate((i) => window.deck.go(i, Infinity), i);
    await page.waitForTimeout(60);
    const p = `${base}.slide-${i + 1}.png`;
    await page.screenshot({ path: p });
    console.log(`png: ${p}`);
  }
}

await page.emulateMedia({ media: "print" });
await page.pdf({ path: out, width: `${info.w}px`, height: `${info.h}px`, printBackground: true, preferCSSPageSize: true });
await browser.close();

const pdf = readFileSync(out);
const pages = (pdf.toString("latin1").match(/\/Type\s*\/Page(?![s\w])/g) || []).length;
console.log(`pdf: ${out} (${pages} pages for ${info.count} slides, ${info.w}x${info.h}, ${(pdf.length / 1024).toFixed(0)} KB)`);
if (pages !== info.count) console.warn("warning: page count != slide count. Check for slide content overflowing its frame.");
