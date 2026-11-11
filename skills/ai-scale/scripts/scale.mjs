#!/usr/bin/env node
// Compute a scale scene (real math + auto comparison captions) and emit scene JSON.
//
//   node scale.mjs preset <money-tower|money-time|paper-moon> [--out scene.json]
//   node scale.mjs tower    --unit usd100 --amounts 1e5,1e6,1e9 [--title ..] [--prefix $]
//   node scale.mjs tower    --heights 2,450,8849 --labels "A,B,C"       (raw meters)
//   node scale.mjs timeline --amounts 1e6,1e9,1e12 [--per-second 1] [--rate "at $1 a second"] [--prefix $]
//   node scale.mjs timeline --seconds 86400,31557600
//   node scale.mjs doubling --start-m 0.0001 --target "The Moon" [--label "Fold"]
// Common: --size 1080x1350  --fps 30  --title "..."  --note "..."  --now 2026-10-23  --out file.json
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "./_browser.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const REF = JSON.parse(readFileSync(join(DIR, "..", "data", "references.json"), "utf8"));
const YEAR_S = 365.25 * 86400;

/* ---------- formatting ---------- */
const SCALES = [[1e15, "quadrillion"], [1e12, "trillion"], [1e9, "billion"], [1e6, "million"], [1e3, "thousand"]];
const sig = (x, n = 3) => Number(x.toPrecision(n));
const commas = (x) => Math.round(x).toLocaleString("en-US");
export function words(n) {
  for (const [v, w] of SCALES) if (n >= v) return `${sig(n / v)} ${w}`;
  return commas(n);
}
export function length(m) {
  if (m < 0.01) return `${sig(m * 1000, 2)} mm`;
  if (m < 1) return `${sig(m * 100, 2)} cm`;
  if (m < 1000) return `${sig(m, 3)} m`;
  const km = m / 1000;
  if (km >= 1e6) return `${sig(km / 1e6, 3)} million km`;
  return `${sig(km, 3).toLocaleString("en-US")} km`;
}
export function duration(s) {
  const y = s / YEAR_S;
  if (s < 3600) return `${sig(s / 60, 2)} minutes`;
  if (s < 86400 * 2) return `${sig(s / 3600, 2)} hours`;
  if (s < 86400 * 60) return `${sig(s / 86400, 3)} days`;
  if (y < 2) return `${sig(s / (YEAR_S / 12), 2)} months`;
  if (y < 1e6) return `${commas(sig(y, 3))} years`;
  if (y < 1e9) return `${sig(y / 1e6, 3)} million years`;
  return `${sig(y / 1e9, 3)} billion years`;
}
const lc = (s) => s.charAt(0).toLowerCase() + s.slice(1);

/* ---------- comparisons ---------- */
function towerCaption(h, landmarks, anchor) {
  if (h < anchor.h * 0.95) {
    const r = h / anchor.h;
    const part = r < 0.12 ? "Ankle" : r < 0.33 ? "Shin" : r < 0.55 ? "Knee" : r < 0.75 ? "Waist" : "Chest";
    return `${part}-high next to ${anchor.ref}.`;
  }
  const others = landmarks.filter((l) => l.kind !== "anchor").sort((a, b) => a.h - b.h);
  const near = others.find((l) => Math.abs(h / l.h - 1) < 0.12);
  if (near) return near.kind === "marker" ? `About as high as ${near.ref}.` : `About as tall as ${near.ref}.`;
  const below = [...others].reverse().find((l) => l.h < h) || anchor;
  const above = others.find((l) => l.h > h);
  const ratio = h / below.h;
  const lead = below.kind === "marker" ? `Past ${below.ref}` : ratio >= 3 ? `${sig(ratio, 2)}× the height of ${below.ref}` : `Taller than ${below.ref}`;
  return above ? `${lead}. Short of ${above.ref}.` : `${lead}.`;
}
function eventsResolved(now) {
  const nowY = now.getUTCFullYear() + (now - Date.UTC(now.getUTCFullYear(), 0, 1)) / (YEAR_S * 1000);
  return REF.events.map((e) => ({ ...e, ya: e.ya ?? nowY - e.year - (e.year < 0 ? 1 : 0) }));
}
function timelineCaption(years, events) {
  const younger = events.filter((e) => e.ya < years).sort((a, b) => b.ya - a.ya)[0];
  const older = events.filter((e) => e.ya > years).sort((a, b) => a.ya - b.ya)[0];
  if (younger && older) return `Before ${younger.ref}. After ${older.ref}.`;
  if (younger) return `Before ${younger.ref}.`;
  return "";
}
function dateLabel(seconds, now) {
  const years = seconds / YEAR_S;
  if (years < 2) return new Date(now - seconds * 1000).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  const y = now.getUTCFullYear() - years;
  if (years < 12000) return y >= 1 ? `around ${Math.round(y)}` : `around ${commas(1 - y)} BC`;
  return "";
}

