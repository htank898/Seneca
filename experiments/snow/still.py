import bpy, sys, os
s = bpy.context.scene
s.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"; prefs.get_devices()
for d in prefs.devices: d.use = True
s.cycles.device = "GPU"; s.cycles.samples = 64; s.cycles.use_denoising = True
s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1280, 720, 100
s.render.filepath = os.path.abspath("../frames/test_default.png")
bpy.ops.render.render(write_still=True)
