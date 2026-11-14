"""bkit: a small helper layer over bpy for throwing scenes together fast.

Import it from a scene script that runs under scripts/blender.mjs (which puts
this folder on PYTHONPATH):

    import bkit as k
    k.reset()
    k.render_settings(res=(1920, 1080))
    k.world("#1b1d22", 0.3)
    k.backdrop("#e9e4dc")
    box = k.cube(size=1, loc=(0, 0, 0.5), mat=k.material("#d9472b", roughness=0.35), bevel=0.04)
    k.studio_lights(target=box)
    k.camera(loc=(3.5, -4.5, 2.4), look_at=box, lens=60, fit=[box])
    k.finish()

Everything uses the data API (bpy.data, bmesh) rather than operators where
possible, so scripts don't depend on UI context. Verified against Blender 5.2.
"""
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- arguments

def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out[key] = argv[i + 1]
                i += 2
                continue
            out[key] = True
        i += 1
    return out


ARGS = _parse_args()
PREVIEW = bool(ARGS.get("preview"))


def arg(name, default=None):
    """Read a custom CLI flag passed after the scene path, e.g. --color '#ff0000'."""
    return ARGS.get(name, default)


def rng(seed=1):
    """Seeded random generator. Never use the global random module in scenes."""
    return random.Random(seed)


# ---------------------------------------------------------------- scene

def scene():
    return bpy.context.scene


def reset():
    """Delete everything from the startup file and start from an empty scene."""
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.curves, bpy.data.node_groups, bpy.data.images,
                 bpy.data.actions):
        for item in list(coll):
            coll.remove(item)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = scene()
    sc.unit_settings.system = "METRIC"
    sc.frame_start, sc.frame_end = 1, 1
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")


def _link(obj, collection=None):
    (collection or scene().collection).objects.link(obj)
    return obj


def _place(obj, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    obj.location = loc
    obj.rotation_euler = [math.radians(a) for a in rot]
    obj.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return obj


def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene().collection).children.link(c)
    return c


