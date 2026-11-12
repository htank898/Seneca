#!/usr/bin/env node
// Gemini as the art department: concept stills (Nano Banana) and reference video (Gemini Omni Flash).
// Outputs are REFERENCE ONLY. They are art targets for the Blender build, never frames of the final video.
//
//   node gemini.mjs image --prompt "..." [--ref frame.jpg --ref sheet.png ...] --out concept/restaged.png
//        [--model gemini-nano-banana-2.1] [--aspect 16:9] [--size 2K] [--n 1]
//   node gemini.mjs video --prompt "..." [--image concept/restaged.png] [--ref-video ref.mp4 --ref-start 2.0]
//        --out reference/omni.mp4 [--model gemini-omni-1.2-flash] [--duration 6s] [--aspect 16:9] [--resolution 720p]
//   add --dry-run to print the request (without base64 data) and exit.
//
// Key: $GEMINI_API_KEY (or $GOOGLE_API_KEY), else GEMINI_API_KEY= in the nearest .env up the tree.
// Every call appends { time, kind, model, prompt, refs, out, bytes } to log.json beside --out,
// so a look can be traced back to the exact prompt and references that produced it.
//
// API: POST https://generativelanguage.googleapis.com/v1beta/interactions (Interactions API,
// verified against Google's docs 2026-11). Veo 3.1 preview was shut down 2026-10-22; Omni Flash
// replaces it on this API. Reference video clips are capped at 3 s (this script trims them).
import { spawnSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, extname, join, resolve } from "node:path";

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions";
const API_REVISION = "2026-05-20";
const DEFAULTS = { image: "gemini-nano-banana-2.1", video: "gemini-omni-1.2-flash" };
const MIME = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".mp4": "video/mp4", ".mov": "video/quicktime" };

const [kind, ...rest] = process.argv.slice(2);
const flags = { ref: [] };
for (let i = 0; i < rest.length; i++) {
  const a = rest[i];
  if (!a.startsWith("--")) continue;
  const key = a.slice(2);
  const val = i + 1 < rest.length && !rest[i + 1].startsWith("--") ? rest[++i] : true;
  if (key === "ref") flags.ref.push(val);
  else flags[key] = val;
}
if (!["image", "video"].includes(kind) || !flags.prompt || !flags.out) {
  console.error(readFileSync(new URL(import.meta.url)).toString().split("\n").filter((l) => l.startsWith("//")).slice(0, 10)
    .map((l) => l.slice(3)).join("\n"));
  process.exit(1);
}

