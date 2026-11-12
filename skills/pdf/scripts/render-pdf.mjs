#!/usr/bin/env node
// Render an HTML document to a print-accurate PDF.
// Paper size and margins come from the page's CSS @page rule.
//   node render-pdf.mjs doc.html [--out doc.pdf] [--preview]
// --preview also writes doc.page-N.png screenshots of each .page element for visual QA.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-pdf.mjs <doc.html> [--out doc.pdf] [--preview]");
  process.exit(1);
}
const inputPath = resolve(input);
const base = inputPath.replace(/\.html?$/i, "");
const out = resolve(args.out || base + ".pdf");

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
await page.goto(fileUrl(inputPath), { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

if (args.preview) {
  const pages = await page.$$(".page");
  for (let i = 0; i < pages.length; i++) {
    const p = `${base}.page-${i + 1}.png`;
    await pages[i].screenshot({ path: p });
    console.log(`preview: ${p}`);
  }
}

await page.emulateMedia({ media: "print" });
await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
await browser.close();

// Page count and size from the PDF itself (Chromium writes plain /Type /Page objects).
const pdf = readFileSync(out).toString("latin1");
const count = (pdf.match(/\/Type\s*\/Page(?![s\w])/g) || []).length;
const box = pdf.match(/\/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]/);
let size = "";
if (box) {
  const w = +box[3] - +box[1], h = +box[4] - +box[2];
  size = `${(w / 72).toFixed(2)}in x ${(h / 72).toFixed(2)}in (${Math.round(w)}x${Math.round(h)}pt)`;
}
const kb = (readFileSync(out).length / 1024).toFixed(0);
console.log(`pdf: ${out} (${count} page${count === 1 ? "" : "s"}, ${size}, ${kb} KB)`);