def empty(name="Empty", loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    obj = _link(bpy.data.objects.new(name, None))
    _place(obj, loc, rot)
    if parent:
        obj.parent = parent
    return obj


# ---------------------------------------------------------------- color + materials

def rgb(color):
    """'#rrggbb' (sRGB, as designers write it) or a 0-1 tuple -> linear RGBA for Blender."""
    if isinstance(color, str):
        h = color.lstrip("#")
        srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
        return (*lin, 1.0)
    return (*color[:3], color[3] if len(color) > 3 else 1.0)


def material(color="#cccccc", name=None, roughness=0.5, metallic=0.0, emission=None,
             emission_strength=1.0, transmission=0.0, ior=1.45, coat=0.0, alpha=1.0,
             subsurface=0.0):
    """Principled BSDF material. Returns the material."""
    m = bpy.data.materials.new(name or f"mat_{color}")
    p = m.node_tree.nodes["Principled BSDF"]
    i = p.inputs
    i["Base Color"].default_value = rgb(color)
    i["Roughness"].default_value = roughness
    i["Metallic"].default_value = metallic
    i["IOR"].default_value = ior
    i["Transmission Weight"].default_value = transmission
    i["Coat Weight"].default_value = coat
    i["Subsurface Weight"].default_value = subsurface
    i["Alpha"].default_value = alpha
    if emission:
        i["Emission Color"].default_value = rgb(emission)
        i["Emission Strength"].default_value = emission_strength
    m.diffuse_color = rgb(color)  # viewport/workbench color
    return m


def glass(tint="#ffffff", roughness=0.02):
    return material(tint, roughness=roughness, transmission=1.0, ior=1.5)


def metal(color="#c8c8c8", roughness=0.25):
    return material(color, roughness=roughness, metallic=1.0)


def emissive(color="#ffffff", strength=5.0):
    return material("#000000", emission=color, emission_strength=strength, roughness=1.0)


def assign(obj, mat):
    if mat is None:
        return obj
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# ---------------------------------------------------------------- geometry

def _from_bmesh(name, build, loc, rot, scale, mat, smooth):
    bm = bmesh.new()
    build(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = _link(bpy.data.objects.new(name, me))
    _place(obj, loc, rot, scale)
    assign(obj, mat)
    if smooth:
        shade_smooth(obj, smooth if isinstance(smooth, (int, float)) and smooth is not True else None)
    return obj


def cube(size=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, bevel=0.0, name="Cube"):
    obj = _from_bmesh(name, lambda bm: bmesh.ops.create_cube(bm, size=size, calc_uvs=True),
                      loc, rot, scale, mat, False)
    if bevel:
        add_bevel(obj, bevel)
    return obj


def sphere(radius=0.5, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, segments=64, rings=32,
           name="Sphere"):
    return _from_bmesh(name, lambda bm: bmesh.ops.create_uvsphere(
        bm, u_segments=segments, v_segments=rings, radius=radius, calc_uvs=True),
        loc, rot, scale, mat, True)


def icosphere(radius=0.5, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, subdivisions=3,
              smooth=False, name="Ico"):
    return _from_bmesh(name, lambda bm: bmesh.ops.create_icosphere(
        bm, subdivisions=subdivisions, radius=radius, calc_uvs=True),
        loc, rot, scale, mat, smooth)


def cylinder(radius=0.5, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None,
             segments=64, bevel=0.0, name="Cylinder"):
    return cone(radius, radius, depth, loc, rot, scale, mat, segments, bevel, name)


def cone(radius1=0.5, radius2=0.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None,
         segments=64, bevel=0.0, name="Cone"):
    obj = _from_bmesh(name, lambda bm: bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius1,
        radius2=radius2, depth=depth, calc_uvs=True), loc, rot, scale, mat, 30)
    if bevel:
        add_bevel(obj, bevel)
    return obj


def plane(size=2.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, name="Plane"):
    return _from_bmesh(name, lambda bm: bmesh.ops.create_grid(
        bm, x_segments=1, y_segments=1, size=size / 2, calc_uvs=True),
        loc, rot, scale, mat, False)


def torus(major=0.5, minor=0.15, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None,
          major_segments=96, minor_segments=32, name="Torus"):
    def build(bm):
        rings = []
        for i in range(major_segments):
            u = 2 * math.pi * i / major_segments
            ring = []
            for j in range(minor_segments):
                v = 2 * math.pi * j / minor_segments
                r = major + minor * math.cos(v)
                ring.append(bm.verts.new((r * math.cos(u), r * math.sin(u), minor * math.sin(v))))
            rings.append(ring)
        for i in range(major_segments):
            a, b = rings[i], rings[(i + 1) % major_segments]
            for j in range(minor_segments):
                n = (j + 1) % minor_segments
                bm.faces.new((a[j], b[j], b[n], a[n]))
    return _from_bmesh(name, build, loc, rot, scale, mat, True)


def monkey(loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, subsurf_levels=2, name="Suzanne"):
    obj = _from_bmesh(name, lambda bm: bmesh.ops.create_monkey(bm, calc_uvs=True),
                      loc, rot, scale, mat, True)
    if subsurf_levels:
        add_subsurf(obj, subsurf_levels)
    return obj


def mesh(verts, faces, loc=(0, 0, 0), rot=(0, 0, 0), scale=1, mat=None, smooth=False,
         name="Mesh"):
    """Build a mesh from raw vertex/face lists."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    obj = _link(bpy.data.objects.new(name, me))
    _place(obj, loc, rot, scale)
    assign(obj, mat)
    if smooth:
        shade_smooth(obj)
    return obj


def text(body, size=1.0, loc=(0, 0, 0), rot=(90, 0, 0), mat=None, extrude=0.05, bevel=0.01,
         font=None, align="CENTER", spacing=1.0, name="Text"):
    """3D text. Default rotation stands it upright facing -Y (toward a front camera)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    if font:
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    obj = _link(bpy.data.objects.new(name, cu))
    _place(obj, loc, rot)
    if mat:
        cu.materials.append(mat)
    return obj


def backdrop(color="#e8e6e1", width=20.0, depth=12.0, height=10.0, curve=3.0, back=4.0,
             mat=None, segments=24, name="Backdrop"):
    """Seamless studio cyclorama: a floor that curves up into a back wall at y=back."""
    profile = [(-depth, 0.0)]
    start = back - curve
    for s in range(segments + 1):
        a = (math.pi / 2) * s / segments
        profile.append((start + curve * math.sin(a), curve * (1 - math.cos(a))))
    profile.append((back, height))
    verts, faces = [], []
    for x in (-width / 2, width / 2):
        verts += [(x, y, z) for y, z in profile]
    n = len(profile)
    faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    obj = mesh(verts, faces, mat=mat or material(color, roughness=0.8), smooth=True, name=name)
    return obj


# ---------------------------------------------------------------- modifiers

def shade_smooth(obj, angle=None):
    """Smooth shading; with angle (degrees), keep edges sharper than that crisp."""
    obj.data.shade_smooth()
    if angle:
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    return obj


def add_bevel(obj, width=0.02, segments=4, angle=30):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    obj.data.shade_smooth()
    return m


def add_subsurf(obj, levels=2):
    m = obj.modifiers.new("Subsurf", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    return m


def add_boolean(obj, cutter, operation="DIFFERENCE", hide_cutter=True):
    m = obj.modifiers.new("Boolean", "BOOLEAN")
    m.object = cutter
    m.operation = operation
    m.solver = "EXACT"
    if hide_cutter:
        cutter.hide_render = True
        cutter.hide_viewport = True
    return m


def add_array(obj, count=5, offset=(1.1, 0, 0), relative=True):
    m = obj.modifiers.new("Array", "ARRAY")
    m.count = count
    m.use_relative_offset = relative
    m.use_constant_offset = not relative
    if relative:
        m.relative_offset_displace = offset
    else:
        m.constant_offset_displace = offset
    return m


def add_solidify(obj, thickness=0.02):
    m = obj.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thickness
    return m


def duplicate(obj, loc=None, linked=True):
    """Copy an object. linked=True shares mesh data (cheap instancing)."""
    new = obj.copy()
    if not linked and obj.data:
        new.data = obj.data.copy()
    _link(new)
    if loc is not None:
        new.location = loc
    return new


# ---------------------------------------------------------------- bounds + aiming

def _center(target):
    if target is None:
        return Vector((0, 0, 0))
    if isinstance(target, bpy.types.Object):
        lo, hi = bounds([target])
        return (lo + hi) / 2
    return Vector(target)


def bounds(objs):
    """World-space (min, max) corners over the evaluated geometry of objs."""
    bpy.context.view_layer.update()
    pts = []
    for o in objs:
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _aim(obj, target):
    direction = _center(target) - Vector(obj.location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


look_at = _aim  # public name; camera()/light() take a look_at= argument too


def drop_to_floor(obj, z=0.0):
    lo, _ = bounds([obj])
    obj.location.z += z - lo.z
    return obj


# ---------------------------------------------------------------- camera + lights

def camera(loc=(0, -6, 2), look_at=None, lens=50, fit=None, margin=1.15, dof=None, fstop=2.8,
           ortho=None, name="Camera"):
    """Camera aimed at look_at. fit=[objs] dollies along the view line so they fill the frame.
    dof=obj or point focuses there. ortho=scale switches to orthographic."""
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_end = 1000
    obj = _link(bpy.data.objects.new(name, cam))
    obj.location = loc
    target = look_at if look_at is not None else (fit and _center_of(fit))
    _aim(obj, target if target is not None else (0, 0, 0))
    scene().camera = obj
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    if fit:
        fit_camera(obj, fit, margin)
    if dof is not None:
        cam.dof.use_dof = True
        if isinstance(dof, bpy.types.Object):
            cam.dof.focus_object = dof
        else:
            cam.dof.focus_distance = (Vector(dof) - Vector(obj.location)).length
        cam.dof.aperture_fstop = fstop
    return obj


def _center_of(objs):
    lo, hi = bounds(objs)
    return (lo + hi) / 2


def fit_camera(cam_obj, objs, margin=1.15):
    """Dolly the camera along its view line until every bounding-box corner of objs is in
    frame. margin > 1 leaves breathing room (1.15 = ~15% padding)."""
    bpy.context.view_layer.update()
    corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo, hi = bounds(objs)
    center = (lo + hi) / 2
    r = scene().render
    aspect = r.resolution_x / r.resolution_y
    cam = cam_obj.data
    rot = cam_obj.matrix_world.to_quaternion()
    right, up, back = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0)), rot @ Vector((0, 0, 1))
    local = [((p - center).dot(right), (p - center).dot(up), (p - center).dot(back)) for p in corners]
    if cam.type == "ORTHO":
        w = 2 * max(abs(x) for x, _, _ in local) * margin
        h = 2 * max(abs(y) for _, y, _ in local) * margin
        cam.ortho_scale = max(w, h * aspect)
        far = max(z for _, _, z in local)
        cam_obj.location = center + back * max((Vector(cam_obj.location) - center).length, far + 1)
        return cam_obj
    # sensor_fit AUTO: cam.angle spans the longer image side.
    t = math.tan(cam.angle / 2) / margin
    tx, ty = (t, t / aspect) if aspect >= 1 else (t * aspect, t)
    dist = max(z + max(abs(x) / tx, abs(y) / ty) for x, y, z in local)
    cam_obj.location = center + back * dist
    return cam_obj


def light(kind="AREA", loc=(0, 0, 5), look_at=(0, 0, 0), power=500, color="#ffffff", size=1.0,
          spot_angle=45, name=None):
    """kind: AREA | POINT | SPOT | SUN. power is watts (SUN: strength in W/m^2, ~1-5)."""
    li = bpy.data.lights.new(name or kind.title(), kind)
    li.color = rgb(color)[:3]
    li.energy = power
    if kind == "AREA":
        li.size = size
    elif kind in ("POINT", "SPOT"):
        li.shadow_soft_size = size / 2
    if kind == "SPOT":
        li.spot_size = math.radians(spot_angle)
    if kind == "SUN":
        li.angle = math.radians(size)
    obj = _link(bpy.data.objects.new(li.name, li))
    obj.location = loc
    _aim(obj, look_at)
    return obj


def studio_lights(target=None, scale=None, key=1.0, warm="#fff1e0", cool="#e6eeff"):
    """Three-point rig (key, fill, rim) sized to the target's bounds. key scales all power."""
    objs = target if isinstance(target, (list, tuple)) and target and isinstance(target[0], bpy.types.Object) else None
    if objs is None and isinstance(target, bpy.types.Object):
        objs = [target]
    if objs:
        lo, hi = bounds(objs)
        c = (lo + hi) / 2
        s = scale or max((hi - lo).length, 0.5)
    else:
        c, s = Vector(target or (0, 0, 0)), scale or 1.0
    def at(x, y, z):
        return (c.x + x * s, c.y + y * s, c.z + z * s)
    p = 400 * key * s * s
    return [
        light("AREA", at(-1.6, -1.8, 1.8), c, p, warm, size=1.2 * s, name="Key"),
        light("AREA", at(2.0, -1.2, 0.6), c, p * 0.3, cool, size=2.0 * s, name="Fill"),
        light("AREA", at(0.6, 2.2, 2.0), c, p * 0.8, "#ffffff", size=0.8 * s, name="Rim"),
    ]


def world(color="#202226", strength=0.5):
    """Flat world color: ambient fill plus what reflective surfaces see."""
    w = scene().world
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = rgb(color)
    bg.inputs["Strength"].default_value = strength
    return w


def hdri(path, strength=1.0, rotation=0.0):
    """Light the scene with an .hdr/.exr environment map."""
    w = scene().world
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    mapping = nt.nodes.new("ShaderNodeMapping")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping.inputs["Rotation"].default_value[2] = math.radians(rotation)
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes["Background"]
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    return w


# ---------------------------------------------------------------- animation

def frames(start=1, end=120, fps=30):
    sc = scene()
    sc.frame_start, sc.frame_end = start, end
    sc.render.fps = fps


def key(obj, path, frame, value=None, index=-1, linear=False):
    """Set obj.<path> = value (if given) and keyframe it at frame."""
    if value is not None:
        target = obj
        *parents, attr = path.split(".")
        for p in parents:
            target = getattr(target, p)
        if index >= 0:
            getattr(target, attr)[index] = value
        else:
            setattr(target, attr, value)
    obj.keyframe_insert(path, index=index, frame=frame)
    if linear:
        # The keyframe_new_interpolation_type preference is not honoured in background runs
        # (keys came out Bezier and eased), so set the new keys' interpolation directly.
        from bpy_extras import anim_utils
        ad = obj.animation_data
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot) if ad and ad.action else None
        for fc in (cb.fcurves if cb else []):
            if fc.data_path == path and (index < 0 or fc.array_index == index):
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-4:
                        kp.interpolation = "LINEAR"


