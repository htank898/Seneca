#!/usr/bin/env node
// Render an edit plan: animations laid over a talking-head video, keyed to what the speaker says.
//
//   node render-edit.mjs edit.json [--out final.mp4] [--preview 8.5,17] [--keep-frames]
//
// edit.json (paths relative to it):
//   {
//     "video": "pitch.mov",
//     "transcript": "pitch.transcript.json",          // from scripts/transcribe.py
//     "page": "overlays.html",                         // optional; default templates/overlay-shell.html
//     "brand": { "signal": "#f5c518", "ink": "#16191d", "paper": "#e6eae8" },   // optional palette
//     "output": { "height": 1440, "fps": 30, "crf": 20 },
//     "overlays": [
//       { "type": "lowerthird", "from": { "say": "I'm Jordan" }, "to": { "say": "I'm Jordan", "at": "end", "offset": 3 },
//         "props": { "name": "Jordan Lee", "title": "Account Executive, Acme" } },
//       { "type": "quote", "from": { "say": "here's your quote" }, "to": { "say": "any questions" }, "hold": 3,
//         "props": { "items": [{ "label": "Platform", "amount": 12000, "at": { "say": "platform" } }], "total": 12000 } }
//     ]
//   }
//
// Times: seconds, "start" / "end", or a phrase { "say": "...", "at": "start"|"end", "offset": s, "nth": n }.
// Phrases match whole words, ignoring case and punctuation; one that isn't in the transcript stops the
// render and prints what was said. Any object inside "props" with a "say" key is resolved the same way,
// so a template can cue its parts (bullets, line items) to the words that introduce them.
//
// "hold": N pauses the video for N seconds where that overlay starts (last frame frozen, audio silent),
// for an overlay that needs reading time the speaker didn't leave. Use sparingly. Everything after a
// hold, including later overlays and caption words, shifts by N automatically.
//
// The page defines window.renderFrame(t) on a transparent background (t = output seconds); the renderer
// injects window.EDIT = { width, height, fps, duration, overlays: [...], words: [...], holds: [...] }
// with every time already on the output timeline. Only frames with something on screen are rendered.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, rmdirSync, statSync, symlinkSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { launch, parseArgs, fileUrl, SKILL_DIR } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const planPath = args._[0] && resolve(args._[0]);
if (!planPath || !existsSync(planPath)) {
  console.error("usage: render-edit.mjs <edit.json> [--out final.mp4] [--preview t1,t2] [--keep-frames]");
  process.exit(1);
}
const base = dirname(planPath);
const plan = JSON.parse(readFileSync(planPath, "utf8"));
const video = resolve(base, plan.video);
const transcript = JSON.parse(readFileSync(resolve(base, plan.transcript || plan.video.replace(/\.[^.]+$/, ".transcript.json")), "utf8"));
const page = plan.page ? resolve(base, plan.page) : join(SKILL_DIR, "templates", "overlay-shell.html");
const out = resolve(args.out || resolve(base, plan.out || basename(video).replace(/\.[^.]+$/, "") + ".edited.mp4"));

try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); }
catch { console.error("ffmpeg is required (macOS: brew install ffmpeg)"); process.exit(1); }
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const probe = (a) => execFileSync("ffprobe", ["-v", "error", ...a]).toString().trim();

// ------------------------------------------------------------------ source video
const work = join(dirname(out), ".overlay-frames", basename(out, ".mp4"));
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });
ff(["-i", video, "-frames:v", "1", join(work, "probe.png")]);   // decoding applies phone rotation
const [srcW, srcH] = probe(["-show_entries", "stream=width,height", "-of", "csv=p=0", join(work, "probe.png")]).split(",").map(Number);
const srcDur = +probe(["-show_entries", "format=duration", "-of", "csv=p=0", video]);
const hasAudio = probe(["-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", video]).length > 0;
const height = Math.round((plan.output?.height || Math.max(srcH, 1080)) / 2) * 2;
const width = Math.round((height * srcW) / srcH / 2) * 2;
const fps = +(plan.output?.fps || 30);

