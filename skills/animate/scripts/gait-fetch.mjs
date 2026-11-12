#!/usr/bin/env node
// Download the gait libraries into ~/.cache/seneca-adapt (resumable; safe to re-run).
//   node gait-fetch.mjs 100style        # 1.5 GB, CC BY 4.0 (credit "The 100STYLE Dataset - Ian Mason")
//   node gait-fetch.mjs cmu 02_01 07_12 # single CMU clips (gait.py also fetches these on demand)
import { spawnSync } from "node:child_process";
import { mkdirSync, existsSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const cache = join(homedir(), ".cache", "seneca-adapt");
const [what, ...rest] = process.argv.slice(2);
const curl = (url, dest) => {
  const r = spawnSync("curl", ["-sSL", "-C", "-", "--retry", "3", "-o", dest, url], { stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status || 1);
};
if (what === "100style") {
  const dir = join(cache, "100style");
  mkdirSync(dir, { recursive: true });
  const dest = join(dir, "100STYLE.zip");
  console.log("[gait] 100STYLE (1.5 GB, CC BY 4.0) ->", dest);
  curl("https://zenodo.org/records/8127870/files/100STYLE.zip?download=1", dest);
  const md5 = spawnSync("md5", ["-q", dest], { encoding: "utf8" }).stdout.trim();
  if (md5 && md5 !== "3cf627852fd8192024c04a8d0ef49583") {
    console.error(`[gait] checksum mismatch (${md5}); delete ${dest} and re-run`);
    process.exit(1);
  }
  console.log(`[gait] ok, ${(statSync(dest).size / 1e9).toFixed(2)} GB, checksum verified`);
} else if (what === "cmu" && rest.length) {
  const dir = join(cache, "cmu");
  mkdirSync(dir, { recursive: true });
  for (const t of rest) {
    const subj = String(Number(t.split("_")[0])).padStart(3, "0");
    const dest = join(dir, `${t}.bvh`);
    if (!existsSync(dest)) curl(`https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/${subj}/${t}.bvh`, dest);
    console.log("[gait]", dest);
  }
} else {
  console.error("usage: gait-fetch.mjs 100style | cmu <trial> [trial ...]");
  process.exit(1);
}
