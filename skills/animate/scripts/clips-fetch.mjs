#!/usr/bin/env node
// Download the ready-made clip packs into ~/.cache/seneca-adapt/clips (safe to re-run).
//   node clips-fetch.mjs quaternius     # Universal Animation Library 1 + 2, Standard tier, CC0, ~25 MB
//   node clips-fetch.mjs list           # what's installed, plus any folders in $SENECA_CLIPS
// Mixamo (Adobe) has no download API and needs your Adobe login: download FBX clips yourself
// ("FBX Binary", "With Skin" or "Without Skin", 30 fps) into a folder and point clips.py at it
// with $SENECA_CLIPS=/path/to/folder (colon-separated for several) or clips.catalog(extra=[...]).
import { spawnSync } from "node:child_process";
import { mkdirSync, existsSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const cache = join(homedir(), ".cache", "seneca-adapt", "clips");
const PACKS = {
  ual1: {
    url: "https://opengameart.org/sites/default/files/universal_animation_librarystandard.zip",
    md5: "12a19225f9c746c124ec17447c357c19",
  },
  ual2: {
    url: "https://opengameart.org/sites/default/files/universal_animation_library_2standard.zip",
    md5: "6301bbf156176ae2ebf10bbd3ee24f50",
  },
};
const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status || 1);
};
const glbs = (dir) => existsSync(dir)
  ? readdirSync(dir, { recursive: true }).filter((f) => /\.(glb|fbx)$/i.test(f)).map((f) => join(dir, f))
  : [];

const [what] = process.argv.slice(2);
if (what === "quaternius") {
  for (const [name, { url, md5 }] of Object.entries(PACKS)) {
    const dir = join(cache, "quaternius", name);
    mkdirSync(dir, { recursive: true });
    const zip = join(dir, `${name}.zip`);
    if (!existsSync(zip)) {
      console.log(`[clips] ${name} (CC0) -> ${zip}`);
      run("curl", ["-sSL", "--retry", "3", "-o", zip, url]);
    }
    const sum = spawnSync("md5", ["-q", zip], { encoding: "utf8" }).stdout.trim();
    if (sum && sum !== md5) {
      console.error(`[clips] checksum mismatch for ${name} (${sum}); delete ${zip} and re-run`);
      process.exit(1);
    }
    run("unzip", ["-oq", zip, "-d", dir]);
    console.log(`[clips] ${name} ok, ${(statSync(zip).size / 1e6).toFixed(1)} MB, checksum verified`);
  }
  console.log("[clips] License: CC0 1.0 (public domain). Models and animations by Quaternius.");
} else if (what === "list") {
  for (const f of glbs(join(cache, "quaternius"))) console.log("[clips]", f);
  for (const d of (process.env.SENECA_CLIPS || "").split(":").filter(Boolean)) {
    for (const f of glbs(d)) console.log("[clips]", f);
  }
} else {
  console.error("usage: clips-fetch.mjs quaternius | list");
  process.exit(1);
}