/* ---------- scene builders ---------- */
function base(args, kind, defaults) {
  const [w, h] = String(args.size || "1080x1350").split("x").map(Number);
  return { kind, size: [w, h], fps: +(args.fps || 30), title: args.title || defaults.title, note: args.note || defaults.note || "", hud: defaults.hud, steps: [] };
}
function landmarksFor(maxH) {
  return REF.landmarks.filter((l) => l.kind === "anchor" || l.h <= maxH * 4);
}
const list = (s) => String(s).split(",").map((x) => Number(x.trim()));

function tower(args) {
  const unit = args.unit ? REF.units[args.unit] : null;
  if (args.unit && !unit) throw new Error(`unknown unit ${args.unit}; one of ${Object.keys(REF.units).join(", ")}`);
  const prefix = args.prefix ?? (unit && unit.name.startsWith("$") ? "$" : "");
  const scene = base(args, "tower", {
    title: unit ? `If it were a stack of ${unit.name}` : "How tall is it?",
    note: unit ? `${unit.note} Heights approximate.` : "Heights approximate.",
    hud: { prefix, suffix: args.suffix || "", interp: "geo" },
  });
  scene.unit = unit;
  const anchor = REF.landmarks.find((l) => l.kind === "anchor");
  let rows;
  if (args.heights) {
    const labels = args.labels ? String(args.labels).split(",") : [];
    rows = list(args.heights).map((h, i) => ({ h, value: h, headline: labels[i] || length(h) }));
  } else {
    rows = list(args.amounts).map((a) => ({ value: a, h: (a / unit.value) * unit.thickness_m }));
  }
  scene.anchor = anchor;
  scene.landmarks = landmarksFor(Math.max(...rows.map((r) => r.h)));
  scene.steps = rows.map((r) => ({
    value: r.value, h: r.h,
    headline: r.headline || `${prefix}${commas(r.value)}${scene.hud.suffix}`,
    sub: unit ? `${words(r.value)} ${unit.name.startsWith("$") ? "dollars" : unit.name}: a stack ${length(r.h)} tall` : length(r.h),
    caption: towerCaption(r.h, scene.landmarks, anchor),
  }));
  return scene;
}

function timeline(args) {
  const now = args.now ? new Date(args.now + "T12:00:00Z") : new Date();
  const perSecond = +(args["per-second"] || 1);
  const prefix = args.prefix ?? (args.amounts ? "$" : "");
  const scene = base(args, "timeline", {
    title: args.amounts ? `At ${prefix}${perSecond} a second, how far back would you start?` : "How long ago?",
    note: "1 year = 365.25 days. Dates approximate.",
    hud: { prefix, suffix: args.suffix || "", interp: "geo" },
  });
  scene.now = now.toISOString().slice(0, 10);
  const events = eventsResolved(now);
  const rows = args.amounts ? list(args.amounts).map((a) => ({ value: a, seconds: a / perSecond })) : list(args.seconds).map((s) => ({ value: s, seconds: s }));
  const maxY = Math.max(...rows.map((r) => r.seconds)) / YEAR_S;
  scene.events = events.filter((e) => e.ya <= maxY * 6).map((e) => ({ name: e.name, ya: e.ya, icon: e.icon }));
  scene.steps = rows.map((r) => {
    const years = r.seconds / YEAR_S;
    const date = dateLabel(r.seconds, now);
    return {
      value: r.value, seconds: r.seconds,
      headline: args.amounts ? `${prefix}${commas(r.value)}` : duration(r.seconds),
      sub: args.amounts ? `${words(r.value)} seconds ago: ${duration(r.seconds)}` : `${commas(r.seconds)} seconds`,
      caption: [date && date.charAt(0).toUpperCase() + date.slice(1) + ".", timelineCaption(years, events)].filter(Boolean).join(" "),
    };
  });
  return scene;
}

