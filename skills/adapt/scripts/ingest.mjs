#!/usr/bin/env node
// Ingest a reference video: probe it, find the shots, pull keyframes, and build a contact sheet.
//
//   node ingest.mjs ref.mp4 [--out dir] [--every 2] [--threshold 0.3] [--trim 4.5-12] [--cols 4]
//
// Writes to --out (default: <video name>/ next to the video):
//   info.json        width, height, fps, duration, frame count
//   shots.json       [{ index, start, end, duration }] from ffmpeg scene detection
//   frames/          keyframes s01_t003.250.jpg (shot 1, at 3.25 s): every shot's start and middle, plus one every --every seconds
//   contact.png      every keyframe tiled in time order (row-major), and frames.json mapping tile index -> time
//   ref.mp4          only with --trim: the working clip (start-end seconds, re-encoded, constant frame rate)
//
// With --trim, everything above is computed on the trimmed clip. Pose capture and the
// Blender timeline then share frame 1 = the trimmed clip's first frame.
// Only needs ffmpeg/ffprobe (the drawtext filter is NOT required).
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";

const argv = process.argv.slice(2);
const flags = {};
const pos = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith("--")) {
    const k = argv[i].slice(2);
    if (i + 1 < argv.length && !argv[i + 1].startsWith("--")) flags[k] = argv[++i];
    else flags[k] = true;
  } else pos.push(argv[i]);
}
if (!pos[0]) {
  console.error("usage: ingest.mjs ref.mp4 [--out dir] [--every 2] [--threshold 0.3] [--trim 4.5-12] [--cols 4]");
  process.exit(1);
}

const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { encoding: "utf8", maxBuffer: 256 * 1024 * 1024, ...opts });
  if (r.status !== 0) {
    console.error(`${cmd} failed:\n${(r.stderr || "").slice(-3000)}`);
    process.exit(1);
  }
  return r;
};

let src = resolve(pos[0]);
if (!existsSync(src)) { console.error(`not found: ${src}`); process.exit(1); }
const out = resolve(flags.out || join(dirname(src), basename(src, extname(src))));
mkdirSync(out, { recursive: true });

function probe(file) {
  const r = run("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries",
    "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", file]);
  const j = JSON.parse(r.stdout);
  const s = j.streams[0];
  const [n, d] = s.r_frame_rate.split("/").map(Number);
  const fps = n / (d || 1);
  const duration = Number(j.format.duration);
  return { width: s.width, height: s.height, fps: Math.round(fps * 1000) / 1000, duration,
           frames: Number(s.nb_frames) || Math.round(duration * fps) };
}

if (flags.trim) {
  const [a, b] = String(flags.trim).split("-").map(Number);
  if (!(b > a)) { console.error("--trim wants start-end in seconds, e.g. 4.5-12"); process.exit(1); }
  const srcFps = probe(src).fps;
  const trimmed = join(out, "ref.mp4");
  // Accurate seek (after -i), constant frame rate, so frame N of ref.mp4 is unambiguous.
  run("ffmpeg", ["-v", "error", "-y", "-i", src, "-ss", String(a), "-t", String(b - a),
    "-r", String(srcFps), "-fps_mode", "cfr", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
    "-an", trimmed]);
  console.log(`[ingest] trimmed ${a}-${b}s -> ${trimmed}`);
  src = trimmed;
}

const info = { source: src, ...probe(src) };
writeFileSync(join(out, "info.json"), JSON.stringify(info, null, 2));

// Shot detection: frames whose scene-change score beats the threshold start a new shot.
const threshold = Number(flags.threshold || 0.3);
const det = spawnSync("ffmpeg", ["-v", "info", "-i", src, "-an", "-vf",
  `select='gt(scene,${threshold})',showinfo`, "-f", "null", "-"], { encoding: "utf8", maxBuffer: 256 * 1024 * 1024 });
const cuts = [...(det.stderr || "").matchAll(/showinfo.*pts_time:([\d.]+)/g)].map((m) => Number(m[1]))
  .filter((t) => t > 0.2 && t < info.duration - 0.2);
const bounds = [0, ...cuts, info.duration];
const shots = [];
for (let i = 0; i < bounds.length - 1; i++) {
  if (bounds[i + 1] - bounds[i] < 0.25) continue; // flash frames, not shots
  shots.push({ index: shots.length + 1, start: +bounds[i].toFixed(3), end: +bounds[i + 1].toFixed(3),
               duration: +(bounds[i + 1] - bounds[i]).toFixed(3) });
}
writeFileSync(join(out, "shots.json"), JSON.stringify(shots, null, 2));

