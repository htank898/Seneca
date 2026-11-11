#!/usr/bin/env node
// Render a deterministic HTML motion graphic to a looping GIF (and optionally MP4).
//
// The page must define   window.renderFrame(t)   where t is in [0, 1). It may return a
// promise (for example while a footage frame loads); each frame waits for it.
// It may define          window.MOTION = { width, height, fps, seconds, audio }
//   audio: { src: "talk.footage/audio.wav", segments: [{ from, to, at }] } (paths relative
//   to the HTML; segments place source seconds [from, to) at output second `at`, and
//   anything not covered is silence. Chalk.timeline(...).audioSegments() builds them.)
// CLI flags override MOTION:
//   node render-gif.mjs motion.html [--out motion.gif] [--width 1080] [--height 1080]
//     [--fps 24] [--seconds 6] [--scale 1] [--colors 256] [--dither sierra2_4a]
//     [--mp4] [--mp4-loops 3] [--video] [--keep-frames] [--budget-mb 5]
//   --video writes only an MP4 that plays once, with the page's audio if it has any.
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, rmdirSync, statSync, existsSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-gif.mjs <motion.html> [--out file.gif] [--fps N] [--seconds N] [--mp4]");
  process.exit(1);
}
const inputPath = resolve(input);
const video = !!args.video;
const out = resolve(args.out || inputPath.replace(/\.html?$/i, "") + (video ? ".mp4" : ".gif")).replace(/\.mp4$/i, ".gif");
const framesDir = join(dirname(out), ".frames", basename(out, ".gif"));
let mp4 = out.replace(/\.gif$/i, ".mp4");

try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); }
catch { console.error("ffmpeg is required (macOS: brew install ffmpeg)"); process.exit(1); }

const browser = await launch();
const page = await browser.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);

const motion = await page.evaluate(() => window.MOTION || {});
// Never write over the video the footage came from (talk.html next to talk.mp4).
const footageDir = await page.evaluate(() => window.FOOTAGE && window.FOOTAGE.dir);
if (footageDir && basename(mp4, ".mp4") + ".footage" === footageDir) mp4 = mp4.replace(/\.mp4$/i, ".chalk.mp4");
const width = +(args.width || motion.width || 1080);
const height = +(args.height || motion.height || 1080);
const fps = +(args.fps || motion.fps || 24);
const seconds = +(args.seconds || motion.seconds || 6);
const scale = +(args.scale || 1);
const colors = +(args.colors || 256);
const dither = args.dither || "sierra2_4a";
const total = Math.round(fps * seconds);

await page.setViewportSize({ width, height });
const hasRender = await page.evaluate(() => typeof window.renderFrame === "function");
if (!hasRender) {
  console.error("page does not define window.renderFrame(t)");
  await browser.close();
  process.exit(1);
}

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });
console.error(`[gif] ${width}x${height} @ ${fps}fps, ${seconds}s = ${total} frames`);
for (let i = 0; i < total; i++) {
  await page.evaluate((t) => window.renderFrame(t), i / total); // awaits a returned promise
  await page.screenshot({ path: join(framesDir, `f${String(i).padStart(5, "0")}.png`) });
  if (i % 24 === 0) process.stderr.write(`\r[gif] frame ${i + 1}/${total}`);
}
process.stderr.write(`\r[gif] captured ${total} frames      \n`);
await browser.close();

const outW = Math.round(width * scale);
const pattern = join(framesDir, "f%05d.png");
const mb = (p) => (statSync(p).size / 1048576).toFixed(2);
if (!video) {
execFileSync("ffmpeg", [
  "-y", "-loglevel", "error", "-framerate", String(fps), "-i", pattern,
  "-vf", `scale=${outW}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=${colors}:stats_mode=diff[p];[b][p]paletteuse=dither=${dither}:diff_mode=rectangle`,
  "-loop", "0", out,
], { stdio: "inherit" });

console.log(`gif: ${out} (${mb(out)} MB)`);
const budget = +(args["budget-mb"] || 5);
if (statSync(out).size > budget * 1048576) {
  console.warn(`warning: over ${budget} MB. Try --scale 0.75, --colors 128, --fps 20, or flatter colors.`);
}
}

if (args.mp4 || video) {
  const loops = video ? 1 : +(args["mp4-loops"] || 3);
  const audio = motion.audio && motion.audio.src ? motion.audio : null;
  const ff = ["-y", "-loglevel", "error", "-stream_loop", String(loops - 1), "-framerate", String(fps), "-i", pattern];
  const vf = `[0:v]scale=${outW - (outW % 2)}:-2:flags=lanczos[v]`;
  let filter = vf, maps = ["-map", "[v]"];
  if (audio && loops === 1) {
    const src = resolve(dirname(inputPath), audio.src);
    if (!existsSync(src)) { console.error(`audio not found: ${src}`); process.exit(1); }
    ff.push("-i", src);
    const segs = audio.segments || [{ from: 0, to: seconds, at: 0 }];
    const parts = segs.map((s, i) =>
      `[1:a]atrim=start=${s.from}:end=${s.to},asetpts=PTS-STARTPTS,adelay=${Math.round(s.at * 1000)}:all=1[a${i}]`);
    const mix = segs.length > 1
      ? `${segs.map((_, i) => `[a${i}]`).join("")}amix=inputs=${segs.length}:normalize=0:dropout_transition=0,apad[aout]`
      : `[a0]apad[aout]`;
    filter = [vf, ...parts, mix].join(";");
    maps = ["-map", "[v]", "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", "-t", String(total / fps)];
  } else if (audio) {
    console.warn("note: audio is only added to single-pass MP4s (use --video or --mp4-loops 1)");
  }
  execFileSync("ffmpeg", [
    ...ff, "-filter_complex", filter, ...maps,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", mp4,
  ], { stdio: "inherit" });
  console.log(`mp4: ${mp4} (${mb(mp4)} MB, ${loops === 1 ? "plays once" : loops + " loops"}${audio && loops === 1 ? ", with audio" : ""})`);
}

if (!args["keep-frames"]) {
  rmSync(framesDir, { recursive: true, force: true });
  const parent = dirname(framesDir);
  try { if (existsSync(parent)) rmdirSync(parent); } catch {}
}
