"""generate: one RGBA character image -> textured mesh (GLB) with TRELLIS.2 on Apple Silicon.

    python generate.py <dir>/views/front.png --out <dir>/raw [--steps 12] [--seed 42]
                       [--pipeline 512|1024|1024_cascade] [--texture 1024|2048]

Runs in the engine venv (setup.sh). Writes <out>.glb (PBR: base colour, metallic, roughness;
~200K faces), <out>.obj (full-resolution decoder mesh, untextured) and <out>.json (timings,
mesh size, peak memory).

The shape engine sits behind generate_mesh() so another local model (e.g. TripoSG, MIT) can
replace TRELLIS.2 without touching the rest of the pipeline.
"""
import argparse
import json
import os
import resource
import sys
import time

BIREFNET = "ZhengPeng7/BiRefNet"
BIREFNET_REV = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"


def _use_mit_matte():
    """TRELLIS.2's pipeline.json builds its background remover as BiRefNet(model_name=
    "briaai/RMBG-2.0"), which is CC BY-NC. Swap the class for one pinned to BiRefNet's own MIT
    weights before the pipeline loads, so RMBG-2.0 is never downloaded or run. (Our inputs are
    already RGBA cut-outs, so preprocess_image skips the matte entirely; this only matters for
    the pipeline's load step and the optional colour match.)"""
    from trellis2.pipelines import rembg
    from transformers import AutoModelForImageSegmentation
    base = rembg.BiRefNet

    class MitBiRefNet(base):
        def __init__(self, model_name=None):  # noqa: ARG002  (config's RMBG-2.0 name ignored)
            self.model = AutoModelForImageSegmentation.from_pretrained(
                BIREFNET, revision=BIREFNET_REV, trust_remote_code=True)
            self.model.float().eval()  # weights ship fp16; inputs are fp32
            from torchvision import transforms
            self.transform_image = transforms.Compose([
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])

    rembg.BiRefNet = MitBiRefNet


def generate_mesh(image_path, out_base, pipeline_type="512", steps=None, seed=42, texture=1024,
                  resident=False):
    from trellis_silicon import core  # must come first: sets MPS/attention env before torch

    _use_mit_matte()
    t0 = time.time()
    pipeline = core.load_pipeline(pipeline_type, resident=resident)
    t_load = time.time() - t0
    print(f"[gen] pipeline {pipeline_type} loaded in {t_load:.0f}s (low_vram={pipeline.low_vram})",
          flush=True)
    img = core.PILImage.open(image_path)
    if img.mode != "RGBA":
        print("[gen] warning: input has no alpha; run prep.py first", flush=True)
    result = core.generate_glb(pipeline, img, seed=seed, pipeline_type=pipeline_type,
                               texture_size=texture, output_base=out_base, steps=steps)
    obj_path = f"{out_base}.obj"
    with open(obj_path, "w") as f:
        for v in result["verts"]:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for fc in result["faces"]:
            f.write(f"f {fc[0] + 1} {fc[1] + 1} {fc[2] + 1}\n")
    return {
        "engine": "trellis2",
        "pipeline": pipeline_type,
        "steps": steps,
        "seed": seed,
        "glb": result["glb_path"] or f"{out_base}.glb",
        "obj": obj_path,
        "vertices": result["vertices"],
        "triangles": result["triangles"],
        "load_s": round(t_load, 1),
        "gen_s": round(result["gen_time"], 1),
        "bake_s": round(result["bake_time"], 1) if result["bake_time"] else None,
        "bake_backend": result["backend"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", required=True, help="output base path without extension")
    ap.add_argument("--pipeline", default="512", choices=["512", "1024", "1024_cascade"])
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--texture", type=int, default=1024, choices=[512, 1024, 2048])
    ap.add_argument("--resident", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time()
    try:
        stats = generate_mesh(a.image, a.out, a.pipeline, a.steps, a.seed, a.texture, a.resident)
    except Exception as e:  # surface the watchdog help text etc. without a 200-line trace
        print(f"[gen] FAILED: {type(e).__name__}: {e}", flush=True)
        return 2
    stats["total_s"] = round(time.time() - t0, 1)
    stats["peak_rss_gb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2)
    with open(f"{a.out}.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"[gen] {stats['glb']}: {stats['triangles']:,} tris, {stats['total_s']}s total, "
          f"peak RSS {stats['peak_rss_gb']} GB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
