# bpy reference (Blender 5.2)

Checked against Blender 5.2.2 LTS: the `blender-v5.2-release` doc sources (`doc/python_api/rst/info_*.rst`) and the API of the installed copy. Read this when you need something `bkit` doesn't cover, or when a script fails in a way you can't explain.

## Running Blender with no window

```bash
Blender -b --factory-startup --python-exit-code 1 -P scene.py -- --my-flag value
```
- `-b` runs in the background with no window. `--factory-startup` ignores the user's prefs and add-ons, so renders are reproducible. `--python-exit-code 1` makes a Python error fail the process. Without it, Blender exits 0 after a traceback.
- Everything after `--` goes to the script in `sys.argv`.
- Blender's bundled Python **ignores `PYTHONPATH`**. Use `--python-expr "import sys; sys.path.insert(0, '...')"` before `-P`, which is what `blender.mjs` does.
- On macOS the binary is `/Applications/Blender.app/Contents/MacOS/Blender`. It runs Python 3.13.

## Use the data API, not operators

`bpy.ops.*` are the UI's tools. They act on the *context* (the active object, the selection, the editor under the mouse), only report success or failure, and fail their `poll()` check when the context is wrong (`RuntimeError: Operator ... poll() failed, context is incorrect`). Prefer:

| Instead of | Use |
|---|---|
| `bpy.ops.mesh.primitive_*_add` | `bmesh.ops.create_cube / create_uvsphere / create_cone / create_grid / create_icosphere / create_circle / create_monkey`, then `bm.to_mesh(me)` |
| Building faces in edit mode | `me.from_pydata(verts, edges, faces)` + `me.validate()`, or bmesh |
| `bpy.ops.object.modifier_add` | `obj.modifiers.new(name, 'BEVEL')` |
| `bpy.ops.object.select_all` + delete | `bpy.data.objects.remove(obj)` |
| Creating an object | `obj = bpy.data.objects.new(name, data)` then `scene.collection.objects.link(obj)` |

When you must call an operator, give it the context it expects:
```python
with bpy.context.temp_override(object=obj, active_object=obj,
                               selected_objects=[obj], selected_editable_objects=[obj]):
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
```
Operators that work fine in the background: `render.render`, `wm.save_as_mainfile`, `export_scene.gltf`, `import_scene.gltf`, `wm.obj_import`, `wm.stl_import`, `object.shade_smooth_by_angle` (with an override).

## Gotchas from the docs

- **Names aren't guaranteed.** `bpy.data.meshes.new("Box")` can come back as `Box.001` if the name is taken or longer than 63 bytes. Keep the Python reference you got back; don't look things up by name later.
- **Changes don't apply until an update.** After moving or parenting, `matrix_world` is stale until `bpy.context.view_layer.update()`. `bkit.bounds()` calls it for you.
- **Don't hold references across reallocation.** Adding many items to a collection, switching modes (`object.mode_set`), or undo can free memory. Re-fetch `mesh.polygons` and similar afterwards, or the script crashes. Avoid edit mode in scripts entirely.
- **Edit-mode data is separate.** `obj.data` doesn't reflect edit-mode changes until you leave edit mode. Do geometry in bmesh in object mode.
- **Faces:** `mesh.polygons` is for storage and export, `mesh.loop_triangles` is read-only triangles, and bmesh faces are for creating and editing.
- **No redraw while a script runs.** Not an issue in the background.

## Changes in 5.x you'll trip on

- **Engine IDs:** `'BLENDER_EEVEE'` (the `_NEXT` suffix is gone), `'CYCLES'`, `'BLENDER_WORKBENCH'`.
- **Node trees on by default:** new materials and worlds already have one. `Material.use_nodes` and `World.use_nodes` are deprecated and slated for removal in 6.0, so don't set them.
- **Compositor:** `scene.node_tree` is gone. Use `scene.compositing_node_group`, a node group you create and assign.
- **Layered actions:** `action.fcurves` is gone. Keyframes live in `action.layers[...].strips[...]` channelbags, per slot. `obj.keyframe_insert(path, frame=...)` still works and is the easy route. To edit F-curves:
  ```python
  from bpy_extras import anim_utils
  cb = anim_utils.action_get_channelbag_for_slot(obj.animation_data.action, obj.animation_data.action_slot)
  for fc in cb.fcurves: ...
  ```
  To make new keys linear, set `bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'` before inserting (`bkit.key(..., linear=True)` does this).
