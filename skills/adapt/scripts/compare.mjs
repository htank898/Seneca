#!/usr/bin/env node
// Side-by-side review sheets: what the art target / source looked like vs what Blender rendered.
//
//   Images, one row per comma-separated group (left to right):
//     node compare.mjs --out cmp.png concept/turnaround.png,turn_0.png,turn_90.png,turn_180.png
//   Videos, the same frame numbers pulled from each (1-based), one row per frame:
//     node compare.mjs --out cmp.png --videos ref.mp4,preview.mp4[,omni.mp4] --frames 1,48,96,150
//   Options: --height 360 (row height in px)
//
// No text labels (drawtext isn't in every ffmpeg build): columns are in the order given, rows in
// the order given, and the script prints that legend. Use the sheet for self-review (Read it) and
// as the render input for a Nano Banana paint-over.
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const argv = process.argv.slice(2);
const flags = {};
const groups = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith("--")) {
    const k = argv[i].slice(2);
    flags[k] = i + 1 < argv.length && !argv[i + 1].startsWith("--") ? argv[++i] : true;
  } else groups.push(argv[i].split(",").filter(Boolean));
}
if (!flags.out || (!groups.length && !flags.videos)) {
  console.error("usage: compare.mjs --out cmp.png a.png,b.png [c.png,d.png ...]\n" +
    "       compare.mjs --out cmp.png --videos ref.mp4,render.mp4 --frames 1,48,96");
  process.exit(1);
}
const H = Number(flags.height || 360);
const tmp = mkdtempSync(join(tmpdir(), "seneca-cmp-"));
const ff = (args) => {
  const r = spawnSync("ffmpeg", ["-v", "error", "-y", ...args], { encoding: "utf8" });
  if (r.status !== 0) { console.error(r.stderr); process.exit(1); }
};

let rows = groups.map((g) => g.map((p) => resolve(p)));
if (flags.videos) {
  const vids = String(flags.videos).split(",").map((p) => resolve(p));
  const frames = String(flags.frames || "1").split(",").map(Number);
  rows = frames.map((f) => vids.map((v, j) => {
    const out = join(tmp, `v${j}_f${f}.png`);
    ff(["-i", v, "-vf", `select=eq(n\\,${f - 1})`, "-frames:v", "1", out]);
    if (!existsSync(out)) { console.error(`frame ${f} not in ${v}`); process.exit(1); }
    return out;
  }));
}

// each row: scale every image to height H, hstack with a 6px gap; then vstack rows padded to the widest
const rowFiles = rows.map((row, r) => {
  const out = join(tmp, `row${r}.png`);
  if (row.length === 1) { ff(["-i", row[0], "-vf", `scale=-2:${H}`, out]); return out; }
  const inputs = row.flatMap((p) => ["-i", p]);
  const sc = row.map((_, i) => `[${i}]scale=-2:${H},pad=iw+6:ih:0:0:white[s${i}]`).join(";");
  ff([...inputs, "-filter_complex", `${sc};${row.map((_, i) => `[s${i}]`).join("")}hstack=${row.length}[o]`,
      "-map", "[o]", out]);
  return out;
});
const out = resolve(flags.out);
if (rowFiles.length === 1) ff(["-i", rowFiles[0], out]);
else {
  const probe = rowFiles.map((f) => Number(spawnSync("ffprobe", ["-v", "error", "-show_entries", "stream=width",
    "-of", "csv=p=0", f], { encoding: "utf8" }).stdout.trim()));
  const W = Math.max(...probe);
  const pads = rowFiles.map((_, i) => `[${i}]pad=${W}:ih+6:0:0:white[r${i}]`).join(";");
  ff([...rowFiles.flatMap((f) => ["-i", f]), "-filter_complex",
      `${pads};${rowFiles.map((_, i) => `[r${i}]`).join("")}vstack=${rowFiles.length}[o]`, "-map", "[o]", out]);
}
rmSync(tmp, { recursive: true, force: true });
console.log(`[compare] ${out}`);
if (flags.videos) {
  console.log(`[compare] columns: ${String(flags.videos).split(",").join(" | ")}`);
  console.log(`[compare] rows: frames ${flags.frames || "1"}`);
} else rows.forEach((r, i) => console.log(`[compare] row ${i + 1}: ${r.map((p) => p.split("/").pop()).join(" | ")}`));