def turntable(obj, turns=1, start=None, end=None):
    """Spin obj around Z at constant speed. Loops seamlessly: frame end+1 == frame start."""
    sc = scene()
    start = sc.frame_start if start is None else start
    end = sc.frame_end if end is None else end
    z0 = obj.rotation_euler.z
    key(obj, "rotation_euler", start, z0, index=2, linear=True)
    key(obj, "rotation_euler", end + 1, z0 + 2 * math.pi * turns, index=2, linear=True)
    return obj


# ---------------------------------------------------------------- render

def render_settings(engine="EEVEE", res=(1920, 1080), samples=None, transparent=False,
                    look="AgX - Medium High Contrast", exposure=0.0, motion_blur=False):
    """engine: EEVEE (fast, default) | CYCLES (path traced, slower, best glass/GI) | WORKBENCH."""
    sc = scene()
    r = sc.render
    eng = ARGS.get("engine", engine).upper()
    r.engine = {"EEVEE": "BLENDER_EEVEE", "CYCLES": "CYCLES", "WORKBENCH": "BLENDER_WORKBENCH"}.get(eng, eng)
    if "res" in ARGS:
        res = tuple(int(v) for v in ARGS["res"].lower().split("x"))
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 50 if PREVIEW else 100
    r.film_transparent = transparent
    r.use_motion_blur = motion_blur
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look or "None"
    sc.view_settings.exposure = exposure
    n = int(ARGS.get("samples", samples or 0)) or None
    if r.engine == "CYCLES":
        c = sc.cycles
        c.samples = n or (32 if PREVIEW else 256)
        c.use_adaptive_sampling = True
        c.use_denoising = True
        prefs = bpy.context.preferences.addons["cycles"].preferences
        try:
            prefs.compute_device_type = "METAL"
            prefs.refresh_devices()
            for d in prefs.devices:
                d.use = d.type != "CPU"
            c.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"
        except TypeError:
            c.device = "CPU"
        print(f"[bkit] cycles: {c.samples} samples on {c.device}", flush=True)
    elif r.engine == "BLENDER_EEVEE":
        e = sc.eevee
        # Animations default to 16 samples: on a matte character scene that rendered 3.4x faster
        # than 64 with frames indistinguishable (SSIM 0.992). Stills keep 64; pass --samples 64
        # for an animation with glossy or glass materials.
        anim = ARGS.get("anim") or ARGS.get("frames") or str(ARGS.get("out", "")).lower().endswith(".mp4")
        e.taa_render_samples = n or (16 if PREVIEW or anim else 64)
        e.use_raytracing = not PREVIEW
        e.use_shadows = True
    r.image_settings.color_mode = "RGBA" if transparent else "RGB"