function apiKey() {
  const k = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (k) return k;
  // nearest .env walking up from the current folder (a project root .env covers every shot folder)
  for (let d = resolve("."); ; d = dirname(d)) {
    const f = join(d, ".env");
    if (existsSync(f)) {
      const m = readFileSync(f, "utf8").match(/^\s*(?:export\s+)?(?:GEMINI_API_KEY|GOOGLE_API_KEY)\s*=\s*["']?([^"'\n]+)["']?/m);
      if (m) return m[1].replace(/\s+#.*$/, "").trim();  // drop an inline "# comment"
    }
    if (dirname(d) === d) return null;
  }
}

function mediaItem(path, type) {
  const p = resolve(path);
  if (!existsSync(p)) { console.error(`not found: ${p}`); process.exit(1); }
  const mime = MIME[extname(p).toLowerCase()];
  if (!mime) { console.error(`unsupported file type: ${p}`); process.exit(1); }
  return { type, mime_type: mime, data: readFileSync(p).toString("base64"), _path: p };
}

function trimClip(path, start, tmp) {
  // Reference videos may be at most 3 s; cut 2.9 s from --ref-start, no audio.
  const out = join(tmp, `ref-${basename(path, extname(path))}.mp4`);
  const r = spawnSync("ffmpeg", ["-v", "error", "-y", "-ss", String(start || 0), "-i", resolve(path), "-t", "2.9",
    "-an", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", out]);
  if (r.status !== 0) { console.error(`ffmpeg failed trimming ${path}:\n${r.stderr}`); process.exit(1); }
  return out;
}

const tmp = mkdtempSync(join(tmpdir(), "seneca-gemini-"));
const model = flags.model || DEFAULTS[kind];
const input = [];
if (kind === "image") {
  for (const r of flags.ref) input.push(mediaItem(r, "image"));
} else {
  if (flags.image) input.push(mediaItem(flags.image, "image"));
  if (flags["ref-video"]) input.push(mediaItem(trimClip(flags["ref-video"], flags["ref-start"], tmp), "video"));
}
input.push({ type: "text", text: String(flags.prompt) });

const body = { model, input: input.map(({ _path, ...x }) => x) };
if (kind === "image") {
  body.response_format = { type: "image", mime_type: "image/png" };
  if (flags.aspect) body.response_format.aspect_ratio = String(flags.aspect);
  if (flags.size) body.response_format.image_size = String(flags.size).toUpperCase();
} else {
  body.response_format = { type: "video" };
  if (flags.duration) body.response_format.duration = /s$/.test(flags.duration) ? flags.duration : `${flags.duration}s`;
  if (flags.aspect) body.response_format.aspect_ratio = String(flags.aspect);
  if (flags.resolution) body.response_format.resolution = String(flags.resolution);
}
body.store = false;

if (flags["dry-run"]) {
  const shown = JSON.parse(JSON.stringify(body));
  for (const it of shown.input) if (it.data) it.data = `<${it.data.length} base64 chars>`;
  console.log(`POST ${ENDPOINT}\n${JSON.stringify(shown, null, 2)}`);
  rmSync(tmp, { recursive: true, force: true });
  process.exit(0);
}

const key = apiKey();
if (!key) {
  console.error("[gemini] no API key. Create one at https://aistudio.google.com/apikey, then\n" +
    "         export GEMINI_API_KEY=...   (or put GEMINI_API_KEY=... in ./.env)");
  process.exit(2);
}

function post(payload) {
  const bodyPath = join(tmp, "body.json");
  const respPath = join(tmp, "resp.json");
  writeFileSync(bodyPath, JSON.stringify(payload));
  // curl, not fetch: video generation can outlast fetch's 5-minute header timeout.
  const r = spawnSync("curl", ["-sS", "--max-time", "1200", "-X", "POST", ENDPOINT,
    "-H", `x-goog-api-key: ${key}`, "-H", "Content-Type: application/json", "-H", `Api-Revision: ${API_REVISION}`,
    "--data-binary", `@${bodyPath}`, "-o", respPath, "-w", "%{http_code}"], { encoding: "utf8" });
  if (r.status !== 0) { console.error(`[gemini] request failed: ${r.stderr}`); process.exit(1); }
  const code = Number(r.stdout.trim());
  const text = existsSync(respPath) ? readFileSync(respPath, "utf8") : "";
  if (code < 200 || code >= 300) {
    console.error(`[gemini] HTTP ${code}\n${text.slice(0, 3000)}`);
    process.exit(1);
  }
  return JSON.parse(text);
}

// The raw REST shape isn't fully documented, so collect every media block anywhere in the response:
// objects with {type: "image"|"video", data} (or a uri), e.g. under output_image or steps[].content[].
function collect(node, want, out = [], texts = []) {
  if (Array.isArray(node)) { node.forEach((n) => collect(n, want, out, texts)); return { out, texts }; }
  if (node && typeof node === "object") {
    const t = node.type || (node.mime_type || "").split("/")[0];
    if ((t === want || (node.mime_type || "").startsWith(want)) && (node.data || node.uri)) out.push(node);
    else if (typeof node.text === "string" && node.type !== undefined) texts.push(node.text);
    for (const [k, v] of Object.entries(node)) if (k !== "data") collect(v, want, out, texts);
  }
  return { out, texts };
}

function download(uri, dest) {
  const id = (uri.match(/files\/([^/:?]+)/) || [])[1];
  const url = id ? `https://generativelanguage.googleapis.com/v1beta/files/${id}:download?alt=media` : uri;
  const r = spawnSync("curl", ["-sSL", "--max-time", "600", "-H", `x-goog-api-key: ${key}`, url, "-o", dest]);
  if (r.status !== 0) { console.error(`[gemini] download failed: ${r.stderr}`); process.exit(1); }
}

const out = resolve(flags.out);
mkdirSync(dirname(out), { recursive: true });
const n = Math.max(1, Number(flags.n || 1));
const written = [];
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  const resp = post(body);
  const { out: media, texts } = collect(resp, kind);
  // de-duplicate (output_image repeats the last step's image)
  const seen = new Set();
  const uniq = media.filter((m) => { const k = (m.data || m.uri).slice(-64); if (seen.has(k)) return false; seen.add(k); return true; });
  if (!uniq.length) {
    console.error(`[gemini] no ${kind} in the response.${texts.length ? ` Model said: ${texts.join(" ").slice(0, 800)}` : ""}`);
    writeFileSync(join(tmp, "last-response.json"), JSON.stringify(resp, null, 2));
    console.error(`[gemini] raw response kept at ${join(tmp, "last-response.json")}`);
    process.exit(1);
  }
  const m = uniq[uniq.length - 1];
  const ext = extname(out) || (kind === "image" ? ".png" : ".mp4");
  const dest = n === 1 ? out : out.replace(new RegExp(`${ext.replace(".", "\\.")}$`), `-${i + 1}${ext}`);
  if (m.data) writeFileSync(dest, Buffer.from(m.data, "base64"));
  else download(m.uri, dest);
  written.push(dest);
  if (texts.length) console.log(`[gemini] note from model: ${texts.join(" ").slice(0, 400)}`);
}
rmSync(tmp, { recursive: true, force: true });

const logPath = join(dirname(out), "log.json");
let log = [];
if (existsSync(logPath)) { try { log = JSON.parse(readFileSync(logPath, "utf8")); } catch { log = []; } }
for (const w of written) {
  log.push({ time: new Date().toISOString(), kind, model, prompt: String(flags.prompt),
             refs: input.filter((x) => x._path).map((x) => x._path), out: w,
             options: body.response_format, bytes: readFileSync(w).length });
}
writeFileSync(logPath, JSON.stringify(log, null, 2));
for (const w of written) console.log(`[gemini] ${kind}: ${w}`);
console.log(`[gemini] ${model}, ${((Date.now() - t0) / 1000).toFixed(1)}s, logged to ${logPath}`);
