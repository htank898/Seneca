#!/usr/bin/env node
// Compile a real LaTeX document to PDF with Tectonic (MIT): one binary, no TeX Live install.
// Packages are fetched on first use and cached, so the first build of a new document is slower.
//
//   node latex-pdf.mjs doc.tex [--out doc.pdf] [--preview] [--keep-logs]
//
// --preview also writes doc.page-1.png (first page, 1650 px tall) for a visual check.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, renameSync, rmSync, statSync, readFileSync, mkdtempSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { parseArgs } from "./_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const input = args._[0];
if (!input) {
  console.error("usage: latex-pdf.mjs <doc.tex> [--out doc.pdf] [--preview] [--keep-logs]");
  process.exit(1);
}
const texPath = resolve(input);
if (!existsSync(texPath)) { console.error(`no such file: ${texPath}`); process.exit(1); }
const out = resolve(args.out || texPath.replace(/\.tex$/i, "") + ".pdf");

const which = spawnSync("tectonic", ["--version"], { encoding: "utf8" });
if (which.error) {
  console.error("tectonic is required for LaTeX → PDF.\n  macOS:  brew install tectonic\n  other:  https://tectonic-typesetting.github.io/install.html");
  process.exit(1);
}
console.error(`[latex] ${which.stdout.trim()}`);

const work = mkdtempSync(join(tmpdir(), "ai-math-latex-"));
const r = spawnSync("tectonic", ["-X", "compile", "--outdir", work, "--keep-logs", texPath],
  { cwd: dirname(texPath), encoding: "utf8" });
const built = join(work, basename(texPath).replace(/\.tex$/i, "") + ".pdf");
if (r.status !== 0 || !existsSync(built)) {
  // Tectonic prints "error: file.tex:LINE: message"; surface those first.
  const lines = `${r.stdout}\n${r.stderr}`.split("\n");
  const errs = lines.filter((l) => /^error|:\d+: /.test(l));
  console.error(`[latex] compile failed:\n${(errs.length ? errs : lines.slice(-30)).join("\n")}`);
  process.exit(1);
}
const warnings = `${r.stderr}`.split("\n").filter((l) => /^warning/.test(l));
if (warnings.length) console.error(`[latex] ${warnings.length} warning(s):\n${warnings.slice(0, 8).join("\n")}`);

mkdirSync(dirname(out), { recursive: true });
renameSync(built, out);
// The PDF's objects are compressed, so read the page count from XeTeX's log instead.
const log = join(work, basename(texPath).replace(/\.tex$/i, "") + ".log");
const pages = existsSync(log) ? +(/Output written on .*?\((\d+) pages?/.exec(readFileSync(log, "utf8"))?.[1] || 0) : 0;
if (args["keep-logs"] && existsSync(log)) renameSync(log, out.replace(/\.pdf$/i, ".log"));
rmSync(work, { recursive: true, force: true });
console.log(`pdf: ${out} (${pages || "?"} page${pages === 1 ? "" : "s"}, ${(statSync(out).size / 1024).toFixed(0)} KB)`);

if (args.preview) {
  // macOS `sips` rasterizes the first page; elsewhere, open the PDF to check it.
  const png = out.replace(/\.pdf$/i, ".page-1.png");
  const sips = spawnSync("sips", ["-s", "format", "png", "-Z", "1650", out, "--out", png], { encoding: "utf8" });
  if (sips.status === 0 && existsSync(png)) console.log(`preview: ${png}`);
  else console.error("[latex] preview needs macOS `sips`; open the PDF to check it instead");
}