def _summary(kind, path, t0):
    r = scene().render
    w = r.resolution_x * r.resolution_percentage // 100
    h = r.resolution_y * r.resolution_percentage // 100
    print(f"[bkit] {kind}: {path} ({w}x{h}, {r.engine}, {time.time() - t0:.1f}s)", flush=True)


def finish(out=None):
    """End every scene script with this. Reads the runner's flags:
    --out file.png|.jpg|.mp4|dir/   --anim   --blend file.blend   --glb file.glb   --no-render"""
    sc = scene()
    r = sc.render
    out = os.path.abspath(ARGS.get("out") or out or "render.png")
    if ARGS.get("blend"):
        path = os.path.abspath(ARGS["blend"])
        bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
        print(f"[bkit] blend: {path}", flush=True)
    if ARGS.get("glb"):
        path = os.path.abspath(ARGS["glb"])
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True)
        print(f"[bkit] glb: {path}", flush=True)
    if ARGS.get("no-render"):
        return
    if "frames" in ARGS:
        a, b = ARGS["frames"].split("-")
        sc.frame_start, sc.frame_end = int(a), int(b)
    anim = bool(ARGS.get("anim")) or out.endswith(".mp4")
    os.makedirs(os.path.dirname(out) if not out.endswith("/") else out, exist_ok=True)
    t0 = time.time()
    if not anim:
        ext = os.path.splitext(out)[1].lower()
        r.image_settings.media_type = "IMAGE"
        r.image_settings.file_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR",
                                        ".webp": "WEBP"}.get(ext, "PNG")
        if ARGS.get("frame"):
            sc.frame_set(int(ARGS["frame"]))
        r.filepath = out
        bpy.ops.render.render(write_still=True)
        _summary("still", out, t0)
        return
    if out.endswith(".mp4"):
        r.image_settings.media_type = "VIDEO"
        r.image_settings.file_format = "FFMPEG"
        r.ffmpeg.format = "MPEG4"
        r.ffmpeg.codec = "H264"
        r.ffmpeg.constant_rate_factor = "HIGH"
        r.image_settings.color_mode = "RGB"
        r.filepath = out
    else:
        r.image_settings.media_type = "IMAGE"
        r.image_settings.file_format = "PNG"
        r.filepath = os.path.join(out if os.path.isdir(out) or out.endswith("/") else os.path.splitext(out)[0], "f####")
    bpy.ops.render.render(animation=True)
    _summary(f"animation {sc.frame_start}-{sc.frame_end}", r.filepath, t0)