// ------------------------------------------------------------------ phrases -> source seconds
const norm = (s) => s.toLowerCase().replace(/[’']/g, "'").replace(/[^a-z0-9'$% ]+/g, " ").trim();
const words = transcript.words.map((w) => ({ ...w, n: norm(w.word) })).filter((w) => w.n);
function findPhrase(say, nth = 1) {
  const want = norm(say).split(/\s+/);
  let seen = 0;
  for (let i = 0; i + want.length <= words.length; i++) {
    if (want.every((w, k) => words[i + k].n === w) && ++seen === nth) return { start: words[i].start, end: words[i + want.length - 1].end };
  }
  return null;
}
function srcTime(spec, label) {
  if (typeof spec === "number") return spec;
  if (spec === "start") return 0;
  if (spec === "end") return srcDur;
  const hit = findPhrase(spec.say, spec.nth || 1);
  if (!hit) {
    console.error(`[edit] ${label}: "${spec.say}" isn't in the transcript. What was said:\n` +
      transcript.segments.map((s) => `  ${s.start.toFixed(2)}–${s.end.toFixed(2)}  ${s.text}`).join("\n"));
    process.exit(1);
  }
  return Math.max(0, Math.min(srcDur, (spec.at === "end" ? hit.end : hit.start) + (spec.offset || 0)));
}

// ------------------------------------------------------------------ holds: source -> output timeline
const raw = plan.overlays.map((o, i) => ({ o, id: o.id || `${o.type}-${i + 1}`, from: srcTime(o.from, `${o.id || o.type}.from`) }));
const holds = raw.filter((r) => r.o.hold > 0).map((r) => ({ at: r.from, dur: +r.o.hold, id: r.id })).sort((a, b) => a.at - b.at);
const extra = holds.reduce((s, h) => s + h.dur, 0);
const duration = srcDur + extra;
// a time exactly at a hold maps to the start of the freeze; later times shift by every earlier hold
const toOut = (t) => t + holds.filter((h) => h.at < t).reduce((s, h) => s + h.dur, 0);
// spoken words are heard after the freeze, so a word starting exactly at a hold maps past it
const toOutSpoken = (t) => t + holds.filter((h) => h.at <= t).reduce((s, h) => s + h.dur, 0);
const outHold = holds.map((h) => ({ ...h, outAt: toOut(h.at) }));
const toSrc = (t) => {           // inverse, for previews: inside a freeze returns the frozen moment
  let shift = 0;
  for (const h of outHold) {
    if (t >= h.outAt && t < h.outAt + h.dur) return h.at;
    if (t >= h.outAt + h.dur) shift += h.dur;
  }
  return t - shift;
};

function resolveProps(v, label) {
  if (Array.isArray(v)) return v.map((x, i) => resolveProps(x, `${label}[${i}]`));
  if (v && typeof v === "object") {
    if (typeof v.say === "string") return +toOut(srcTime(v, label)).toFixed(3);
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolveProps(x, `${label}.${k}`)]));
  }
  return v;
}

const overlays = raw.map(({ o, id, from }) => {
  const to = srcTime(o.to ?? "end", `${id}.to`);
  if (!(to > from)) { console.error(`[edit] ${id}: ends (${to.toFixed(2)}s) before it starts (${from.toFixed(2)}s)`); process.exit(1); }
  const outFrom = toOut(from);
  // an overlay that holds stays up through its own freeze even if its "to" is earlier
  const outTo = Math.max(toOut(to), o.hold ? outFrom + o.hold + 0.5 : 0);
  const props = resolveProps(o.props || {}, `${id}.props`);
  // image props (a logo file) are paths relative to edit.json
  for (const k of ["image"]) {
    if (typeof props[k] !== "string" || /^(https?|data|file):/.test(props[k])) continue;
    const f = resolve(base, props[k]);
    if (!existsSync(f)) { console.error(`[edit] ${id}.props.${k}: no such file ${f}`); process.exit(1); }
    props[k] = fileUrl(f);
  }
  return { id, type: o.type, from: +outFrom.toFixed(3), to: +Math.min(duration, outTo).toFixed(3),
           hold: o.hold || 0, props };
});
const outWords = transcript.words.map((w) => ({ ...w, start: +toOutSpoken(w.start).toFixed(3), end: +toOutSpoken(w.end).toFixed(3) }));
for (const o of overlays) console.error(`[edit] ${o.id.padEnd(14)} ${o.from.toFixed(2)}s → ${o.to.toFixed(2)}s${o.hold ? `  (video paused ${o.hold}s)` : ""}`);
if (extra) console.error(`[edit] holds add ${extra.toFixed(2)}s: ${srcDur.toFixed(2)}s → ${duration.toFixed(2)}s`);

