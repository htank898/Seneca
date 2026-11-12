#!/usr/bin/env node
// Record the layout of a real web app so a guide can rebuild it accurately.
// Captures STRUCTURE ONLY: each visible interactive element and landmark with its
// role, accessible name, and bounding box, plus one reference screenshot.
// It does not save the page's HTML, CSS, scripts, or images.
//
//   node capture-ui-map.mjs <url> [--out ui-map] [--width 1440] [--height 900]
//        [--headed] [--profile ./.guide-profile] [--wait]
//
// --headed --profile DIR --wait : opens a visible browser with a persistent profile so
//   YOU can sign in and navigate to the screen to capture, then press Enter in the
//   terminal. Never script someone's credentials.
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createInterface } from "node:readline";
import { createRequire } from "node:module";
import { join } from "node:path";
import { launch, parseArgs, SKILL_DIR } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const url = args._[0];
if (!url) {
  console.error("usage: capture-ui-map.mjs <url> [--out ui-map] [--headed --profile dir --wait]");
  process.exit(1);
}
const out = resolve(args.out || "ui-map");
const width = +(args.width || 1440), height = +(args.height || 900);

let context, browser;
if (args.profile) {
  await launch().then((b) => b.close()); // ensures Playwright is installed
  const { chromium } = createRequire(join(SKILL_DIR, "package.json"))("playwright");
  context = await chromium.launchPersistentContext(resolve(args.profile), {
    headless: !args.headed, viewport: { width, height },
  });
} else {
  browser = await launch();
  context = await browser.newContext({ viewport: { width, height } });
}
const page = context.pages()[0] || (await context.newPage());
await page.goto(url, { waitUntil: "domcontentloaded" });

if (args.wait) {
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  await new Promise((r) => rl.question("Navigate to the screen to capture, then press Enter here... ", r));
  rl.close();
}
await page.waitForTimeout(1000);

const map = await page.evaluate(() => {
  const SEL = "a[href], button, input, select, textarea, [role=button], [role=link], [role=tab], [role=menuitem], [role=search], [role=combobox], [contenteditable=true], header, nav, main, aside, footer, [role=banner], [role=navigation], [role=main], [role=complementary], h1, h2, h3";
  const roleOf = (el) => el.getAttribute("role") || ({ A: "link", BUTTON: "button", INPUT: "textbox", SELECT: "combobox", TEXTAREA: "textbox", HEADER: "banner", NAV: "navigation", MAIN: "main", ASIDE: "complementary", FOOTER: "contentinfo", H1: "heading", H2: "heading", H3: "heading" })[el.tagName] || el.tagName.toLowerCase();
  const nameOf = (el) => (el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("placeholder") || el.innerText || el.value || "").replace(/\s+/g, " ").trim().slice(0, 80);
  const out = [];
  for (const el of document.querySelectorAll(SEL)) {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width < 4 || r.height < 4 || cs.visibility === "hidden" || cs.display === "none") continue;
    if (r.bottom < 0 || r.top > innerHeight * 3) continue;
    out.push({
      role: roleOf(el), name: nameOf(el),
      x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
      bg: cs.backgroundColor, color: cs.color, radius: cs.borderRadius, font: `${cs.fontWeight} ${cs.fontSize}`,
    });
  }
  return {
    url: location.origin + location.pathname, title: document.title,
    viewport: { width: innerWidth, height: innerHeight },
    body: { bg: getComputedStyle(document.body).backgroundColor, font: getComputedStyle(document.body).fontFamily },
    elements: out,
  };
});
writeFileSync(out + ".json", JSON.stringify(map, null, 2));
await page.screenshot({ path: out + ".png" });
await context.close();
if (browser) await browser.close();
console.log(`ui map: ${out}.json (${map.elements.length} elements), screenshot: ${out}.png`);
console.log("Review both before using them: accessible names can include other people's names or messages. Keep raw captures out of public repos.");
