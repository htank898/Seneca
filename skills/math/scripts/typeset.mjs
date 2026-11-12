#!/usr/bin/env node
// Typeset LaTeX math in any Seneca HTML page with KaTeX (MIT), at build time.
//
//   node typeset.mjs page.html [--out page.html] [--mathml] [--macros macros.json] [--check]
//
// Finds  $…$  \(…\)  (inline)  and  $$…$$  \[…\]  (display)  in text, plus
// <span class="tex">…</span> (inline) and <div class="tex">…</div> (display).
// Skips <script>, <style>, <code>, <pre>, <kbd>, <samp>, <textarea>, comments, and
// anything inside class="no-math". Write \$ for a literal dollar sign.
//
// The result needs no JavaScript and no network: KaTeX's CSS is inlined with only the
// fonts the page actually uses, embedded as base64 woff2. --mathml emits MathML only
// (no CSS, no fonts; smallest output, plainer look). A bad expression fails the run
// with its line number and KaTeX's message; nothing is written.
import { readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { SKILL_DIR, parseArgs, launch, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: typeset.mjs <page.html> [--out file.html] [--mathml] [--macros macros.json] [--check]");
  process.exit(1);
}
if (!existsSync(join(SKILL_DIR, "node_modules", "katex"))) {
  console.error("[setup] installing katex + playwright into", SKILL_DIR);
  execSync("npm install --silent --no-audit --no-fund", { cwd: SKILL_DIR, stdio: ["ignore", "inherit", "inherit"] });
}
const require = createRequire(join(SKILL_DIR, "package.json"));
const katex = require("katex");
const KATEX_DIST = join(dirname(require.resolve("katex/package.json")), "dist");

const inputPath = resolve(input);
const out = resolve(args.out || inputPath);
const src = readFileSync(inputPath, "utf8");
const mathml = !!args.mathml;
const macros = args.macros ? JSON.parse(readFileSync(resolve(args.macros), "utf8")) : {};

// ------------------------------------------------------------------ scanning
const SKIP = new Set(["script", "style", "code", "pre", "kbd", "samp", "textarea", "math", "svg"]);
// Already-typeset output is left alone, so running twice is harmless.
const NO_MATH = ["no-math", "katex", "katex-display"];
const ENT = { "&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#39;": "'", "&nbsp;": " ", "&#36;": "$" };
const decode = (s) => s.replace(/&(lt|gt|amp|quot|#39|nbsp|#36);/g, (m) => ENT[m]);
const lineOf = (i) => src.slice(0, i).split("\n").length;
const classes = (tag) => (/\bclass\s*=\s*(["'])([^"']*)\1/i.exec(tag)?.[2] || "").split(/\s+/);

const errors = [];
let count = 0;
function render(tex, display, at) {
  count++;
  try {
    return katex.renderToString(decode(tex).trim(), {
      displayMode: display, throwOnError: true, output: mathml ? "mathml" : "htmlAndMathml",
      macros: { ...macros }, strict: "warn", trust: false,
    });
  } catch (e) {
    errors.push(`  line ${lineOf(at)}: ${display ? "$$" : "$"}${tex.trim()}${display ? "$$" : "$"}\n    ${e.message}`);
    return "";
  }
}

// Math in a run of text. Display first, then inline. Pandoc's rule for $: the opening $
// is not followed by whitespace, the closing $ is not preceded by whitespace or followed by a digit.
function typesetText(text, offset) {
  const re = /\\\$|\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$(?!\s)((?:\\.|[^$\\])+?)(?<!\s)\$(?!\d)/g;
  return text.replace(re, (m, dd, br, pa, d, i) => {
    if (m === "\\$") return "&#36;";
    const at = offset + i;
    if (dd !== undefined) return render(dd, true, at);
    if (br !== undefined) return render(br, true, at);
    if (pa !== undefined) return render(pa, false, at);
    return render(d, false, at);
  });
}

// Walk tags and text; only text outside skipped elements is typeset.
const parts = [];
const tagRe = /<!--[\s\S]*?-->|<\/?([a-zA-Z][\w-]*)\b[^>]*>/g;
const stack = [];        // open skip-elements and no-math containers
let last = 0;
let m;
while ((m = tagRe.exec(src))) {
  const text = src.slice(last, m.index);
  parts.push(stack.length ? text : typesetText(text, last));
  const tag = m[0];
  const name = (m[1] || "").toLowerCase();
  last = tagRe.lastIndex;

  // <span class="tex">…</span> / <div class="tex">…</div>
  const texEl = !stack.length && classes(tag).includes("tex") && /^<(span|div)\b/i.exec(tag);
  if (texEl) {
    const close = src.indexOf(`</${texEl[1].toLowerCase()}>`, last);
    if (close !== -1) {
      const body = src.slice(last, close);
      parts.push(tag.replace(/\bclass\s*=\s*(["'])([^"']*)\1/i, (_, q, c) => `class=${q}${c.split(/\s+/).map((k) => (k === "tex" ? "tex-done" : k)).join(" ")}${q}`));
      parts.push(render(body, texEl[1].toLowerCase() === "div", last));
      parts.push(`</${texEl[1]}>`);
      last = close + texEl[1].length + 3;
      tagRe.lastIndex = last;
      continue;
    }
  }
  parts.push(tag);
  if (tag.startsWith("<!--") || tag.endsWith("/>")) continue;
  if (tag[1] === "/") {
    if (stack.length && stack[stack.length - 1] === name) stack.pop();
  } else if (SKIP.has(name)) {
    stack.push(name);
  } else if (classes(tag).some((c) => NO_MATH.includes(c)) && !/^(br|img|hr|input|meta|link)$/.test(name)) {
    stack.push(name);
  } else if (stack.length && stack[stack.length - 1] === name) {
    stack.push(name);    // nested same-name element inside a no-math container
  }
}
parts.push(stack.length ? src.slice(last) : typesetText(src.slice(last), last));

if (errors.length) {
  console.error(`[math] ${errors.length} expression(s) failed to typeset in ${inputPath}:\n${errors.join("\n")}`);
  process.exit(1);
}
let html = parts.join("");
console.error(`[math] typeset ${count} expression(s)`);
if (args.check) process.exit(0);

// ------------------------------------------------------------------ CSS + fonts
html = html.replace(/<style data-seneca-katex>[\s\S]*?<\/style>\n?/g, "");
const usesKatexHtml = !mathml && /class="katex/.test(html);
if (usesKatexHtml) {
  const css = readFileSync(join(KATEX_DIST, "katex.min.css"), "utf8");
  const faces = [...css.matchAll(/@font-face\{[^}]*\}/g)].map((f) => {
    const body = f[0];
    return {
      rule: body,
      family: /font-family:([^;]+)/.exec(body)[1].replace(/["']/g, ""),
      weight: /font-weight:([^;]+)/.exec(body)[1],
      style: /font-style:([^;]+)/.exec(body)[1],
      file: /url\((fonts\/[^)]+\.woff2)\)/.exec(body)[1],
    };
  });
  const used = await fontsUsed(html, css);
  const faceCss = faces.filter((f) => used === null || used.has(`${f.family}|${f.weight}|${f.style}`)).map((f) => {
    const b64 = readFileSync(join(KATEX_DIST, f.file)).toString("base64");
    return `@font-face{font-display:block;font-family:${f.family};font-style:${f.style};font-weight:${f.weight};src:url(data:font/woff2;base64,${b64}) format("woff2")}`;
  });
  const rest = css.replace(/@font-face\{[^}]*\}/g, "");
  const style = `<style data-seneca-katex>/* KaTeX ${katex.version} | Copyright (c) 2013-2020 Khan Academy and other contributors | MIT License: https://github.com/KaTeX/KaTeX/blob/main/LICENSE | inlined by math/typeset.mjs */\n${faceCss.join("\n")}\n${rest}</style>\n`;
  html = /<\/head>/i.test(html) ? html.replace(/<\/head>/i, `${style}</head>`) : style + html;
  console.error(`[math] inlined ${faceCss.length}/${faces.length} KaTeX fonts${used === null ? " (all: detection unavailable)" : ""}`);
}

writeFileSync(out, html);
console.log(`typeset: ${out}`);

// Render just the math in Chromium and ask which KaTeX faces actually loaded.
async function fontsUsed(page_html, css) {
  const probe = join(dirname(out), `.typeset-probe-${process.pid}.html`);
  const abs = css.replace(/url\(fonts\//g, `url(${fileUrl(join(KATEX_DIST, "fonts"))}/`);
  // the whole document body is used so no math is missed, with page CSS removed
  const body = page_html.replace(/<style[\s\S]*?<\/style>|<script[\s\S]*?<\/script>|<link[^>]*>/gi, "");
  writeFileSync(probe, `<!doctype html><meta charset="utf-8"><style>${abs}</style>${body}`);
  let browser;
  try {
    browser = await launch();
    const page = await browser.newPage();
    await page.goto(fileUrl(probe));
    await page.evaluate(() => document.fonts.ready);
    const loaded = await page.evaluate(() => [...document.fonts].filter((f) => f.status === "loaded")
      .map((f) => `${f.family.replace(/["']/g, "")}|${f.weight === "bold" ? "700" : f.weight === "normal" ? "400" : f.weight}|${f.style}`));
    return new Set(loaded);
  } catch (e) {
    console.error(`[math] font detection failed (${e.message.split("\n")[0]}); inlining all fonts`);
    return null;
  } finally {
    if (browser) await browser.close();
    try { rmSync(probe); } catch {}
  }
}
