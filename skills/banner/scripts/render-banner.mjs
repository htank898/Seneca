#!/usr/bin/env node
// Render an HTML banner to a static PNG.
// The page must define   window.BANNER = { width, height, safe?: [...], maxMB? }
// (templates/banner-shell.html resolves this from a platform preset).
//   node render-banner.mjs banner.html [--out banner.png] [--scale 2]
//     [--theme name[,name...]] [--guides]
// --theme renders once per theme, setting <html data-theme="name">, to banner.<name>.png.
// --guides also writes banner[.<name>].guides.png with the platform's safe areas drawn on top.
import { statSync } from "node:fs";
import { resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-banner.mjs <banner.html> [--out banner.png] [--scale 2] [--theme a,b] [--guides]");
  process.exit(1);
}
const inputPath = resolve(input);
const base = resolve(args.out ? args.out.replace(/\.png$/i, "") : inputPath.replace(/\.html?$/i, ""));
const scale = +(args.scale || 2);
const themes = typeof args.theme === "string" ? args.theme.split(",").map((s) => s.trim()).filter(Boolean) : [null];

const browser = await launch();
const probe = await browser.newPage();
await probe.goto(fileUrl(inputPath), { waitUntil: "networkidle" });
const spec = await probe.evaluate(() => window.BANNER || null);
await probe.close();
if (!spec || !spec.width || !spec.height) {
  console.error("page does not define window.BANNER = { width, height }");
  await browser.close();
  process.exit(1);
}

const page = await browser.newPage({ viewport: { width: spec.width, height: spec.height }, deviceScaleFactor: scale });
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath), { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

const clip = { x: 0, y: 0, width: spec.width, height: spec.height };
const mb = (p) => statSync(p).size / 1048576;
for (const theme of themes) {
  await page.evaluate((t) => {
    if (t) document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    document.getElementById("__guides")?.remove();
  }, theme);
  const stem = theme ? `${base}.${theme}` : base;
  const out = `${stem}.png`;
  await page.screenshot({ path: out, clip });
  console.log(`png: ${out} (${spec.width * scale}x${spec.height * scale}, ${(mb(out) * 1024).toFixed(0)} KB)`);
  if (spec.maxMB && mb(out) > spec.maxMB) {
    console.warn(`warning: over the platform's ${spec.maxMB} MB limit. Try --scale 1 or flatter fills.`);
  }

  if (args.guides) {
    await page.evaluate((zones) => {
      const g = document.createElement("div");
      g.id = "__guides";
      g.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:2147483647;font:600 12px/1.2 system-ui,sans-serif";
      for (const z of zones || []) {
        const d = document.createElement("div");
        const clear = z.kind !== "keep-inside";
        d.style.cssText = `position:absolute;left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;` +
          (clear
            ? "background:repeating-linear-gradient(45deg,rgba(230,40,40,.28) 0 6px,transparent 6px 12px);outline:2px solid rgba(230,40,40,.9)"
            : "outline:2px dashed rgba(20,160,90,.95);outline-offset:-2px") +
          (z.round ? ";border-radius:50%" : "");
        const tag = document.createElement("span");
        tag.textContent = z.label || (clear ? "keep clear" : "keep text inside");
        tag.style.cssText = `position:absolute;left:4px;top:4px;padding:2px 5px;color:#fff;background:${clear ? "rgba(200,30,30,.9)" : "rgba(15,130,70,.95)"}`;
        d.appendChild(tag);
        g.appendChild(d);
      }
      document.body.appendChild(g);
    }, spec.safe);
    const gout = `${stem}.guides.png`;
    await page.screenshot({ path: gout, clip });
    console.log(`guides: ${gout}`);
  }
}
await browser.close();
