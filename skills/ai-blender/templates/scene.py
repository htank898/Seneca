"""Starter scene: a hero object on a seamless studio backdrop.

Copy this next to where the render should live, edit the SUBJECT section, then:
    node <skill>/scripts/blender.mjs scene.py --preview        # fast look
    node <skill>/scripts/blender.mjs scene.py --engine CYCLES  # final
"""
import bkit as k

k.reset()
k.render_settings(res=(1920, 1080))           # EEVEE by default; --engine CYCLES for final
k.world("#1d1f24", 0.25)
k.backdrop("#ece7df")

# ---- SUBJECT: replace with the thing you're showing ----
accent = k.material("#e0512f", roughness=0.32, coat=0.4)
dark = k.material("#22252b", roughness=0.45)
chrome = k.metal("#d6d6d6", roughness=0.12)

base = k.cylinder(radius=0.9, depth=0.18, loc=(0, 0, 0.09), mat=dark, bevel=0.03)
body = k.cube(size=1.0, loc=(0, 0, 0.68), rot=(0, 0, 28), mat=accent, bevel=0.08)
orb = k.sphere(radius=0.32, loc=(0.95, -0.55, 0.32), mat=chrome)
ring = k.torus(major=0.42, minor=0.06, loc=(-0.95, -0.45, 0.06), mat=accent)
subject = [base, body, orb, ring]
# ---------------------------------------------------------

k.studio_lights(target=subject)
k.camera(loc=(4.2, -6.0, 2.6), look_at=body, lens=70, fit=subject, margin=1.35)
k.finish()
