#!/usr/bin/env node
// Turn a video into footage a motion page can draw over: numbered JPEG frames, the audio
// track, and (with --words) a word-timed transcript, so callouts can land on the exact word.
//
//   node prepare-footage.mjs talk.mp4 [--fps 24] [--width 1280] [--words] [--model small] [--lang en]
//
// Writes, next to the video:
//   talk.footage/f00001.jpg ...   one frame per 1/fps second
//   talk.footage/audio.wav        the audio (if the video has any)
//   talk.footage/footage.js       window.FOOTAGE = { dir, fps, frames, width, height, duration, audio, words }
//   talk.footage/words.txt        with --words: one line per word, "12.34-12.80  Louis,"
// Load footage.js with a <script> tag from an HTML file in the same folder as the video.
// --words runs faster-whisper locally through uv (brew install uv); nothing leaves the machine.
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";
import { parseArgs } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: prepare-footage.mjs <video> [--fps 24] [--width 1280] [--words] [--model small] [--lang en]");
  process.exit(1);
}
const src = resolve(input);
const name = basename(src, extname(src)) + ".footage";
const dir = resolve(args.out || join(dirname(src), name));
const fps = +(args.fps || 24);

for (const bin of ["ffmpeg", "ffprobe"]) {
  try { execFileSync(bin, ["-version"], { stdio: "ignore" }); }
  catch { console.error(`${bin} is required (macOS: brew install ffmpeg)`); process.exit(1); }
}

const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", src]).toString());
const v = probe.streams.find((s) => s.codec_type === "video");
const hasAudio = probe.streams.some((s) => s.codec_type === "audio");
if (!v) { console.error("no video stream found"); process.exit(1); }
const duration = +probe.format.duration;
const width = +(args.width || v.width);
const height = Math.round((v.height * width) / v.width / 2) * 2;

rmSync(dir, { recursive: true, force: true });
mkdirSync(dir, { recursive: true });
console.error(`[footage] ${basename(src)}: ${duration.toFixed(2)}s, extracting ${fps}fps at ${width}x${height}`);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-vf", `fps=${fps},scale=${width}:${height}:flags=lanczos`, "-q:v", "3", join(dir, "f%05d.jpg")], { stdio: "inherit" });
const frames = readdirSync(dir).filter((f) => /^f\d{5}\.jpg$/.test(f)).length;
if (hasAudio) execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "2", "-ar", "48000", join(dir, "audio.wav")], { stdio: "inherit" });

let words = [];
if (args.words) {
  if (!hasAudio) { console.error("--words: the video has no audio"); process.exit(1); }
  try { execFileSync("uv", ["--version"], { stdio: "ignore" }); }
  catch { console.error("--words needs uv (macOS: brew install uv)"); process.exit(1); }
  // Raw 16 kHz mono float32, so whisper never has to decode media itself.
  const wav16 = join(dir, ".whisper.f32");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", wav16]);
  const py = `
import json, sys
import numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[2], compute_type="int8")
segs, _ = m.transcribe(np.fromfile(sys.argv[1], dtype=np.float32), word_timestamps=True, language=sys.argv[3] or None, vad_filter=True)
print(json.dumps([{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)} for s in segs for w in (s.words or [])]))
`;
  console.error(`[footage] transcribing with faster-whisper (${args.model || "small"}); the first run downloads the model`);
  const outp = execFileSync("uv", ["run", "--quiet", "--python", "3.12", "--with", "faster-whisper", "python", "-c", py, wav16, args.model || "small", args.lang || "en"], { stdio: ["ignore", "pipe", "inherit"], maxBuffer: 64 << 20 }).toString();
  words = JSON.parse(outp.trim().split("\n").pop());
  rmSync(wav16, { force: true });
  writeFileSync(join(dir, "words.txt"), words.map((w) => `${w.start.toFixed(2)}-${w.end.toFixed(2)}  ${w.w}`).join("\n") + "\n");
}

const footage = {
  dir: name, fps, frames, width, height, duration: +duration.toFixed(3),
  audio: hasAudio ? `${name}/audio.wav` : null, words,
};
writeFileSync(join(dir, "footage.js"), `window.FOOTAGE = ${JSON.stringify(footage)};\n`);
console.log(`footage: ${dir} (${frames} frames${hasAudio ? ", audio" : ""}${args.words ? `, ${words.length} words` : ""})`);
if (args.words && existsSync(join(dir, "words.txt"))) console.log(`words: ${join(dir, "words.txt")}`);
