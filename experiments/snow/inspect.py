import bpy, collections
print("=== objects")
for o in bpy.data.objects:
    extra = ""
    if o.type == "MESH":
        sk = o.data.shape_keys
        extra = f" verts={len(o.data.vertices)} shapekeys={len(sk.key_blocks) if sk else 0} mods={[m.type for m in o.modifiers]}"
    if o.type == "ARMATURE":
        extra = f" bones={len(o.data.bones)}"
    print(f"{o.type:9s} {o.name:40s} hide_render={o.hide_render}{extra}")
print("=== texts")
for t in bpy.data.texts:
    print(t.name, len(t.as_string()), "use_module=", t.use_module)
print("=== driver expressions using python (non-simple)")
n = collections.Counter()
for idb in list(bpy.data.objects) + list(bpy.data.shape_keys) + list(bpy.data.armatures) + list(bpy.data.meshes):
    ad = getattr(idb, "animation_data", None)
    if ad:
        for d in ad.drivers:
            n[d.driver.type] += 1
            if d.driver.type == "SCRIPTED" and not d.driver.is_simple_expression:
                n["py:" + d.driver.expression[:40]] += 1
print(n.most_common(20))
print("=== collections", [c.name for c in bpy.data.collections])
print("=== scene", bpy.context.scene.name, bpy.context.scene.render.engine)