// Keyframe times: each shot's start (nudged in past the cut) and middle, plus every N seconds.
const every = Number(flags.every || 2);
const times = [];
for (const s of shots) {
  const pts = [s.start + Math.min(0.15, s.duration / 4), s.start + s.duration / 2];
  for (let t = s.start + every; t < s.end - 0.2; t += every) pts.push(t);
  for (const t of pts) times.push({ shot: s.index, t: Math.min(t, info.duration - 1 / info.fps) });
}
times.sort((a, b) => a.t - b.t);
const keep = times.filter((x, i) => i === 0 || x.t - times[i - 1].t > 0.4);

const framesDir = join(out, "frames");
rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });
const frameList = keep.map((k, i) => {
  const name = `s${String(k.shot).padStart(2, "0")}_t${k.t.toFixed(3).padStart(7, "0")}.jpg`;
  run("ffmpeg", ["-v", "error", "-y", "-ss", k.t.toFixed(3), "-i", src, "-frames:v", "1", "-q:v", "3",
    join(framesDir, name)]);
  return { tile: i + 1, shot: k.shot, time: +k.t.toFixed(3), frame: Math.floor(k.t * info.fps) + 1, file: `frames/${name}` };
});
writeFileSync(join(out, "frames.json"), JSON.stringify(frameList, null, 2));

// Contact sheet: tiles in time order. No text (drawtext isn't in every ffmpeg build);
// frames.json maps tile number (row-major, from 1) to time.
const cols = Number(flags.cols || 4);
const rows = Math.ceil(frameList.length / cols);
const tileW = 400;
const inputs = frameList.flatMap((f) => ["-i", join(out, f.file)]);
const scale = frameList.map((_, i) => `[${i}]scale=${tileW}:-2,pad=iw+6:ih+6:3:3:color=white[t${i}]`).join(";");
const pads = frameList.length < rows * cols
  ? `;color=c=black:s=${tileW + 6}x${Math.round((tileW * info.height) / info.width / 2) * 2 + 6}:d=1[blank]`
  : "";
let labels = frameList.map((_, i) => `[t${i}]`).join("");
let n = frameList.length;
if (pads) {
  const missing = rows * cols - n;
  const split = missing > 1 ? `;[blank]split=${missing}${Array.from({ length: missing }, (_, i) => `[b${i}]`).join("")}` : "";
  labels += missing > 1 ? Array.from({ length: missing }, (_, i) => `[b${i}]`).join("") : "[blank]";
  n = rows * cols;
  const graph = `${scale}${pads}${split};${labels}xstack=inputs=${n}:layout=${layout(cols, n)}[o]`;
  sheet(graph);
} else {
  sheet(`${scale};${labels}xstack=inputs=${n}:layout=${layout(cols, n)}[o]`);
}

function layout(c, count) {
  const cells = [];
  for (let i = 0; i < count; i++) {
    const col = i % c, row = Math.floor(i / c);
    const x = col === 0 ? "0" : Array.from({ length: col }, () => "w0").join("+");
    const y = row === 0 ? "0" : Array.from({ length: row }, () => "h0").join("+");
    cells.push(`${x}_${y}`);
  }
  return cells.join("|");
}
function sheet(graph) {
  if (frameList.length === 1) {
    run("ffmpeg", ["-v", "error", "-y", "-i", join(out, frameList[0].file), "-vf", `scale=${tileW}:-2`, join(out, "contact.png")]);
    return;
  }
  run("ffmpeg", ["-v", "error", "-y", ...inputs, "-filter_complex", graph, "-map", "[o]", "-frames:v", "1",
    join(out, "contact.png")]);
}

console.log(`[ingest] ${info.width}x${info.height} @ ${info.fps} fps, ${info.duration.toFixed(2)} s, ${info.frames} frames`);
console.log(`[ingest] ${shots.length} shot(s):`);
for (const s of shots) console.log(`  shot ${s.index}: ${s.start.toFixed(2)}-${s.end.toFixed(2)} s (${s.duration.toFixed(2)} s)`);
console.log(`[ingest] ${frameList.length} keyframes -> ${framesDir}`);
console.log(`[ingest] contact sheet (${cols} per row, tiles numbered row-major from 1): ${join(out, "contact.png")}`);
for (const f of frameList) console.log(`  tile ${String(f.tile).padStart(2)}  shot ${f.shot}  t=${f.time.toFixed(2)}s  frame ${f.frame}`);
