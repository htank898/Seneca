#!/usr/bin/env node
// Tracking pass: footage -> track.json (+ track.js for file:// pages).
//
// Runs MediaPipe Face Landmarker inside headless Chromium (launched through the
// ai-gif skill's _browser.mjs), seeks a <video> frame by frame, and records the
// 52 ARKit-style blendshapes plus head pose (yaw/pitch/roll, degrees) from the
// facial transformation matrix. Every channel is then One Euro filtered.
//
//   node experiments/face-puppet/track.mjs [source.mp4] [--fps 30]
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, writeFileSync, createReadStream, statSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, parseArgs } from "../../skills/ai-gif/scripts/_browser.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const args = parseArgs(process.argv.slice(2));
const src = resolve(args._[0] || join(HERE, "source.mp4"));
const fps = +(args.fps || 30);
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
const cache = join(HERE, ".cache");
mkdirSync(cache, { recursive: true });

// 1. Model (3.6 MB, cached, gitignored).
const modelPath = join(cache, "face_landmarker.task");
if (!existsSync(modelPath)) {
  console.error("[track] downloading face_landmarker.task");
  const res = await fetch(MODEL_URL);
  if (!res.ok) throw new Error(`model download failed: ${res.status}`);
  writeFileSync(modelPath, Buffer.from(await res.arrayBuffer()));
}

// 2. Playwright's Chromium has no H.264 decoder, so track a VP9 copy.
const webm = join(cache, "source.webm");
if (!existsSync(webm) || statSync(webm).mtimeMs < statSync(src).mtimeMs) {
  console.error("[track] transcoding to VP9 for Chromium");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-an", "-r", String(fps),
    "-c:v", "libvpx-vp9", "-crf", "20", "-b:v", "0", "-g", "1", "-deadline", "realtime", "-cpu-used", "8", webm]);
}
const total = +execFileSync("ffprobe", ["-v", "error", "-count_frames", "-select_streams", "v:0",
  "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", webm]).toString().trim();
const [vw, vh] = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
  "-show_entries", "stream=width,height", "-of", "csv=p=0", webm]).toString().trim().split(",").map(Number);

// 3. Tiny static server: wasm + model + video need http://, not file://.
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".wasm": "application/wasm", ".webm": "video/webm", ".task": "application/octet-stream" };
const routes = {
  "/vision.mjs": join(HERE, "node_modules/@mediapipe/tasks-vision/vision_bundle.mjs"),
  "/model.task": modelPath,
  "/video.webm": webm,
};
const server = createServer((req, res) => {
  const url = req.url.split("?")[0];
  let p = routes[url];
  if (!p && url.startsWith("/wasm/")) p = join(HERE, "node_modules/@mediapipe/tasks-vision", url);
  if (url === "/") { res.writeHead(200, { "content-type": "text/html" }); return res.end(PAGE); }
  if (!p || !existsSync(p)) { res.writeHead(404); return res.end(); }
  const size = statSync(p).size;
  const range = /bytes=(\d+)-(\d*)/.exec(req.headers.range || "");
  const head = { "content-type": MIME[extname(p)] || "application/octet-stream", "accept-ranges": "bytes" };
  if (range) {
    const a = +range[1], b = range[2] ? +range[2] : size - 1;
    res.writeHead(206, { ...head, "content-range": `bytes ${a}-${b}/${size}`, "content-length": b - a + 1 });
    return createReadStream(p, { start: a, end: b }).pipe(res);
  }
  res.writeHead(200, { ...head, "content-length": size });
  createReadStream(p).pipe(res);
});
const PAGE = `<!doctype html><body><video id="v" src="/video.webm" muted playsinline preload="auto"></video>
<script type="module">
import { FilesetResolver, FaceLandmarker } from "/vision.mjs";
const fileset = await FilesetResolver.forVisionTasks("/wasm");
const lm = await FaceLandmarker.createFromOptions(fileset, {
  baseOptions: { modelAssetPath: "/model.task", delegate: "CPU" },
  runningMode: "VIDEO", numFaces: 1,
  outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
});
const v = document.getElementById("v");
await new Promise((r) => v.readyState >= 2 ? r() : v.addEventListener("loadeddata", r, { once: true }));
const seek = (t) => new Promise((r) => { v.addEventListener("seeked", r, { once: true }); v.currentTime = t; });
window.trackFrame = async (i, fps) => {
  await seek((i + 0.5) / fps);                  // mid-frame: never lands on a boundary
  const out = lm.detectForVideo(v, Math.round(i * 1000 / fps) + 1);
  if (!out.faceBlendshapes.length) return null;
  const bs = {};
  for (const c of out.faceBlendshapes[0].categories) bs[c.categoryName] = c.score;
  const lmk = out.faceLandmarks[0];
  return { bs, m: Array.from(out.facialTransformationMatrixes[0].data),
           nose: [lmk[1].x, lmk[1].y] };   // face position in frame, for camera-follow
};
window.ready = true;
</script>`;
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await launch();
const page = await browser.newPage();
page.on("console", (m) => m.type() === "error" && console.error("[page]", m.text()));
await page.goto(base + "/");
await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });

// 4. Per-frame capture.
const DEG = 180 / Math.PI;
// MediaPipe returns a column-major 4x4; R[row][col] = m[col*4+row].
// Angles are in the camera frame: +yaw = head turns to the subject's left
// (viewer's right), +pitch = chin up, +roll = head tilts toward the viewer's right.
function pose(m) {
  const R = (r, c) => m[c * 4 + r];
  return {
    yaw: Math.asin(Math.max(-1, Math.min(1, -R(2, 0)))) * DEG,
    pitch: Math.atan2(R(2, 1), R(2, 2)) * DEG,
    roll: Math.atan2(R(1, 0), R(0, 0)) * DEG,
  };
}
const raw = [];
let names = null, misses = 0;
for (let i = 0; i < total; i++) {
  const f = await page.evaluate(([i, fps]) => window.trackFrame(i, fps), [i, fps]);
  if (!f) { misses++; raw.push(raw.length ? raw[raw.length - 1] : null); continue; }
  names ??= Object.keys(f.bs);
  const p = pose(f.m);
  raw.push({ ...Object.fromEntries(names.map((n) => [n, f.bs[n]])),
    yaw: p.yaw, pitch: p.pitch, roll: p.roll, faceX: f.nose[0], faceY: f.nose[1] });
  if (i % 30 === 0) process.stderr.write(`\r[track] frame ${i + 1}/${total}`);
}
process.stderr.write(`\r[track] tracked ${total} frames (${misses} without a face)\n`);
await browser.close();
server.close();
if (!names) throw new Error("no face found in any frame");
for (let i = 0; i < raw.length; i++) raw[i] ??= raw.find(Boolean);   // leading misses

// 5. One Euro filter (Casiez et al. 2012). Low jitter when still, low lag when fast.
function oneEuro(xs, { minCutoff = 1, beta = 0, dCutoff = 1 } = {}) {
  const alpha = (fc) => { const tau = 1 / (2 * Math.PI * fc); return 1 / (1 + tau * fps); };
  const out = []; let xPrev = xs[0], dxPrev = 0;
  for (let i = 0; i < xs.length; i++) {
    const dx = i ? (xs[i] - xPrev) * fps : 0;
    const dxHat = dxPrev + alpha(dCutoff) * (dx - dxPrev);
    const fc = minCutoff + beta * Math.abs(dxHat);
    const x = i ? xPrev + alpha(fc) * (xs[i] - xPrev) : xs[i];
    out.push(x); xPrev = x; dxPrev = dxHat;
  }
  return out;
}
// Blinks are fast and binary: barely smooth them or they never fully close.
// Pose and brows are slow and jittery: smooth hard, let speed open it up.
const PARAMS = (k) =>
  /^eyeBlink/.test(k) ? { minCutoff: 4, beta: 0.5 } :
  /^(jaw|mouth)/.test(k) ? { minCutoff: 3, beta: 0.3 } :
  /^(yaw|pitch|roll)$/.test(k) ? { minCutoff: 0.8, beta: 0.02 } :
  /^face[XY]$/.test(k) ? { minCutoff: 0.6, beta: 1 } :
  { minCutoff: 1.5, beta: 0.2 };
const channels = [...names, "yaw", "pitch", "roll", "faceX", "faceY"];
const filtered = {};
const jitter = {};
for (const k of channels) {
  const xs = raw.map((r) => r[k]);
  filtered[k] = oneEuro(xs, PARAMS(k));
  // Mean abs second difference: a cheap "how jittery is this channel" number for NOTES.
  const d2 = (a) => a.slice(2).reduce((s, x, i) => s + Math.abs(x - 2 * a[i + 1] + a[i]), 0) / (a.length - 2);
  jitter[k] = { raw: +d2(xs).toFixed(4), filtered: +d2(filtered[k]).toFixed(4) };
}

const r3 = (x) => Math.round(x * 1000) / 1000;
const track = {
  source: src.split("/").pop(), fps, frames: total, seconds: total / fps, width: vw, height: vh,
  channels,
  // frames[i][c] = filtered value of channels[c] at frame i (compact, row per frame)
  data: Array.from({ length: total }, (_, i) => channels.map((k) => r3(filtered[k][i]))),
  raw: Array.from({ length: total }, (_, i) => channels.map((k) => r3(raw[i][k]))),
  jitter,
};
writeFileSync(join(HERE, "track.json"), JSON.stringify(track));
writeFileSync(join(HERE, "track.js"), "window.TRACK = " + JSON.stringify(track) + ";\n");
console.log(`track.json: ${total} frames x ${channels.length} channels @ ${fps} fps (${(total / fps).toFixed(2)} s)`);
