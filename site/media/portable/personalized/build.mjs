#!/usr/bin/env node
// Personalized at scale: one template + one data file -> one page per recipient.
//
//   node personalized/build.mjs
//
// Reads customers.json and template.html (next to this script), computes every
// number for each customer itself, checks those numbers against the figures the
// scenario publishes, and writes out/<slug>.html plus out/index.html.
// No dependencies: Node's standard library only.
//
// Sample scenario: Lumen Desk and its customers are fictional.

import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "out");

// Pricing, in integer cents so nothing drifts through floating point.
const CURRENT_SEAT_CENTS = 4900;  // $49 per seat per month today
const NEW_SEAT_CENTS = 5900;      // $59 per seat per month from renewal
const LOYALTY_PERCENT_OFF = 10;   // one-time, first year at the new price

// The figures published in SCENARIO.md. The build fails if its own math disagrees.
const EXPECTED = {
  "Harbor & Pine Dental Group": { current: "$588.00", firstYear: "$637.20", after: "$708.00" },
  "Corvid Logistics": { current: "$2,352.00", firstYear: "$2,548.80", after: "$2,832.00" },
  "Fernhill Public Library": { current: "$294.00", firstYear: "$318.60", after: "$354.00" },
};

// ---------- helpers ----------

const usd = (cents) =>
  "$" + (cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const slugify = (s) =>
  s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

const escapeHtml = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Dates are calendar dates, handled in UTC so the build machine's timezone never shifts them.
function parseDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) throw new Error(`renewal_date must be YYYY-MM-DD, got "${iso}"`);
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  if (d.toISOString().slice(0, 10) !== iso) throw new Error(`Not a real date: ${iso}`);
  return d;
}
const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
const addYears = (d, n) => {
  const r = new Date(d);
  r.setUTCFullYear(r.getUTCFullYear() + n);
  return r;
};
const iso = (d) => d.toISOString().slice(0, 10);
const longDate = (d) =>
  d.toLocaleDateString("en-US", { timeZone: "UTC", month: "long", day: "numeric", year: "numeric" });
const shortDate = (d) =>
  d.toLocaleDateString("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" });

// ---------- compute ----------

function compute(c) {
  if (!Number.isInteger(c.seats) || c.seats <= 0) throw new Error(`${c.account}: seats must be a positive integer`);
  const currentCents = c.seats * CURRENT_SEAT_CENTS;
  const afterCents = c.seats * NEW_SEAT_CENTS;
  const firstYearCents = (afterCents * (100 - LOYALTY_PERCENT_OFF)) / 100;
  if (!Number.isInteger(firstYearCents)) throw new Error(`${c.account}: first-year price is not a whole number of cents`);
  const loyaltyCents = afterCents - firstYearCents;

  const renewal = parseDate(c.renewal_date);
  const after = addYears(renewal, 1);

  return {
    account: c.account,
    first_name: c.contact_first_name,
    seats: String(c.seats),
    current_monthly: usd(currentCents),
    first_year_monthly: usd(firstYearCents),
    after_monthly: usd(afterCents),
    loyalty_monthly: usd(loyaltyCents),
    loyalty_yearly: usd(loyaltyCents * 12),
    renewal_iso: iso(renewal),
    renewal_long: longDate(renewal),
    renewal_short: shortDate(renewal),
    renewal_eve_long: longDate(addDays(renewal, -1)),
    first_year_end_long: longDate(addDays(after, -1)),
    after_iso: iso(after),
    after_long: longDate(after),
  };
}

function assertMatchesScenario(v) {
  const want = EXPECTED[v.account];
  if (!want) throw new Error(`No published figures for "${v.account}" to check against`);
  const got = { current: v.current_monthly, firstYear: v.first_year_monthly, after: v.after_monthly };
  for (const k of Object.keys(want)) {
    if (got[k] !== want[k]) {
      throw new Error(`${v.account}: computed ${k} = ${got[k]}, scenario says ${want[k]}`);
    }
  }
}

function render(template, values) {
  const html = template.replace(/\{\{\s*([a-z_]+)\s*\}\}/g, (_, key) => {
    if (!(key in values)) throw new Error(`Template uses {{${key}}} but no value was computed for it`);
    return escapeHtml(values[key]);
  });
  if (/\{\{|\}\}/.test(html)) throw new Error("Unfilled placeholder left in output");
  return html;
}

// ---------- build ----------