function doubling(args) {
  const start = +(args["start-m"] || 0.0001);
  const target = REF.landmarks.find((l) => l.name.toLowerCase() === String(args.target || "The Moon").toLowerCase());
  if (!target) throw new Error(`unknown target; one of ${REF.landmarks.map((l) => l.name).join(", ")}`);
  const label = args.label || "Fold";
  const scene = base(args, "tower", {
    title: `How many folds to reach ${lc(target.name)}?`,
    note: `Starts ${length(start)} thick and doubles each time. Real paper tears long before this; the math doesn't.`,
    hud: { prefix: `${label} `, suffix: "", interp: "linear" },
  });
  scene.unit = { name: "paper", width_m: 0.216, thickness_m: start, color: "#ffffff", band: 0 };
  scene.anchor = REF.landmarks.find((l) => l.kind === "anchor");
  const n = Math.ceil(Math.log2(target.h / start));
  scene.landmarks = landmarksFor(target.h);
  const crossed = new Set();
  for (let i = 0; i <= n; i++) {
    const h = start * 2 ** i;
    const newly = scene.landmarks.filter((l) => !crossed.has(l.name) && h >= l.h);
    newly.forEach((l) => crossed.add(l.name));
    const stop = i === 0 || i === n || newly.length > 0;
    scene.steps.push({
      value: i, h,
      headline: `${label} ${i}`,
      sub: `${length(h)} thick`,
      caption: i === 0 ? "One sheet." : towerCaption(h, scene.landmarks, scene.anchor),
      move: i === 0 ? undefined : stop ? 0.55 : 0.2,
      hold: stop ? 1.7 : 0,
    });
  }
  return scene;
}

const PRESETS = {
  "money-tower": () => tower({ unit: "usd100", amounts: "1e5,1e6,1e7,1e8,1e9,1e10,1e11,1e12", title: "Your net worth, stacked in $100 bills" }),
  "money-time": () => timeline({ amounts: "1e5,1e6,1e7,1e8,1e9,1e10,1e11,1e12,2.1e15", "per-second": 1, title: "Earn $1 every second. When did you start?" }),
  "paper-moon": () => doubling({ "start-m": 0.0001, target: "The Moon" }),
};

const args = parseArgs(process.argv.slice(2));
const [cmd, name] = args._;
let scene;
if (cmd === "preset") {
  if (!PRESETS[name]) { console.error(`presets: ${Object.keys(PRESETS).join(", ")}`); process.exit(1); }
  scene = PRESETS[name]();
  if (args.size) scene.size = String(args.size).split("x").map(Number);
  if (args.title) scene.title = args.title;
} else if (cmd === "tower") scene = tower(args);
else if (cmd === "timeline") scene = timeline(args);
else if (cmd === "doubling") scene = doubling(args);
else { console.error("usage: scale.mjs <preset|tower|timeline|doubling> ... (see header)"); process.exit(1); }

const json = JSON.stringify(scene, null, 2);
if (args.out) { writeFileSync(args.out, json + "\n"); console.error(`scene: ${args.out} (${scene.steps.length} steps)`); }
else console.log(json);
for (const s of scene.steps.filter((s) => s.hold !== 0)) console.error(`  ${s.headline.padEnd(22)} ${s.sub}  |  ${s.caption}`);
