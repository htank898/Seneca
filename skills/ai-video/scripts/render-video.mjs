#!/usr/bin/env node
// Render a narrated MP4 from a deterministic HTML animation + Kokoro voice-over.
//
// Inputs:  animation.html   defines  window.renderFrame(t, info)   (t in SECONDS)
//          voice/timings.json + voice/NN-*.wav   (written by scripts/tts.py)
// Before any page script runs, the renderer injects
//   window.VIDEO = { width, height, fps, duration, scenes: [{ id, index, start, end, from, to, text, show }] }
// so the animation can time itself to the narration. start/end bound the spoken line;
// from/to bound the scene on screen (cuts land in the silence between lines).
//
// Outputs (next to --out): name.mp4 (H.264 yuv420p + AAC, faststart), name.vtt, name.srt,
// and voice/narration.wav (the joined track, for previewing the HTML with sound).
//
//   node render-video.mjs animation.html [--timings voice/timings.json] [--out name.mp4]
//     [--width 1080] [--height 1080] [--fps 30] [--burn-captions] [--keep-frames]
//     [--lufs -16] [--true-peak -1.5] [--crf 20] [--audio-bitrate 128k] [--budget-mb 10]
//     [--audio-only] [--captions-only]
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, rmSync, rmdirSync, statSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-video.mjs <animation.html> [--timings voice/timings.json] [--out video.mp4] [--burn-captions]");
  process.exit(1);
}
const inputPath = resolve(input);
const timingsPath = resolve(args.timings || join(dirname(inputPath), "voice", "timings.json"));
if (!existsSync(timingsPath)) {
  console.error(`no timings at ${timingsPath}. Run scripts/tts.py on your scenes.json first, or pass --timings.`);
  process.exit(1);
}
const voiceDir = dirname(timingsPath);
const timings = JSON.parse(readFileSync(timingsPath, "utf8"));
const out = resolve(args.out || inputPath.replace(/\.html?$/i, "") + ".mp4");
const stem = out.replace(/\.mp4$/i, "");
const framesDir = join(dirname(out), ".frames", basename(stem));
const workDir = join(dirname(out), ".frames", basename(stem) + "-audio");

try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); }
catch { console.error("ffmpeg is required (macOS: brew install ffmpeg)"); process.exit(1); }

const fps = +(args.fps || 30);
const width = +(args.width || 1080);
const height = +(args.height || 1080);
if (width % 2 || height % 2) { console.error("width and height must be even for yuv420p"); process.exit(1); }
const lufs = +(args.lufs ?? -16);
const truePeak = +(args["true-peak"] ?? -1.5);
const crf = String(args.crf || 20);
const audioBitrate = args["audio-bitrate"] || "128k";
const totalFrames = Math.ceil(timings.duration * fps);
const duration = totalFrames / fps;               // video and audio are both cut to exactly this

/* ------------------------------------------------------------------ audio */
function readWav(path) {
  const b = readFileSync(path);
  if (b.toString("ascii", 0, 4) !== "RIFF" || b.toString("ascii", 8, 12) !== "WAVE") throw new Error(`${path}: not a WAV`);
  let off = 12, fmt = null, data = null;
  while (off + 8 <= b.length) {
    const id = b.toString("ascii", off, off + 4), size = b.readUInt32LE(off + 4);
    if (id === "fmt ") fmt = { format: b.readUInt16LE(off + 8), channels: b.readUInt16LE(off + 10), rate: b.readUInt32LE(off + 12), bits: b.readUInt16LE(off + 22) };
    if (id === "data") data = b.subarray(off + 8, off + 8 + size);
    off += 8 + size + (size & 1);
  }
  if (!fmt || !data) throw new Error(`${path}: missing fmt/data chunk`);
  if (fmt.format !== 1 || fmt.bits !== 16 || fmt.channels !== 1) throw new Error(`${path}: expected 16-bit mono PCM`);
  return { rate: fmt.rate, samples: new Int16Array(data.buffer.slice(data.byteOffset, data.byteOffset + data.length)) };
}