try {
  const { customers } = JSON.parse(readFileSync(join(here, "customers.json"), "utf8"));
  const template = readFileSync(join(here, "template.html"), "utf8");

  const pages = customers.map((c) => {
    const values = compute(c);
    assertMatchesScenario(values);
    return { slug: slugify(c.account), values, html: render(template, values) };
  });

  // Isolation check: no page may mention another customer's account or contact.
  for (const p of pages) {
    for (const other of pages) {
      if (other === p) continue;
      for (const needle of [other.values.account, escapeHtml(other.values.account), other.values.first_name]) {
        if (p.html.includes(needle)) throw new Error(`${p.slug}.html contains data for ${other.values.account}`);
      }
    }
  }

  rmSync(outDir, { recursive: true, force: true });
  mkdirSync(outDir, { recursive: true });
  for (const p of pages) writeFileSync(join(outDir, `${p.slug}.html`), p.html);
  writeFileSync(join(outDir, "index.html"), renderIndex(pages));

  console.log(`Built ${pages.length} notices into ${outDir}`);
  console.table(
    pages.map(({ slug, values: v }) => ({
      file: `${slug}.html`,
      seats: +v.seats,
      renewal: v.renewal_iso,
      today: v.current_monthly,
      "first year": v.first_year_monthly,
      after: v.after_monthly,
    })),
  );
  console.log("All computed figures match SCENARIO.md.");
} catch (err) {
  console.error(`\nBUILD FAILED: ${err.message}\n`);
  process.exit(1);
}

function renderIndex(pages) {
  const rows = pages
    .map(
      ({ slug, values: v }) => `
      <tr>
        <th scope="row"><a href="${slug}.html">${escapeHtml(v.account)}</a><small>Contact: ${escapeHtml(v.first_name)}</small></th>
        <td class="num">${v.seats}</td>
        <td><time datetime="${v.renewal_iso}">${v.renewal_short}</time></td>
        <td class="num">${v.current_monthly}</td>
        <td class="num">${v.first_year_monthly}</td>
        <td class="num">${v.after_monthly}</td>
      </tr>`,
    )
    .join("");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Pro renewal notices · Lumen Desk</title>
<style>
  :root {
    --ink: #1b2a33; --ink-soft: #4a5a63; --paper: #f6f7f5; --card: #ffffff; --rule: #dfe3df;
    --accent: #2f7d6d; --warm: #d9a441;
    --display: "Avenir Next", Avenir, "Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
    --text: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --mono: "SF Mono", ui-monospace, Menlo, Consolas, "Liberation Mono", monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root { --ink: #e6ecea; --ink-soft: #a7b5b1; --paper: #121b20; --card: #1a252b; --rule: #2c3a40; --accent: #5fb8a3; --warm: #e3b45a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.5 var(--text); font-variant-numeric: tabular-nums; }
  main { max-width: 900px; margin: 0 auto; padding: 40px 32px 56px; }
  .eyebrow { margin: 0 0 8px; font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
  h1 { margin: 0 0 12px; font: 600 clamp(26px, 5vw, 34px)/1.15 var(--display); }
  p { max-width: 62ch; color: var(--ink-soft); margin: 0 0 24px; }
  .wrap { overflow-x: auto; border: 1px solid var(--rule); border-radius: 6px; background: var(--card); }
  table { width: 100%; border-collapse: collapse; min-width: 560px; }
  th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--rule); vertical-align: top; }
  tr:last-child th, tr:last-child td { border-bottom: 0; }
  thead th { font: 600 11.5px/1.2 var(--mono); letter-spacing: .06em; text-transform: uppercase; color: var(--ink-soft); }
  tbody th small { display: block; font-weight: 400; font-size: 13px; color: var(--ink-soft); }
  .num { text-align: right; white-space: nowrap; }
  a { color: var(--accent); font-weight: 600; text-underline-offset: 3px; }
  code { font: 13px var(--mono); }
  td time { white-space: nowrap; }
  footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid var(--rule); font: 12px/1.4 var(--mono); color: var(--ink-soft); }
  @media (max-width: 640px) { main { padding: 24px 16px 40px; } }
</style>
</head>
<body>
<main>
  <p class="eyebrow">Generated by build.mjs</p>
  <h1>Pro renewal notices</h1>
  <p>One page per customer, built from <code>template.html</code> and <code>customers.json</code>. Each notice holds only that customer's figures and prints cleanly to PDF from the browser.</p>
  <div class="wrap">
  <table>
    <thead><tr><th scope="col">Account</th><th scope="col" class="num">Seats</th><th scope="col">Renewal</th><th scope="col" class="num">Today</th><th scope="col" class="num">First year</th><th scope="col" class="num">After</th></tr></thead>
    <tbody>${rows}
    </tbody>
  </table>
  </div>
  <footer>Sample scenario: Lumen Desk is fictional. Monthly amounts in USD.</footer>
</main>
</body>
</html>
`;
}
