// Shared bootstrap: installs Playwright into this skill folder on first run,
// then launches Chromium (falling back to an installed Google Chrome).
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

export const SKILL_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

function sh(cmd) {
  execSync(cmd, { cwd: SKILL_DIR, stdio: ["ignore", "inherit", "inherit"] });
}

async function loadPlaywright() {
  if (!existsSync(join(SKILL_DIR, "node_modules", "playwright"))) {
    console.error("[setup] installing playwright into", SKILL_DIR);
    sh("npm install --silent --no-audit --no-fund");
  }
  const require = createRequire(join(SKILL_DIR, "package.json"));
  return require("playwright");
}

export async function launch() {
  const { chromium } = await loadPlaywright();
  try {
    return await chromium.launch();
  } catch {
    try {
      return await chromium.launch({ channel: "chrome" });
    } catch {
      console.error("[setup] downloading Chromium for Playwright (one time)");
      sh("npx playwright install chromium");
      return await chromium.launch();
    }
  }
}

// Minimal --flag value / --flag parser.
export function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

export function fileUrl(p) {
  return "file://" + (p.startsWith("/") ? p : join(process.cwd(), p));
}