function writeWav(path, samples, rate) {
  const h = Buffer.alloc(44);
  h.write("RIFF", 0); h.writeUInt32LE(36 + samples.length * 2, 4); h.write("WAVE", 8);
  h.write("fmt ", 12); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22);
  h.writeUInt32LE(rate, 24); h.writeUInt32LE(rate * 2, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34);
  h.write("data", 36); h.writeUInt32LE(samples.length * 2, 40);
  writeFileSync(path, Buffer.concat([h, Buffer.from(samples.buffer, samples.byteOffset, samples.length * 2)]));
}

// Place every scene's WAV at its exact start sample; silence everywhere else.
function buildNarration() {
  const rate = timings.sampleRate || 24000;
  const track = new Int16Array(Math.round(duration * rate));
  for (const s of timings.scenes) {
    const w = readWav(join(voiceDir, s.file));
    if (w.rate !== rate) throw new Error(`${s.file}: ${w.rate} Hz, expected ${rate}`);
    const at = Math.round(s.start * rate);
    track.set(w.samples.subarray(0, Math.max(0, Math.min(w.samples.length, track.length - at))), at);
  }
  const p = join(voiceDir, "narration.wav");
  writeWav(p, track, rate);
  return p;
}

// Two-pass EBU R128 loudness normalization (linear gain when possible), resampled to 48 kHz.
function normalize(src, dst) {
  const target = `I=${lufs}:TP=${truePeak}:LRA=11`;
  const pass1 = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", src, "-af", `loudnorm=${target}:print_format=json`, "-f", "null", "-"], { encoding: "utf8" });
  const m = pass1.stderr.match(/\{[\s\S]*?"input_i"[\s\S]*?\}/);
  if (!m) throw new Error("loudnorm measurement failed:\n" + pass1.stderr.slice(-800));
  const j = JSON.parse(m[0]);
  const af = `loudnorm=${target}:measured_I=${j.input_i}:measured_TP=${j.input_tp}:measured_LRA=${j.input_lra}:measured_thresh=${j.input_thresh}:offset=${j.target_offset}:linear=true:print_format=summary`;
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", "48000", "-ac", "1", dst], { stdio: "inherit" });
  return j;
}

function measure(path) {
  const r = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], { encoding: "utf8" });
  const tail = r.stderr.slice(r.stderr.lastIndexOf("Summary:"));
  const num = (re) => { const x = tail.match(re); return x ? +x[1] : NaN; };
  return { I: num(/I:\s+(-?[\d.]+) LUFS/), LRA: num(/LRA:\s+(-?[\d.]+) LU/), peak: num(/Peak:\s+(-?[\d.]+) dBFS/) };
}

/* --------------------------------------------------------------- captions */
const MAX_CHARS = 42, MAX_LINES = 2, MAX_CUE = 6.0;

// Wrap into at most MAX_LINES balanced lines of <= MAX_CHARS, or null if it can't fit.
function wrap(text) {
  if (text.length <= MAX_CHARS) return [text];
  const words = text.split(" ");
  let best = null;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" "), b = words.slice(i).join(" ");
    if (a.length <= MAX_CHARS && b.length <= MAX_CHARS) {
      // Balanced, slightly bottom-heavy; prefer breaking after punctuation, never after a function word.
      const weak = /\b(a|an|the|to|of|and|or|in|on|for|with|is|are|that|your|my|it's)$/i.test(a);
      const score = Math.abs(a.length - b.length) + (a.length > b.length ? 3 : 0) - (/[,.;:!?]$/.test(a) ? 8 : 0) + (weak ? 20 : 0);
      if (!best || score < best.score) best = { lines: [a, b], score };
    }
  }
  return best ? best.lines : null;
}

