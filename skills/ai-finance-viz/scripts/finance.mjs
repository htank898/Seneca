#!/usr/bin/env node
// Compute valuation metrics from the user's numbers, write a finance scene (JSON) and a self-contained HTML page.
//
//   node finance.mjs data.json|data.csv [--views payback,building,yields,margins,field,ev,card]
//       [--basis ttm|fwd] [--growth] [--size 1080x1350] [--fps 24] [--title ".."] [--out dir/name]
//   node finance.mjs build name.scene.json [--out name.html]   rebuild the HTML after hand-editing the scene JSON
//   node finance.mjs metrics data.json                         print the derived metrics, write nothing
//
// Writes <out>.scene.json and <out>.html. The HTML is the interactive explorer, and it also follows the ai-gif
// contract (window.MOTION + window.renderFrame(t)), so render-gif.mjs and render-stills.mjs can render it.
// Numbers come only from the input file. Nothing here fetches or remembers market data.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "./_browser.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = join(DIR, "..");
// Ticker colors. Brick red (#c4604b) is reserved for losses, so it never marks a ticker.
const PALETTE = ["#f5c518", "#4f86c6", "#6f9e6a", "#9a7fb8", "#e39a3b", "#7fb5a3"];
const ALL_VIEWS = ["payback", "building", "yields", "margins", "field", "ev", "card"];
const NUM_FIELDS = ["price", "shares", "market_cap", "eps_ttm", "eps_fwd", "revenue", "gross_profit", "operating_income",
  "net_income", "ebitda", "fcf", "debt", "cash", "book_value", "dividend", "growth"];

/* ---------- input ---------- */
// "3.4T", "15.2B", "820M", "$1,234", "9%" → numbers. Percent strings become fractions.
function num(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return v;
  const s = String(v).trim().replace(/[$,\s]/g, "").replace(/^−/, "-");
  const m = s.match(/^(-?[\d.]+(?:e-?\d+)?)([kmbt%])?$/i);
  if (!m) throw new Error(`can't read number "${v}"`);
  const k = { k: 1e3, m: 1e6, b: 1e9, t: 1e12, "%": 0.01 }[(m[2] || "").toLowerCase()] || 1;
  return Number(m[1]) * k;
}
function readCsv(text) {
  const cells = (l) => (l.match(/("([^"]|"")*"|[^,]*)(,|$)/g) || []).slice(0, -1).map((c) => c.replace(/,$/, "").replace(/^"|"$/g, "").replace(/""/g, '"').trim());
  const rows = text.trim().split(/\r?\n/).map(cells);
  const head = rows.shift();
  return { tickers: rows.filter((r) => r.some(Boolean)).map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""]))) };
}
function load(path) {
  const text = readFileSync(path, "utf8");
  const d = /\.csv$/i.test(path) ? readCsv(text) : JSON.parse(text);
  if (!Array.isArray(d.tickers) || !d.tickers.length) throw new Error("input needs a non-empty tickers array (or CSV rows)");
  return d;
}