// ------------------------------------------------------------------ overlay page
const browser = await launch();
const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
const tab = await ctx.newPage();
const EDIT = { width, height, fps, duration, overlays, words: outWords, holds: outHold, brand: plan.brand || {} };
await tab.addInitScript((e) => { window.EDIT = e; window.__CAPTURE__ = true; }, EDIT);
await tab.goto(fileUrl(page), { waitUntil: "networkidle" });
await tab.evaluate(() => document.fonts.ready);
await tab.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => console.warn("image failed: " + i.src)))));
if (!(await tab.evaluate(() => typeof window.renderFrame === "function"))) {
  console.error("overlay page does not define window.renderFrame(t)");
  process.exit(1);
}
// Chromium saves a fully opaque screenshot (a full-screen logo/endcard/title frame) as an RGB PNG, and ffmpeg's
// image2 input stops at the first pixel-format change, silently truncating the video. Clipping a 1 px corner of
// the page keeps every frame RGBA, whatever the page draws; each frame is checked anyway.
await tab.addStyleTag({ content: "html { clip-path: polygon(1px 0, 100vw 0, 100vw 100vh, 0 100vh, 0 1px) !important; }" });
const shoot = async (t, path) => {
  await tab.evaluate((tt) => window.renderFrame(tt), t);
  const png = await tab.screenshot({ path, omitBackground: true });
  if (png[25] !== 6) { console.error(`\n[edit] frame at ${t.toFixed(2)}s is not RGBA (PNG color type ${png[25]})`); process.exit(1); }
};

if (args.preview) {
  for (const t of String(args.preview).split(",").map(Number)) {
    const p = `${out.replace(/\.mp4$/, "")}.preview-${t.toFixed(2)}s.png`;
    ff(["-ss", String(toSrc(t)), "-i", video, "-frames:v", "1", "-vf", `scale=${width}:${height}:flags=lanczos`, join(work, "bg.png")]);
    await shoot(t, join(work, "ov.png"));
    ff(["-i", join(work, "bg.png"), "-i", join(work, "ov.png"), "-filter_complex", "overlay", p]);
    console.log(`preview: ${p}`);
  }
  await browser.close();
  if (!args["keep-frames"]) rmSync(work, { recursive: true, force: true });
  process.exit(0);
}

const total = Math.round(duration * fps);
const blank = join(work, "blank.png");
await shoot(-1, blank);
const live = (t) => overlays.some((o) => t >= o.from - 0.05 && t < o.to + 0.6);   // +0.6 s for exit animations
let drawn = 0;
for (let i = 0; i < total; i++) {
  const t = i / fps;
  const f = join(work, `f${String(i).padStart(5, "0")}.png`);
  if (live(t)) { await shoot(t, f); drawn++; } else symlinkSync(blank, f);
  if (i % 30 === 0) process.stderr.write(`\r[edit] frame ${i + 1}/${total} (${drawn} drawn)`);
}
process.stderr.write(`\r[edit] ${total} frames, ${drawn} with overlays drawn          \n`);
await browser.close();

