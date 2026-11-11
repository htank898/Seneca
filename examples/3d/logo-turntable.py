import bkit as k
k.reset()
k.render_settings(res=(1080, 1080))  # --preview for 540p
k.frames(1, 48, fps=24)
k.world("#cfd6e0", 0.6)
k.backdrop("#1f2a44")
logo = k.text("SENECA", size=0.55, loc=(0, 0, 0.9), mat=k.material("#f2c14e", roughness=0.25, metallic=1.0), extrude=0.08, bevel=0.015)
puck = k.cylinder(radius=0.7, depth=0.25, loc=(0, 0, 0.125), mat=k.material("#e9edf2", roughness=0.4), bevel=0.02)
cut = k.cube(size=0.5, loc=(0, -0.7, 0.2), rot=(0, 0, 45))
k.add_boolean(puck, cut)
pivot = k.empty("Pivot")
logo.parent = pivot
k.turntable(pivot)
k.studio_lights(target=[logo, puck])
k.camera(loc=(0, -6, 2.2), fit=[logo, puck], lens=60, margin=1.3)
k.finish()
