#!/usr/bin/env node
// Character image(s) -> textured, Rigify-rigged Blender character. All local.
//
//   node char3d.mjs front.png --out <dir> [--back b.png] [--left l.png] [--right r.png]
//        [--height 1.8] [--steps 12] [--seed 42] [--texture 1024|2048] [--pipeline 512]
//        [--facing auto|-Y|+Y|+X|-X] [--project 0.85] [--weights proxy|direct]
//        [--mesh existing.glb] [--regen] [--no-render] [--open]
//
// Stages (each skipped when its output exists, so re-runs only redo what changed):
//   1. prep      views/*.png + views.json   BiRefNet cut-outs, framed, pose check
//   2. generate  raw.glb (+ raw.obj, raw.json)  TRELLIS.2 on the front view (the slow part)
//   3. rig       character.blend, character_rigged.glb, landmarks.json, check_*.png
// --mesh skips 2 and rigs any GLB you already have. --regen forces 2 again (new --seed/--steps).
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const flags = {};
const pos = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith("--")) {
    const v = argv[i + 1];
    if (v === undefined || v.startsWith("--")) flags[a.slice(2)] = true;
    else { flags[a.slice(2)] = v; i++; }
  } else pos.push(a);
}
const front = pos[0] || flags.front;
if (!front || !flags.out) {
  console.error("usage: char3d.mjs front.png --out <dir> [--back b.png] [--left l.png] [--right r.png] [--mesh raw.glb]");
  process.exit(1);
}
const out = resolve(flags.out);
mkdirSync(out, { recursive: true });

const home = process.env.SENECA_CHAR3D_HOME || join(homedir(), ".cache/seneca/char3d");
const enginePy = join(home, "trellis-silicon/.venv/bin/python");
const haveEngine = existsSync(enginePy);

function run(label, cmd, args, opts = {}) {
  const t0 = Date.now();
  console.log(`[char3d] ${label} ...`);
  const r = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  const s = ((Date.now() - t0) / 1000).toFixed(1);
  if (r.status !== 0) {
    console.error(`[char3d] ${label} failed (exit ${r.status}) after ${s}s`);
    process.exit(r.status || 1);
  }
  console.log(`[char3d] ${label} done in ${s}s`);
}

// Python for prep: the engine venv (has torch + BiRefNet); without it, a throwaway uv env with
// Pillow + numpy is enough as long as every input already has a real alpha channel.
function py(script, args) {
  if (haveEngine) return [enginePy, [join(here, script), ...args]];
  return ["uv", ["run", "-q", "--no-project", "--with", "pillow", "--with", "numpy", "python", join(here, script), ...args]];
}

// 1. prep
const viewsDir = join(out, "views");
const viewsJson = join(viewsDir, "views.json");
const prepArgs = ["--out", viewsDir, "--front", resolve(front)];
for (const v of ["back", "left", "right"]) if (flags[v]) prepArgs.push(`--${v}`, resolve(flags[v]));
const [pcmd, pargs] = py("prep.py", prepArgs);
run("prep (background removal + framing)", pcmd, pargs);
const views = JSON.parse(readFileSync(viewsJson, "utf8"));

// 2. generate
let mesh = flags.mesh ? resolve(flags.mesh) : join(out, "raw.glb");
if (!flags.mesh && (flags.regen || !existsSync(mesh))) {
  if (!haveEngine) {
    console.error(`[char3d] engine not installed. Run: bash ${join(here, "setup.sh")}`);
    process.exit(1);
  }
  const g = [join(here, "generate.py"), views.front.path, "--out", join(out, "raw"),
    "--seed", String(flags.seed || 42), "--texture", String(flags.texture || 1024),
    "--pipeline", String(flags.pipeline || "512")];
  if (flags.steps) g.push("--steps", String(flags.steps));
  console.log("[char3d] generating with TRELLIS.2: several minutes; close memory-heavy apps on a 16 GB Mac");
  run("generate (TRELLIS.2)", enginePy, g);
} else if (!flags.mesh) {
  console.log(`[char3d] reusing ${mesh} (pass --regen to generate again)`);
}

// 3. rig
const b = [join(here, "../../blender/scripts/blender.mjs"), join(here, "rig_character.py"),
  "--mesh", mesh, "--views", viewsJson, "--height", String(flags.height || 1.8),
  "--blend", join(out, "character.blend"), "--glb", join(out, "character_rigged.glb"),
  "--out", join(out, "check.png")];
for (const f of ["facing", "project", "weights", "voxel"]) if (flags[f] !== undefined) b.push(`--${f}`, String(flags[f]));
if (flags["no-render"]) b.push("--no-render");
if (flags.preview) b.push("--preview");
run("rig (clean, landmarks, Rigify, weights, checks)", "node", b);

console.log(`[char3d] outputs in ${out}:
  character.blend          open in Blender: rig "rig" with IK/FK controls, mesh "Character"
  character_rigged.glb     deform skeleton + skinned mesh for game engines / the web
  landmarks.json           detected joints (metres, facing -Y, left = +X)
  check_{front,back,three_quarter,bones,pose}.png   look at these before animating`);
if (flags.open) spawnSync("open", [join(out, "character.blend")]);
