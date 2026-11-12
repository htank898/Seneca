#!/usr/bin/env node
// Render a Manim scene to MP4, GIF, and/or a transparent clip other Seneca pages can composite.
//
//   node render-math.mjs scene.py SceneName [--out dir/name.mp4]
//     [--quality l|m|h|k] [--fps 30] [--size 1080x1080]
//     [--gif] [--gif-fps 24] [--scale 1] [--colors 256] [--dither sierra2_4a] [--budget-mb 5]
//     [--clip] [--no-mp4] [--timings voice/timings.json] [--keep-media]
//
// --clip writes a transparent PNG sequence to <name>.clip/ with clip.json + clip.js,
// for templates/clip-player.js inside any renderFrame(t) page (gif-create, video-create, guides).
// --timings exposes a video-create timings.json to the scene, so SenecaScene.beat("id")
// holds each beat until that narration scene leaves the screen.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync, copyFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { parseArgs, SKILL_DIR } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const [sceneFile, sceneName] = args._;
if (!sceneFile || !sceneName) {
  console.error("usage: render-math.mjs <scene.py> <SceneName> [--out name.mp4] [--size 1080x1080] [--gif] [--clip]");
  process.exit(1);
}
const scenePath = resolve(sceneFile);
if (!existsSync(scenePath)) { console.error(`no such file: ${scenePath}`); process.exit(1); }

try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); }
catch { console.error("ffmpeg is required (macOS: brew install ffmpeg)"); process.exit(1); }

const out = resolve(args.out || join(dirname(scenePath), `${sceneName}.mp4`));
const stem = out.replace(/\.(mp4|gif|mov)$/i, "");
const name = basename(stem);
const mediaDir = join(dirname(out), ".manim-media", name);
const quality = String(args.quality || "h");
const wantMp4 = !args["no-mp4"];
const wantGif = !!args.gif;
const wantClip = !!args.clip;
if (!wantMp4 && !wantGif && !wantClip) { console.error("nothing to render: --no-mp4 without --gif or --clip"); process.exit(1); }

const env = { ...process.env };
if (args.timings) {
  const t = resolve(args.timings);
  if (!existsSync(t)) { console.error(`no such timings file: ${t}`); process.exit(1); }
  env.AI_MATH_TIMINGS = t;
}

function manim(extra) {
  const cli = ["render", scenePath, sceneName, `-q${quality}`, "--media_dir", mediaDir, "-o", name, "--disable_caching"];
  if (args.fps) cli.push("--fps", String(args.fps));
  if (args.size) cli.push("-r", String(args.size).replace(/x/i, ","));
  const r = spawnSync("python3", [join(SKILL_DIR, "scripts", "manim.py"), ...cli, ...extra],
    { stdio: ["ignore", "inherit", "inherit"], env });
  if (r.status !== 0) { console.error(`[math] manim failed (exit ${r.status})`); process.exit(r.status || 1); }
}

function find(dir, test) {
  const hits = [];
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) { if (e.name !== "partial_movie_files") walk(p); }
      else if (test(p)) hits.push(p);
    }
  };
  if (existsSync(dir)) walk(dir);
  return hits.sort();
}

const probe = (file, entries) => execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
  "-show_entries", entries, "-of", "csv=p=0", file]).toString().trim();
const mb = (p) => (statSync(p).size / 1048576).toFixed(2);
mkdirSync(dirname(out), { recursive: true });
rmSync(mediaDir, { recursive: true, force: true });

