import bpy
rig = bpy.data.objects["RIG-Snow"]
ctl = [b for b in rig.pose.bones if b.custom_shape and not b.name.startswith(("DEF", "ORG", "MCH"))]
print("controls", len(ctl))
import re
print(" ".join(sorted(b.name for b in ctl)))
cam = bpy.data.objects["Camera"]; print("cam", tuple(round(x,2) for x in cam.location), tuple(round(x,2) for x in cam.rotation_euler), cam.data.lens)
print("rig loc", tuple(rig.location), "dims", tuple(round(x,2) for x in rig.dimensions))
s = bpy.context.scene; print("res", s.render.resolution_x, s.render.resolution_y, "samples", s.cycles.samples, "frames", s.frame_start, s.frame_end)
for k in bpy.data.objects["GEO-snow-head"].data.shape_keys.key_blocks: print("sk", k.name, end=" | ")
