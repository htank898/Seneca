#!/usr/bin/env node
// Render a deterministic HTML motion graphic to a looping GIF (and optionally MP4).
//
// The page must define   window.renderFrame(t)   where t is in [0, 1).
// It may define          window.MOTION = { width, height, fps, seconds }
// CLI flags override MOTION:
//   node render-gif.mjs motion.html [--out motion.gif] [--width 1080] [--height 1080]
//     [--fps 24] [--seconds 6] [--scale 1] [--colors 256] [--dither sierra2_4a]
//     [--mp4] [--mp4-loops 3] [--no-audio] [--keep-frames] [--budget-mb 5]
// If the page defines window.SOUND cues, the MP4 gets a soundtrack synthesized offline
// with the Web Audio API (works headless; no audio device or sound files needed).
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, rmdirSync, statSync, existsSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl, SKILL_DIR } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: render-gif.mjs <motion.html> [--out file.gif] [--fps N] [--seconds N] [--mp4]");
  process.exit(1);
}
const inputPath = resolve(input);
const out = resolve(args.out || inputPath.replace(/\.html?$/i, "") + ".gif");
const framesDir = join(dirname(out), ".frames", basename(out, ".gif"));

try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); }
catch { console.error("ffmpeg is required (macOS: brew install ffmpeg)"); process.exit(1); }

const browser = await launch();
const page = await browser.newPage();
await page.addInitScript(() => { window.__CAPTURE__ = true; });
await page.goto(fileUrl(inputPath));
await page.evaluate(() => document.fonts.ready);

const motion = await page.evaluate(() => window.MOTION || {});
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
  await page.evaluate((t) => window.renderFrame(t), i / total);
  await page.screenshot({ path: join(framesDir, `f${String(i).padStart(5, "0")}.png`) });
  if (i % 24 === 0) process.stderr.write(`\r[gif] frame ${i + 1}/${total}`);
}
process.stderr.write(`\r[gif] captured ${total} frames      \n`);

const loops = +(args["mp4-loops"] || 3);
const audioPath = join(framesDir, "audio.wav");
let hasAudio = false;
if (args.mp4 && !args["no-audio"]) {
  const cues = await page.evaluate(() => (window.SOUND && window.SOUND.cues && window.SOUND.cues.length) || 0);
  if (cues) {
    // Pages made before the sound engine existed can still declare SOUND; borrow the template's engine.
    if (!(await page.evaluate(() => !!window.SFX))) {
      const shell = readFileSync(join(SKILL_DIR, "templates", "motion-shell.html"), "utf8");
      await page.addScriptTag({ content: shell.match(/<script id="sfx-engine">([\s\S]*?)<\/script>/)[1] });
    }
    const b64 = await page.evaluate((o) => window.SFX.render(o), { seconds, loops });
    writeFileSync(audioPath, Buffer.from(b64, "base64"));
    hasAudio = true;
    console.error(`[gif] rendered soundtrack: ${cues} cues x ${loops} loops`);
  }
}
await browser.close();

const outW = Math.round(width * scale);
const pattern = join(framesDir, "f%05d.png");
execFileSync("ffmpeg", [
  "-y", "-loglevel", "error", "-framerate", String(fps), "-i", pattern,
  "-vf", `scale=${outW}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=${colors}:stats_mode=diff[p];[b][p]paletteuse=dither=${dither}:diff_mode=rectangle`,
  "-loop", "0", out,
], { stdio: "inherit" });

const mb = (p) => (statSync(p).size / 1048576).toFixed(2);
console.log(`gif: ${out} (${mb(out)} MB)`);
const budget = +(args["budget-mb"] || 5);
if (statSync(out).size > budget * 1048576) {
  console.warn(`warning: over ${budget} MB. Try --scale 0.75, --colors 128, --fps 20, or flatter colors.`);
}

if (args.mp4) {
  const mp4 = out.replace(/\.gif$/i, ".mp4");
  const audio = hasAudio
    ? ["-i", audioPath, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    : [];
  execFileSync("ffmpeg", [
    "-y", "-loglevel", "error", "-stream_loop", String(loops - 1),
    "-framerate", String(fps), "-i", pattern, ...audio,
    "-vf", `scale=${outW - (outW % 2)}:-2:flags=lanczos`,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", mp4,
  ], { stdio: "inherit" });
  console.log(`mp4: ${mp4} (${mb(mp4)} MB, ${loops} loops${hasAudio ? ", with sound" : ""})`);
}

if (!args["keep-frames"]) {
  rmSync(framesDir, { recursive: true, force: true });
  const parent = dirname(framesDir);
  try { if (existsSync(parent)) rmdirSync(parent); } catch {}
}