// Split a spoken line into sentence/clause units, keeping trailing punctuation.
function units(text) {
  const parts = text.match(/[^.!?;:,—]+[.!?;:,—]*["')\]]*\s*/g) || [text];
  return parts.map((p) => p.trim()).filter(Boolean);
}

function chunkWords(u) {
  const words = u.split(" "), outp = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? cur + " " + w : w;
    if (wrap(next)) cur = next; else { if (cur) outp.push(cur); cur = w; }
  }
  if (cur) outp.push(cur);
  return outp;
}

function buildCues() {
  const cues = [];
  timings.scenes.forEach((s, si) => {
    const secPerChar = s.duration / Math.max(1, s.text.length);
    const pieces = [];
    for (const u of units(s.text)) (wrap(u) ? [u] : chunkWords(u)).forEach((p) => pieces.push(p));
    // Greedily merge pieces into cues that fit 2x42 and <= MAX_CUE seconds.
    const groups = [];
    let cur = "";
    for (const p of pieces) {
      const next = cur ? cur + " " + p : p;
      const newSentence = /[.!?]["')\]]*$/.test(cur);
      const tooLong = !wrap(next) || next.length * secPerChar > MAX_CUE;
      const breakAtSentence = newSentence && next.length > MAX_CHARS;   // don't make a 2-line cue from two sentences
      if (cur && (tooLong || breakAtSentence)) { groups.push(cur); cur = p; } else cur = next;
    }
    if (cur) groups.push(cur);
    // Time each cue proportionally to its share of the characters in the spoken line.
    const total = groups.reduce((a, g) => a + g.length, 0);
    let t = s.start;
    groups.forEach((g, gi) => {
      const d = s.duration * (g.length / total);
      let end = t + d;
      if (gi === groups.length - 1) {
        const next = timings.scenes[si + 1];
        end = Math.min(s.end + 0.3, next ? next.start - 0.05 : duration);   // brief hold after the line
      }
      cues.push({ start: t, end, lines: wrap(g) });
      t += d;
    });
  });
  return cues;
}

const ts = (x, sep) => {
  const ms = Math.round(x * 1000), h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}${sep}${String(ms % 1000).padStart(3, "0")}`;
};
function writeCaptions(cues) {
  const vtt = "WEBVTT\n\n" + cues.map((c, i) => `${i + 1}\n${ts(c.start, ".")} --> ${ts(c.end, ".")}\n${c.lines.join("\n")}\n`).join("\n");
  const srt = cues.map((c, i) => `${i + 1}\n${ts(c.start, ",")} --> ${ts(c.end, ",")}\n${c.lines.join("\n")}\n`).join("\n");
  writeFileSync(stem + ".vtt", vtt);
  writeFileSync(stem + ".srt", srt);
}

/* ------------------------------------------------------------------- run */
const cues = buildCues();
writeCaptions(cues);
console.error(`[video] ${cues.length} caption cues -> ${basename(stem)}.vtt / .srt`);
if (args["captions-only"]) process.exit(0);

const narration = buildNarration();
console.error(`[video] narration track ${duration.toFixed(3)}s -> ${narration}`);
if (args["audio-only"]) process.exit(0);

rmSync(workDir, { recursive: true, force: true });
mkdirSync(workDir, { recursive: true });
const normWav = join(workDir, "narration-norm.wav");
const before = normalize(narration, normWav);
console.error(`[video] loudness ${before.input_i} LUFS -> target ${lufs} LUFS (TP ${truePeak} dBTP)`);

const VIDEO = {
  width, height, fps, duration, frames: totalFrames,
  scenes: timings.scenes.map(({ id, index, start, end, from, to, text, show }) => ({ id, index, start, end, from, to, text, show: show || {} })),
};

const browser = await launch();
const page = await browser.newPage({ viewport: { width, height } });
await page.addInitScript((v) => { window.__CAPTURE__ = true; window.VIDEO = v; }, VIDEO);
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);
if (!(await page.evaluate(() => typeof window.renderFrame === "function"))) {
  console.error("page does not define window.renderFrame(t, info)");
  await browser.close();
  process.exit(1);
}
if (args["burn-captions"]) {
  await page.evaluate(({ w, h }) => {
    const box = document.createElement("div");
    box.id = "__burned_captions__";
    const fs = Math.round(Math.min(w, h) * 0.042);
    Object.assign(box.style, {
      position: "fixed", left: "50%", bottom: Math.round(h * 0.07) + "px", transform: "translateX(-50%)",
      maxWidth: Math.round(w * 0.86) + "px", zIndex: 2147483647, textAlign: "center", pointerEvents: "none",
      font: `600 ${fs}px/1.3 -apple-system, "Helvetica Neue", Arial, sans-serif`, color: "#fff",
      background: "rgba(10,12,14,.78)", padding: `${Math.round(fs * 0.3)}px ${Math.round(fs * 0.6)}px`,
      borderRadius: Math.round(fs * 0.3) + "px", whiteSpace: "pre", display: "none",
    });
    document.body.appendChild(box);
  }, { w: width, h: height });
}

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });
console.error(`[video] ${width}x${height} @ ${fps}fps, ${duration.toFixed(2)}s = ${totalFrames} frames`);
const sceneAt = (t) => { let k = 0; VIDEO.scenes.forEach((s, i) => { if (t >= s.from) k = i; }); return k; };
for (let i = 0; i < totalFrames; i++) {
  const t = i / fps;
  const cue = args["burn-captions"] ? cues.find((c) => t >= c.start && t < c.end) : null;
  await page.evaluate(({ t, info, caption }) => {
    window.renderFrame(t, info);
    const box = document.getElementById("__burned_captions__");
    if (box) { box.textContent = caption || ""; box.style.display = caption ? "block" : "none"; }
  }, { t, info: { frame: i, fps, duration, progress: t / duration, scene: sceneAt(t) }, caption: cue ? cue.lines.join("\n") : "" });
  await page.screenshot({ path: join(framesDir, `f${String(i).padStart(5, "0")}.png`) });
  if (i % 30 === 0) process.stderr.write(`\r[video] frame ${i + 1}/${totalFrames}`);
}
process.stderr.write(`\r[video] captured ${totalFrames} frames      \n`);
await browser.close();

execFileSync("ffmpeg", [
  "-y", "-loglevel", "error",
  "-framerate", String(fps), "-i", join(framesDir, "f%05d.png"),
  "-i", normWav,
  "-map", "0:v", "-map", "1:a",
  "-c:v", "libx264", "-preset", "slow", "-crf", crf, "-tune", "animation", "-pix_fmt", "yuv420p", "-r", String(fps),
  "-c:a", "aac", "-b:a", audioBitrate, "-ar", "48000",
  "-af", `apad,atrim=0:${duration.toFixed(6)}`, "-t", duration.toFixed(6),
  "-movflags", "+faststart", out,
], { stdio: "inherit" });

rmSync(workDir, { recursive: true, force: true });
if (!args["keep-frames"]) rmSync(framesDir, { recursive: true, force: true });
try { rmdirSync(dirname(framesDir)); } catch {}

const probe = (sel, entries) => execFileSync("ffprobe", ["-v", "error", "-select_streams", sel, "-show_entries", entries, "-of", "csv=p=0", out], { encoding: "utf8" }).trim();
const vInfo = probe("v:0", "stream=codec_name,pix_fmt,width,height,duration");
const aInfo = probe("a:0", "stream=codec_name,sample_rate,duration");
const loud = measure(out);
const mb = (statSync(out).size / 1048576).toFixed(2);
console.log(`mp4: ${out} (${mb} MB, ${duration.toFixed(2)}s)`);
console.log(`  video ${vInfo}`);
console.log(`  audio ${aInfo}`);
console.log(`  loudness ${loud.I} LUFS integrated, LRA ${loud.LRA} LU, true peak ${loud.peak} dBFS (target ${lufs} LUFS)`);
console.log(`captions: ${stem}.vtt, ${stem}.srt (${cues.length} cues${args["burn-captions"] ? ", also burned in" : ""})`);
console.log(`narration: ${narration}`);
if (args["keep-frames"]) console.log(`frames: ${framesDir}`);
const budget = +(args["budget-mb"] || 10);
if (statSync(out).size > budget * 1048576) console.warn(`warning: over ${budget} MB. Try --crf 24, --fps 24, or flatter, less-moving visuals.`);