/* ---------- metrics ---------- */
const div = (a, b) => (a == null || b == null || b === 0 ? null : a / b);
// Years until cumulative earnings repay the price, if earnings grow g a year (first year earns E·(1+g)).
function paybackYears(price, eps, g, cap = 200) {
  if (!(eps > 0) || g == null || price == null) return null;
  let cum = 0;
  for (let y = 1; y <= cap; y++) {
    const e = eps * Math.pow(1 + g, y);
    if (cum + e >= price) return y - 1 + (price - cum) / e;
    cum += e;
  }
  return Infinity;
}
export function metrics(raw) {
  const i = Object.fromEntries(NUM_FIELDS.map((f) => [f, num(raw[f])]));
  const why = {}, derived = [];
  if (i.shares == null && i.market_cap != null && i.price) { i.shares = i.market_cap / i.price; derived.push("shares = market_cap ÷ price"); }
  const mcap = i.market_cap ?? (i.price != null && i.shares != null ? i.price * i.shares : null);
  if (i.net_income == null && i.eps_ttm != null && i.shares != null) { i.net_income = i.eps_ttm * i.shares; derived.push("net_income ≈ eps_ttm × shares"); }
  const pos = (v, key, reason) => { if (v == null) return null; if (v <= 0) { why[key] = reason; return null; } return v; };
  const m = { mcap };
  m.pe_ttm = div(i.price, pos(i.eps_ttm, "pe_ttm", "trailing earnings are negative"));
  m.pe_fwd = div(i.price, pos(i.eps_fwd, "pe_fwd", "the forward earnings estimate is negative"));
  m.ey_ttm = div(i.eps_ttm, i.price);
  m.ey_fwd = div(i.eps_fwd, i.price);
  m.peg = i.growth > 0 && m.pe_fwd != null ? m.pe_fwd / (i.growth * 100) : null;
  if (m.peg == null && i.growth == null) why.peg = "no growth estimate";
  if (m.peg == null && i.growth != null && i.growth <= 0) why.peg = "growth is zero or negative";
  if (m.peg == null && why.pe_fwd) why.peg = why.pe_fwd;
  m.ps = div(mcap, pos(i.revenue, "ps", "no revenue"));
  m.pb = div(mcap, pos(i.book_value, "pb", "book value is negative"));
  m.ev = mcap != null && i.debt != null && i.cash != null ? mcap + i.debt - i.cash : null;
  m.ev_ebitda = div(m.ev, pos(i.ebitda, "ev_ebitda", "EBITDA is negative"));
  m.fcf_yield = div(i.fcf, mcap);
  m.div_yield = i.dividend != null ? div(i.dividend, i.price) : null;
  m.gross_margin = div(i.gross_profit, i.revenue);
  m.op_margin = div(i.operating_income, i.revenue);
  m.net_margin = div(i.net_income, i.revenue);
  m.fcf_margin = div(i.fcf, i.revenue);
  m.floors = div(mcap, pos(i.net_income, "floors", "net income is negative"));
  m.payback_growth = paybackYears(i.price, i.eps_ttm, i.growth);
  if (m.payback_growth == null && why.pe_ttm) why.payback_growth = why.pe_ttm;
  for (const [k, v] of Object.entries(m)) if (v != null && Number.isNaN(v)) m[k] = null;
  return { inputs: i, m, why, derived };
}

