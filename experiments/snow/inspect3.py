import bpy
rig = bpy.data.objects["RIG-Snow"]
for bn in ("Properties", "Properties_Character_Snow"):
    pb = rig.pose.bones[bn]
    print(bn, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in pb.items() if not k.startswith("_")})
for bn in ("Jaw", "MSTR-Eyelid_Upper.L", "MSTR-Eyebrow.L", "ACT-Lips_Corner.L", "TGT-Eyes", "FK-Head", "MSTR-Mouth", "IK-Wrist.L", "FK-UpperArm.L"):
    pb = rig.pose.bones[bn]
    print(bn, "rotmode", pb.rotation_mode, "lock_loc", tuple(pb.lock_location), "lock_rot", tuple(pb.lock_rotation),
          "head", tuple(round(x, 3) for x in pb.bone.head_local), "len", round(pb.bone.length, 3))
print([ (l.name, l.type, round(l.data.energy,1)) for l in bpy.data.objects if l.type=="LIGHT"])
print("world", bpy.context.scene.world and bpy.context.scene.world.name)