- **Video output:** set `image_settings.media_type = 'VIDEO'` *before* `file_format = 'FFMPEG'`. Stills use `media_type = 'IMAGE'`.
- **Auto smooth:** `mesh.use_auto_smooth` is gone. Use `mesh.shade_smooth()` plus the `object.shade_smooth_by_angle` operator, or a Bevel modifier with `harden_normals = True`.

## Principled BSDF input names (5.2)

`Base Color, Metallic, Roughness, IOR, Alpha, Normal, Diffuse Roughness, Subsurface Weight / Radius / Scale, Specular IOR Level, Specular Tint, Anisotropic, Anisotropic Rotation, Transmission Weight, Coat Weight / Roughness / IOR / Tint / Normal, Sheen Weight / Roughness / Tint, Emission Color, Emission Strength, Thin Film Thickness / IOR, Thin Wall`

Socket colors are **linear** RGBA. Convert hex from sRGB first (`bkit.rgb`).

## Color management

- `view_settings.view_transform`: `'AgX'` (the default; handles bright highlights gracefully), `'Filmic'`, `'Standard'` (use it for flat brand colors that must match hex exactly, such as logos and UI mockups), `'Khronos PBR Neutral'` (accurate product color).
- `view_settings.look` for AgX: `'None'`, `'AgX - Punchy'`, `'AgX - Very High Contrast'`, `'AgX - High Contrast'`, `'AgX - Medium High Contrast'`, `'AgX - Base Contrast'`, `'AgX - Medium Low Contrast'`, `'AgX - Low Contrast'`, `'AgX - Very Low Contrast'`, `'AgX - Greyscale'`. The prefix is part of the name.
- AgX desaturates bright, saturated colors. If a brand color has to read exactly, use `Standard` and flat lighting, or emission.

## Render settings

- **EEVEE:** `scene.eevee.taa_render_samples` (16 for a preview, 64 to 128 for a final), `use_raytracing` (reflections and refraction; needed for convincing chrome and glass), `use_shadows`, `use_fast_gi`.
- **Cycles:** `scene.cycles.samples`, `use_adaptive_sampling`, `use_denoising`, `device = 'GPU'`. On Apple Silicon, set `preferences.addons['cycles'].preferences.compute_device_type = 'METAL'`, call `refresh_devices()`, and set `d.use` for each device. **The first Cycles render compiles Metal shaders (about a minute, once). After that, a 540p preview at 32 samples takes about 2 s on an M4.**
- **Transparent background:** `render.film_transparent = True` and `image_settings.color_mode = 'RGBA'` with PNG.
- **Formats:** `PNG`, `JPEG`, `WEBP`, `OPEN_EXR`, `FFMPEG` (container `MPEG4`, codec `H264`, `constant_rate_factor = 'HIGH'`).

## Cameras and lights

- `cam.lens` is in mm on a 36 mm sensor. Use 24–35 for environments, 50 for neutral shots, 70–100 for products and hero shots (less distortion). `cam.dof.use_dof`, `focus_object` or `focus_distance`, `aperture_fstop` (1.4 is very shallow; 8 keeps everything sharp).
- Aim with `direction.to_track_quat('-Z', 'Y').to_euler()`. Cameras and lights point down their local −Z.
- Light `energy` is in watts. Area lights: a few hundred W at 2–3 m for a 1 m object; power needed grows with distance². Sun: `energy` is irradiance; 1–5 is typical. `light.color` is linear RGB (3 values, no alpha).

## Importing assets

```python
bpy.ops.import_scene.gltf(filepath="model.glb")      # .glb/.gltf; selects the imported objects
bpy.ops.wm.obj_import(filepath="model.obj")
bpy.ops.wm.stl_import(filepath="part.stl")
imported = list(bpy.context.selected_objects)
```
STEP files from the text-to-cad plugin: export them to GLB or STL first, then import.

## Debugging a failed script

1. `blender.mjs` prints the traceback. The line in *your* scene file is the one to fix.
2. `AttributeError` on a property usually means the API changed in 5.x. Check the list above, or ask Blender directly:
   `Blender -b --factory-startup --python-expr "import bpy; print([p.identifier for p in bpy.types.Light.bl_rna.properties])"`
3. A `KeyError` on a node input means the socket name is wrong. Print `[i.name for i in node.inputs]`.
4. For an enum value error, the message lists the valid values. Read it.