// ------------------------------------------------------------------ composite
// Pass 1 (only with holds): cut the source at each hold, freeze segment i on its last frame (tpad) with
// silence (apad), and join the segments into a near-lossless background. Each segment is its own seeked
// input, padded and then cut to an exact length, so video and audio stay the same duration.
// Pass 2: lay the overlay frames on the background. These are two ffmpeg runs on purpose: one graph that
// both concatenates hold segments and overlays an image sequence deadlocks ffmpeg 8.x (it stalls forever
// at 0% CPU), while each half on its own is reliable.
const crf = String(plan.output?.crf ?? 20);
const D = duration.toFixed(3);
let bg = video, bgScaled = false;
if (holds.length) {
  const bounds = [0, ...holds.map((h) => h.at), srcDur];
  const n = bounds.length - 1;
  const inputs = [], parts = [], labels = [];
  for (let i = 0; i < n; i++) {
    const [a, b] = [bounds[i], bounds[i + 1]];
    const d = i < holds.length ? holds[i].dur : 0;
    const len = (b - a).toFixed(3), whole = (b - a + d).toFixed(3);
    inputs.push("-ss", a.toFixed(3), "-t", len, "-i", video);
    parts.push(`[${i}:v]setpts=PTS-STARTPTS,fps=${fps},scale=${width}:${height}:flags=lanczos,setsar=1,trim=duration=${len}` +
               (d ? `,tpad=stop_mode=clone:stop_duration=${d}` : "") + `,trim=duration=${whole},setpts=PTS-STARTPTS[v${i}]`);
    if (hasAudio) parts.push(`[${i}:a]asetpts=PTS-STARTPTS,aresample=48000,atrim=duration=${len},apad=whole_dur=${whole},` +
                             `atrim=duration=${whole},asetpts=PTS-STARTPTS[a${i}]`);
    labels.push(`[v${i}]` + (hasAudio ? `[a${i}]` : ""));
  }
  parts.push(`${labels.join("")}concat=n=${n}:v=1:a=${hasAudio ? 1 : 0}[bg]${hasAudio ? "[aout]" : ""}`);
  bg = join(work, "background.mkv");
  bgScaled = true;
  process.stderr.write(`[edit] cutting holds into the footage\n`);
  ff([...inputs, "-filter_complex", parts.join(";"), "-map", "[bg]", ...(hasAudio ? ["-map", "[aout]", "-c:a", "pcm_s16le"] : []),
      "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", bg]);
}
const scale = bgScaled ? "" : `fps=${fps},scale=${width}:${height}:flags=lanczos,setsar=1,`;
// tpad + trim pins the video to exactly the planned duration (the last frame can otherwise go missing)
const graph = `[0:v]${scale}setpts=PTS-STARTPTS[bg];[1:v]format=rgba[ov];[bg][ov]overlay=format=auto:eof_action=pass,format=yuv420p,` +
              `tpad=stop_mode=clone:stop_duration=0.2,trim=duration=${D}[vout]` +
              (hasAudio ? `;[0:a]asetpts=PTS-STARTPTS,apad=whole_dur=${D},atrim=duration=${D}[aout]` : "");
process.stderr.write(`[edit] compositing\n`);
ff(["-i", bg, "-framerate", String(fps), "-i", join(work, "f%05d.png"), "-filter_complex", graph,
    "-map", "[vout]", ...(hasAudio ? ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"] : []),
    "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-movflags", "+faststart", out]);
const mb = (statSync(out).size / 1048576).toFixed(2);
const vdur = +probe(["-select_streams", "v", "-show_entries", "stream=duration", "-of", "csv=p=0", out]);
const adur = hasAudio ? +probe(["-select_streams", "a", "-show_entries", "stream=duration", "-of", "csv=p=0", out]) : vdur;
console.log(`video: ${out} (${width}x${height}, ${fps} fps, ${vdur.toFixed(2)}s, ${mb} MB)`);
if (Math.abs(vdur - adur) > 0.1 || Math.abs(vdur - duration) > 0.1) {
  console.error(`[edit] FAILED: video ${vdur.toFixed(2)}s, audio ${adur.toFixed(2)}s, expected ${duration.toFixed(2)}s. ` +
                `The output is truncated or out of sync; frames kept in ${work}`);
  process.exit(1);
}
if (!args["keep-frames"]) {
  rmSync(work, { recursive: true, force: true });
  try { rmdirSync(dirname(work)); } catch {}
}