/* ---------- formatting (mirrors lib/finance-engine.js) ---------- */
const sig = (x, n = 3) => Number(x.toPrecision(n));
function money(x, cur = "$") {
  if (x == null) return "n/a";
  const a = Math.abs(x), s = x < 0 ? "−" : "";
  for (const [v, w] of [[1e12, "T"], [1e9, "B"], [1e6, "M"]]) if (a >= v) return `${s}${cur}${sig(a / v)}${w}`;
  return `${s}${cur}${a >= 100 ? Math.round(a) : a.toFixed(2)}`;
}
const pct = (x) => (x == null ? "n/a" : `${(x * 100).toFixed(Math.abs(x) < 0.1 ? 1 : 0)}%`);
const mult = (x) => (x == null ? "n/m" : `${x >= 100 ? Math.round(x) : x.toFixed(1)}×`);
const yrs = (x) => (x === Infinity ? "200+" : String(Math.round(x)));
const and = (a) => (a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`);

/* ---------- beats ---------- */
const VIEWS = {
  payback: { label: "PRICE ÷ EARNINGS  ·  P/E", title: "How many years until $100 pays you back?" },
  building: { label: "MARKET VALUE vs. PROFIT", title: "The building and its rent" },
  yields: { label: "EARNINGS, FREE CASH FLOW AND DIVIDEND YIELD", title: "What $100 of stock earns in a year" },
  margins: { label: "GROSS → OPERATING → NET MARGIN", title: "What's left of every $100 of sales" },
  field: { label: "FORWARD P/E vs. EXPECTED GROWTH  ·  PEG", title: "The price of growth" },
  ev: { label: "ENTERPRISE VALUE ÷ EBITDA", title: "Buying the whole company" },
  card: { label: "ALL METRICS", title: "The spec sheet" },
};
function caption(view, T, d, opt) {
  const cur = d.currency || "$";
  const has = (k) => T.filter((t) => t.m[k] != null);
  const neg = (k) => T.filter((t) => t.m[k] == null && t.why[k]).map((t) => t.symbol);
  const verb = (a, one, many) => (a.length > 1 ? many : one);
  if (view === "payback") {
    const k = opt.basis === "fwd" ? "pe_fwd" : "pe_ttm";
    const ok = has(k).sort((a, b) => a.m[k] - b.m[k]);
    const parts = ok.map((t, j) => (j === 0 ? `${t.symbol} pays it back in ${yrs(t.m[k])} years` : `${t.symbol} in ${yrs(t.m[k])}`));
    const lost = neg(k);
    let s = `Each coin is one year of earnings on $100 of stock (${opt.basis === "fwd" ? "next 12 months, estimated" : "last 12 months"}). ${and(parts)}.`;
    if (lost.length) s += ` ${and(lost)} ${verb(lost, "is", "are")} losing money, so at these earnings ${verb(lost, "it", "they")} never ${verb(lost, "does", "do")}.`;
    return s;
  }
  if (view === "building") {
    const ok = T.filter((t) => t.m.mcap != null).sort((a, b) => b.m.mcap - a.m.mcap);
    const top = ok[0];
    let s = "Height is market value, all on one scale. Each floor is one year of profit: the rent the building collects.";
    if (top) s += ` ${top.symbol} is tallest at ${money(top.m.mcap, cur)}${top.m.floors ? `, ${Math.round(top.m.floors)} floors high` : ""}.`;
    const lost = neg("floors");
    if (lost.length) s += ` ${and(lost)} collect${verb(lost, "s", "")} no rent right now.`;
    return s;
  }
  if (view === "yields") {
    const k = opt.basis === "fwd" ? "ey_fwd" : "ey_ttm";
    const best = has(k).sort((a, b) => b.m[k] - a.m[k])[0];
    const divs = has("div_yield").filter((t) => t.m.div_yield > 0).sort((a, b) => b.m.div_yield - a.m.div_yield)[0];
    let s = "Per $100 of stock, per year.";
    if (best && divs && best === divs) s = `${best.symbol} earns the most per $100 (${money(best.m[k] * 100, cur)} a year) and pays the most out in cash (${money(divs.m.div_yield * 100, cur)}).`;
    else if (best) s = `${best.symbol} earns the most per $100: ${money(best.m[k] * 100, cur)} a year.${divs ? ` ${divs.symbol} pays the most out in cash: ${money(divs.m.div_yield * 100, cur)}.` : ""}`;
    if (d.benchmark?.rate != null) s += ` For scale: ${d.benchmark.label || "the benchmark"}, ${money(num(d.benchmark.rate) * 100, cur)}.`;
    return s;
  }
  if (view === "margins") {
    const ok = has("net_margin").sort((a, b) => b.m.net_margin - a.m.net_margin);
    const kept = ok.filter((t) => t.m.net_margin >= 0).map((t) => `${t.symbol} keeps ${cur}${Math.round(t.m.net_margin * 100)}`);
    const lost = ok.filter((t) => t.m.net_margin < 0).map((t) => `${t.symbol} loses ${cur}${Math.round(-t.m.net_margin * 100)}`);
    return `After the cost of the product, running the business, interest and tax: ${and([...kept, ...lost])}.`;
  }
  if (view === "field") {
    const off = T.filter((t) => t.m.peg == null).map((t) => t.symbol);
    let s = "Higher means paying more for each dollar of next year's earnings. Further right means faster expected growth. Each dashed line is one PEG (P/E ÷ growth). Bubble area is market value.";
    if (off.length) s += ` ${and(off)} can't be placed.`;
    return s;
  }
  if (view === "ev") return "Shares, plus the debt you'd take on, minus the cash in the till. Then: how many years of operating cash profit (EBITDA) that price equals.";
  if (view === "card") return "Every number on one sheet. n/m means not meaningful, usually because earnings are negative.";
  return "";
}
// Drop views the data can't support, and say why.
function usable(view, T) {
  const any = (k) => T.some((t) => t.m[k] != null || t.why[k]);
  const need = { payback: ["pe_ttm"], building: ["mcap"], yields: ["ey_ttm"], margins: ["net_margin"], field: ["pe_fwd"], ev: ["ev"], card: ["mcap"] }[view];
  const missing = need.filter((k) => !any(k));
  return missing.length ? `skipped "${view}": no ticker has the inputs for ${missing.join(", ")}` : null;
}

