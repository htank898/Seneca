#!/usr/bin/env node
// Bundle a scene JSON + the engine into one self-contained HTML file.
//   node build.mjs scene.json [--out scene.html]
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { SKILL_DIR, parseArgs } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) { console.error("usage: build.mjs <scene.json> [--out file.html]"); process.exit(1); }
const scene = JSON.parse(readFileSync(resolve(input), "utf8"));
const shell = readFileSync(`${SKILL_DIR}/templates/scale-shell.html`, "utf8");
const engine = readFileSync(`${SKILL_DIR}/lib/scale-engine.js`, "utf8");
const out = resolve(args.out || input.replace(/\.json$/i, "") + ".html");
const esc = (s) => s.replace(/</g, "\\u003c");
const html = shell
  .replace("__TITLE__", () => (scene.title || "Scale").replace(/</g, "&lt;"))
  .replace("__SCENE__", () => esc(JSON.stringify(scene)))
  .replace("__ENGINE__", () => engine);
writeFileSync(out, html);
console.log(`html: ${out}`);