// ---- MP4 (also the source for the GIF)
let mp4 = null;
if (wantMp4 || wantGif) {
  console.error(`[math] rendering ${sceneName} (quality ${quality})`);
  manim(["--format", "mp4"]);
  const src = find(join(mediaDir, "videos"), (p) => p.endsWith(`${name}.mp4`))[0];
  if (!src) { console.error("[math] manim finished but no MP4 was found"); process.exit(1); }
  mp4 = `${stem}.mp4`;
  // Re-mux with faststart so it streams and embeds cleanly; manim already encodes H.264 yuv420p.
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-c", "copy", "-movflags", "+faststart", mp4]);
  const [w, h, rate] = probe(mp4, "stream=width,height,r_frame_rate").split(",");
  const dur = (+execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4])).toFixed(2);
  const [rn, rd = 1] = rate.split("/").map(Number);
  console.log(`mp4: ${mp4} (${w}x${h}, ${+(rn / rd).toFixed(2)} fps, ${dur}s, ${mb(mp4)} MB)`);
}

// ---- GIF (same palette pipeline as gif-create)
if (wantGif) {
  const gif = `${stem}.gif`;
  const [w] = probe(mp4, "stream=width").split(",");
  const outW = Math.round(+w * +(args.scale || 1));
  const gfps = +(args["gif-fps"] || 24);
  const colors = +(args.colors || 256);
  const dither = args.dither || "sierra2_4a";
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", mp4,
    "-vf", `fps=${gfps},scale=${outW}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=${colors}:stats_mode=diff[p];[b][p]paletteuse=dither=${dither}:diff_mode=rectangle`,
    "-loop", "0", gif], { stdio: "inherit" });
  console.log(`gif: ${gif} (${mb(gif)} MB, ${gfps} fps)`);
  const budget = +(args["budget-mb"] || 5);
  if (statSync(gif).size > budget * 1048576) {
    console.warn(`warning: over ${budget} MB. Try --scale 0.75, --gif-fps 20, --colors 128, or a shorter scene.`);
  }
  if (!wantMp4) rmSync(mp4);
}

// ---- Transparent clip: PNG sequence + manifest
if (wantClip) {
  console.error(`[math] rendering ${sceneName} as a transparent clip`);
  // A transparent MOV, not --format png-sequence: the PNG sequence drops the frames of
  // wait()/beat() holds, which would throw the clip out of sync with its timeline.
  manim(["--format", "mov", "-t"]);
  const mov = find(join(mediaDir, "videos"), (p) => p.endsWith(`${name}.mov`))[0];
  if (!mov) { console.error("[math] manim finished but no transparent MOV was found"); process.exit(1); }
  const clipDir = `${stem}.clip`;
  rmSync(clipDir, { recursive: true, force: true });
  mkdirSync(clipDir, { recursive: true });
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", mov, "-start_number", "0",
    "-pix_fmt", "rgba", join(clipDir, "f%05d.png")]);
  const frames = readdirSync(clipDir).filter((f) => /^f\d{5}\.png$/.test(f));
  const [w, h, rate] = probe(mov, "stream=width,height,r_frame_rate").split(",");
  const [rn, rd = 1] = rate.split("/").map(Number);
  const fps = +(rn / rd).toFixed(3);
  const clip = { name, fps, frames: frames.length, width: +w, height: +h,
    duration: +(frames.length / fps).toFixed(3), pattern: "f%05d.png" };
  writeFileSync(join(clipDir, "clip.json"), JSON.stringify(clip, null, 2) + "\n");
  // Same data as a script, so a page opened from file:// can load it without fetch().
  writeFileSync(join(clipDir, "clip.js"),
    `(window.CLIPS = window.CLIPS || {})[${JSON.stringify(name)}] = ${JSON.stringify(clip)};\n`);
  copyFileSync(join(SKILL_DIR, "templates", "clip-player.js"), join(clipDir, "clip-player.js"));
  const size = readdirSync(clipDir).reduce((s, f) => s + statSync(join(clipDir, f)).size, 0);
  console.log(`clip: ${clipDir}/ (${clip.frames} frames, ${w}x${h}, ${fps} fps, ${clip.duration}s, ${(size / 1048576).toFixed(1)} MB)`);
}

if (!args["keep-media"]) {
  rmSync(mediaDir, { recursive: true, force: true });
  try { if (!readdirSync(dirname(mediaDir)).length) rmSync(dirname(mediaDir), { recursive: true }); } catch {}
}