/* ---------- scene + html ---------- */
function makeScene(d, args) {
  const opt = { basis: args.basis || d.basis || "ttm", growth: !!(args.growth || d.growth) };
  const T = d.tickers.slice(0, 6).map((raw, j) => {
    const { inputs, m, why, derived } = metrics(raw);
    return { symbol: String(raw.symbol || raw.ticker || `T${j + 1}`).toUpperCase(), name: raw.name || "", color: raw.color || PALETTE[j % PALETTE.length],
      asOf: raw.asOf || raw.as_of || d.asOf || "", source: raw.source || d.source || "", inputs, m, why, derived };
  });
  if (d.tickers.length > 6) console.warn(`warning: only the first 6 of ${d.tickers.length} tickers are used`);
  const req = String(args.views || d.views || ALL_VIEWS.join(",")).split(",").map((s) => s.trim()).filter(Boolean);
  for (const v of req) if (!VIEWS[v]) throw new Error(`unknown view "${v}"; one of ${ALL_VIEWS.join(", ")}`);
  const views = req.filter((v) => { const r = usable(v, T); if (r) console.warn(r); return !r; });
  const [w, h] = String(args.size || d.size || "1080x1350").split("x").map(Number);
  const benchmark = d.benchmark ? { label: d.benchmark.label || "benchmark", rate: num(d.benchmark.rate), source: d.benchmark.source || "", asOf: d.benchmark.asOf || d.asOf || "" } : null;
  if (!d.asOf && T.some((t) => !t.asOf) && !d.sample) console.warn('warning: no asOf date. Every number needs one; add "asOf" to the input.');
  if (!d.source && T.some((t) => !t.source) && !d.sample) console.warn('warning: no source. Add "source", or set "sample": true for illustrative numbers.');
  const beats = views.map((v, j) => {
    const b = { view: v, fig: j + 1, label: VIEWS[v].label, title: VIEWS[v].title, caption: caption(v, T, d, opt) };
    if (v === "payback" || v === "yields") b.basis = opt.basis;
    if (v === "payback" && opt.growth) b.growth = true;
    return b;
  });
  return {
    kind: "finance", version: 1, size: [w, h], fps: +(args.fps || d.fps || 24),
    title: args.title || d.title || `${and(T.map((t) => t.symbol))}, side by side`,
    asOf: d.asOf || "", source: d.source || "", sample: !!d.sample, currency: d.currency || "$", basis: opt.basis,
    benchmark, notes: d.notes || [], theme: d.theme || undefined, tickers: T, beats,
  };
}
const toJson = (scene, space) => JSON.stringify(scene, (k, v) => (v === Infinity ? "Infinity" : v), space);
function html(scene) {
  const shell = readFileSync(join(ROOT, "templates", "finance-shell.html"), "utf8");
  const engine = readFileSync(join(ROOT, "lib", "finance-engine.js"), "utf8");
  return shell
    .replace("<!--TITLE-->", () => scene.title.replace(/&/g, "&amp;").replace(/</g, "&lt;"))
    .replace("/*SCENE*/", () => `window.SCENE = ${toJson(scene).replace(/</g, "\\u003c")};`)
    .replace("/*ENGINE*/", () => engine);
}
function table(scene) {
  const rows = [["", ...scene.tickers.map((t) => t.symbol)]];
  const add = (label, f) => rows.push([label, ...scene.tickers.map((t) => f(t.m, t))]);
  add("Market cap", (m) => money(m.mcap)); add("P/E trailing", (m) => mult(m.pe_ttm)); add("P/E forward", (m) => mult(m.pe_fwd));
  add("Earnings yield", (m) => pct(m.ey_ttm)); add("PEG", (m) => mult(m.peg)); add("P/S", (m) => mult(m.ps)); add("P/B", (m) => mult(m.pb));
  add("EV/EBITDA", (m) => mult(m.ev_ebitda)); add("FCF yield", (m) => pct(m.fcf_yield)); add("Dividend yield", (m) => pct(m.div_yield));
  add("Net margin", (m) => pct(m.net_margin)); add("Payback w/ growth", (m) => (m.payback_growth == null ? "n/a" : `${yrs(m.payback_growth)} yrs`));
  const wd = rows[0].map((_, c) => Math.max(...rows.map((r) => r[c].length)));
  return rows.map((r) => r.map((c, i) => c.padEnd(wd[i])).join("  ")).join("\n");
}

/* ---------- main ---------- */
const args = parseArgs(process.argv.slice(2));
const [cmd, file] = args._;
if (!cmd) { console.error("usage: finance.mjs <data.json|data.csv> [--views ..] [--out dir/name]  |  finance.mjs build scene.json  |  finance.mjs metrics data.json"); process.exit(1); }
if (cmd === "build") {
  const scene = JSON.parse(readFileSync(file, "utf8"), (k, v) => (v === "Infinity" ? Infinity : v));
  const out = resolve(args.out || file.replace(/\.scene\.json$|\.json$/i, "") + ".html");
  writeFileSync(out, html(scene));
  console.log(`html: ${out}`);
} else if (cmd === "metrics") {
  console.log(table(makeScene(load(file), args)));
} else {
  const scene = makeScene(load(cmd), args);
  const out = resolve(args.out || cmd.replace(/\.(json|csv)$/i, ""));
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out + ".scene.json", toJson(scene, 1));
  writeFileSync(out + ".html", html(scene));
  console.log(table(scene));
  console.log(`\nscene: ${out}.scene.json\nhtml:  ${out}.html  (${scene.beats.map((b) => b.view).join(" → ")})`);
}
