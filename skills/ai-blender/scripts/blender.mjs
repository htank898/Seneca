#!/usr/bin/env node
// Run a bkit scene script in Blender with no window and render it.
//
//   node blender.mjs scene.py [--out render.png] [--preview] [--engine EEVEE|CYCLES]
//     [--samples N] [--res 1920x1080] [--anim] [--frames 1-120] [--frame N]
//     [--blend scene.blend] [--glb model.glb] [--no-render] [--open] [--any-custom-flag value]
//
// Every flag after the scene path is forwarded to the script (read with bkit.arg()).
// Blender is found via $BLENDER, then /Applications/Blender.app, then PATH.
import { spawnSync, execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const [scenePath, ...rest] = process.argv.slice(2);
if (!scenePath) {
  console.error("usage: blender.mjs <scene.py> [--out render.png] [--preview] [--engine CYCLES] [--blend out.blend]");
  process.exit(1);
}

function findBlender() {
  const candidates = [
    process.env.BLENDER,
    "/Applications/Blender.app/Contents/MacOS/Blender",
    `${process.env.HOME}/Applications/Blender.app/Contents/MacOS/Blender`,
  ].filter(Boolean);
  for (const c of candidates) if (existsSync(c)) return c;
  try { return execFileSync("which", ["blender"], { encoding: "utf8" }).trim(); } catch {}
  console.error("Blender not found. Install it from blender.org or set BLENDER=/path/to/blender.");
  process.exit(1);
}

const blender = findBlender();
const open = rest.includes("--open");
const fwd = rest.filter((a) => a !== "--open");
const outIdx = fwd.indexOf("--out");
const out = outIdx >= 0 ? resolve(fwd[outIdx + 1]) : resolve(scenePath.replace(/\.py$/i, "") + ".png");
if (outIdx >= 0) fwd[outIdx + 1] = out; else fwd.push("--out", out);
for (const flag of ["--blend", "--glb"]) {
  const i = fwd.indexOf(flag);
  if (i >= 0) fwd[i + 1] = resolve(fwd[i + 1]);
}

// Blender's bundled Python ignores PYTHONPATH, so put bkit on sys.path before the scene runs.
const args = [
  "-b", "--factory-startup", "--python-exit-code", "1",
  "--python-expr", `import sys; sys.path.insert(0, ${JSON.stringify(here)})`,
  "-P", resolve(scenePath), "--", ...fwd,
];
const t0 = Date.now();
const res = spawnSync(blender, args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

// Blender is chatty; keep our own lines, Python errors, and Blender warnings.
const lines = `${res.stdout}\n${res.stderr}`.split("\n");
const keep = lines.filter((l) =>
  /^\[bkit\]|Traceback|Error|error:|Warning|^\s+File "|^\s{2,}\S/.test(l) && !/^Fra:/.test(l));
if (keep.length) console.log(keep.join("\n"));
if (res.status !== 0) {
  console.error(`blender exited with ${res.status} after ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  if (!keep.length) console.error(lines.slice(-40).join("\n"));
  process.exit(res.status || 1);
}
console.log(`[run] done in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (open) {
  const blendIdx = fwd.indexOf("--blend");
  spawnSync("open", [blendIdx >= 0 ? fwd[blendIdx + 1] : out]);
}
