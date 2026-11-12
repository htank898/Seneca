"""rig_character: generated mesh (GLB) -> cleaned, scaled, Rigify-rigged character. Runs in Blender.

    node ../../blender/scripts/blender.mjs rig_character.py --mesh raw.glb --views views/views.json \
        --height 1.8 --blend character.blend --glb character_rigged.glb --out check.png

Steps:
  1. import + clean   join parts, merge doubles, fix normals, stand it up facing -Y, feet on z=0,
                      scaled to --height metres (the character's left is +X, as in Rigify)
  2. refine texture   (optional) project the back / left / right views onto the surfaces they see
                      and bake them into the base-colour texture (Cycles EMIT bake)
  3. landmarks        slice the mesh to find crotch, armpits, hands, neck, ankles, toes, heels;
                      joints are re-centred inside the limb; saved to landmarks.json
  4. rig              fit Rigify's basic_human metarig to the landmarks, generate the rig
  5. skin             automatic weights computed on a watertight voxel proxy, transferred to the
                      real mesh (robust to the loose parts and holes AI meshes have)
  6. check            renders front / back / test-pose stills next to --out

Flags: --mesh --views --height 1.8 --facing auto|-Y|+Y|+X|-X --project 0.85 (0 = off)
       --weights proxy|direct --voxel 0.006 (proxy voxel, x height) --blend --glb --out --no-render
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import bkit as k

A = k.arg


def log(*a):
    print("[rig]", *a, flush=True)


# ---------------------------------------------------------------- 1. import + clean
def import_mesh(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"no mesh in {path}")
    for o in meshes:  # bake parent transforms into the objects
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "Character"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    make_opaque(obj)
    if obj.data.has_custom_normals:   # imported normals would override any fix-ups below
        _select([obj], obj)
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    return obj


def make_opaque(obj):
    """Generated textures often carry a stray alpha channel and the GLB marks the material BLEND,
    which renders the character see-through and speckled. A character is solid: cut alpha."""
    for mat in obj.data.materials:
        if not mat or not mat.node_tree:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                a = n.inputs["Alpha"]
                for l in list(a.links):
                    mat.node_tree.links.remove(l)
                a.default_value = 1.0
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = "OPAQUE"
            except TypeError:
                pass


def _slice_runs(V, up, lat, at, half):
    """Number of solid runs along axis `lat` in the slab where V[:, up] is within half of `at`."""
    b = V[np.abs(V[:, up] - at) < half][:, lat]
    span = V[:, up].max() - V[:, up].min()
    return len(_runs(b, 0.02 * span, 0.01 * span))


def stand_up(obj, front_aspect=None):
    """Rotate so the character stands along +Z. Generators disagree on the up axis (TRELLIS.2's
    GLB imports lying down). Candidates: the two longest axes, either sign. A standing figure
    shows two feet in its bottom slice and one head in its top slice; the front view's
    width/height breaks ties (T-poses are nearly square)."""
    V = verts_np(obj)
    ext = V.max(0) - V.min(0)
    depth = int(np.argmin(ext))
    best, best_s = None, -1e9
    for up in [a for a in range(3) if a != depth]:
        lat = 3 - up - depth
        span = ext[up]
        for sign in (1, -1):
            lo = V[:, up].min() if sign > 0 else V[:, up].max()
            hi = V[:, up].max() if sign > 0 else V[:, up].min()
            bottom = _slice_runs(V, up, lat, lo + sign * 0.03 * span, 0.015 * span)
            top = _slice_runs(V, up, lat, hi - sign * 0.04 * span, 0.015 * span)
            s = (2 if bottom == 2 else 0) + (1 if top == 1 else 0)
            if front_aspect:
                s -= 2 * abs(ext[lat] / ext[up] - front_aspect)
            if s > best_s:
                best, best_s = (up, sign), s
    up, sign = best
    target = Vector((0, 0, 1))
    axis = Vector([1.0 if i == up else 0.0 for i in range(3)]) * sign
    if (axis - target).length > 1e-6:
        q = axis.rotation_difference(target)
        transform(obj, q.to_matrix().to_4x4())
        log(f"stood up: {'+' if sign > 0 else '-'}{'XYZ'[up]} -> +Z")
    return up, sign


def verts_np(obj):
    n = len(obj.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def transform(obj, M):
    obj.data.transform(M)
    obj.data.update()


def clean(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    size = max(obj.dimensions)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=size * 1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    # count loose parts (eyes, accessories, floating fragments)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen, parts = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        parts += 1
        stack = [v]
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            stack.extend(e.other_vert(x) for e in x.link_edges)
    nv, nf = len(bm.verts), len(bm.faces)
    bm.free()
    log(f"mesh: {nv:,} verts ({n0 - nv:,} merged), {nf:,} faces, {parts} loose part(s)")
    return parts


def orient(obj, facing, front_aspect=None):
    """Rotate about Z so the character faces -Y. facing='auto' guesses the depth axis from the
    front view's aspect and the front side from where the toes point."""
    V = verts_np(obj)
    lo, hi = V.min(0), V.max(0)
    ext = hi - lo
    if facing == "auto":
        # lateral axis = the one whose width/height matches the front silhouette best
        if front_aspect:
            rx, ry = ext[0] / ext[2], ext[1] / ext[2]
            depth = 1 if abs(rx - front_aspect) <= abs(ry - front_aspect) else 0
        else:
            depth = 1 if ext[0] >= ext[1] else 0
        H = ext[2]
        z = V[:, 2] - lo[2]
        feet = V[z < 0.06 * H, depth]
        shins = V[(z > 0.12 * H) & (z < 0.3 * H), depth]
        shift = (feet.mean() - shins.mean()) if len(feet) and len(shins) else 0.0
        sign = -1 if shift < 0 else 1
        if abs(shift) < 0.005 * H:
            log("warning: toes don't show a clear front; assuming -Y. Re-run with --facing if wrong")
            sign = -1
        facing = ("-" if sign < 0 else "+") + "XY"[depth]
    rot = {"-Y": 0, "+Y": 180, "+X": -90, "-X": 90}[facing]
    if rot:
        transform(obj, Matrix.Rotation(math.radians(rot), 4, "Z"))
    log(f"facing: {facing} -> -Y (rotated {rot} deg)")
    return facing


def normalize(obj, height):
    V = verts_np(obj)
    lo, hi = V.min(0), V.max(0)
    s = height / (hi[2] - lo[2])
    cx = (lo[0] + hi[0]) / 2
    cy = np.median(V[:, 1])
    transform(obj, Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -lo[2])))
    log(f"scaled x{s:.3f} to {height} m, feet on z=0")


# ---------------------------------------------------------------- 2. texture refinement
def _base_color_node(mat):
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf or not bsdf.inputs["Base Color"].is_linked:
        return None, None
    n = bsdf.inputs["Base Color"].links[0].from_node
    while n.type != "TEX_IMAGE" and n.inputs and any(i.is_linked for i in n.inputs):
        n = next(i for i in n.inputs if i.is_linked).links[0].from_node
    return (n if n.type == "TEX_IMAGE" else None), bsdf


VIEW_SPEC = {  # view: (lateral axis, sign, direction toward that camera)
    "front": (0, 1, (0, -1, 0)), "back": (0, -1, (0, 1, 0)),
    "left": (1, 1, (1, 0, 0)), "right": (1, -1, (-1, 0, 0)),
}


def fill_small_holes(obj, max_sides=40):
    """Close the pinholes generated meshes come with (they show as white specks)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    edges = [e for e in bm.edges if e.is_boundary]
    n0 = len(bm.faces)
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=max_sides)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    added = len(bm.faces) - n0
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    if added:
        log(f"filled {added:,} small holes")


def remesh(obj, voxel):
    """Voxel-remesh into one closed surface with consistent normals. Fixes the cracks and flipped
    triangles that shade as dark flecks on open generated meshes; detail is kept down to the
    voxel size. Only used with view textures (they project in object space, so nothing to transfer)."""
    n0 = len(obj.data.polygons)
    rm = obj.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel
    rm.use_smooth_shade = True
    _select([obj], obj)
    bpy.ops.object.modifier_apply(modifier=rm.name)
    log(f"remeshed: {n0:,} -> {len(obj.data.polygons):,} faces (voxel {voxel * 1000:.1f} mm)")


def _skeleton_segments(J):
    v = lambda key: np.array(J[key])
    hip_c = (v("hip.L") + v("hip.R")) / 2
    sh_c = (v("shoulder.L") + v("shoulder.R")) / 2
    segs = [(hip_c, sh_c), (sh_c, v("neck")), (v("neck"), v("head_top"))]
    for s_ in ("L", "R"):
        segs += [(sh_c, v(f"shoulder.{s_}")), (v(f"shoulder.{s_}"), v(f"elbow.{s_}")),
                 (v(f"elbow.{s_}"), v(f"wrist.{s_}")), (v(f"wrist.{s_}"), v(f"hand_tip.{s_}")),
                 (hip_c, v(f"hip.{s_}")), (v(f"hip.{s_}"), v(f"knee.{s_}")),
                 (v(f"knee.{s_}"), v(f"ankle.{s_}")), (v(f"ankle.{s_}"), v(f"toe.{s_}"))]
    return segs


def normals_outward(obj, J):
    """Point every face away from the nearest bone. Generated meshes have open cracks, so
    Blender's own recalculation can't make the normals consistent across them; the flipped
    patches shade as dark flecks. A body's surface always faces away from its skeleton."""
    me = obj.data
    n = len(me.polygons)
    C = np.empty(n * 3)
    Nn = np.empty(n * 3)
    me.polygons.foreach_get("center", C)
    me.polygons.foreach_get("normal", Nn)
    C, Nn = C.reshape(n, 3), Nn.reshape(n, 3)
    best = np.full(n, np.inf)
    away = np.zeros((n, 3))
    for a, b in _skeleton_segments(J):
        ab = b - a
        t = np.clip(((C - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        P = a + t[:, None] * ab
        d = C - P
        dist = np.linalg.norm(d, axis=1)
        m = dist < best
        best[m] = dist[m]
        away[m] = d[m]
    flip = np.flatnonzero((Nn * away).sum(1) < 0)
    if len(flip):
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in flip])
        bm.to_mesh(me)
        bm.free()
        me.update()
    log(f"normals: flipped {len(flip):,} of {n:,} faces to face outward")


def texture_from_views(obj, views, size=2048):
    """Replace the base colour with one baked straight from the reference views: a fresh UV unwrap,
    then every surface takes colour from the views that face it, blended by facing angle
    (weights (n.v)^3, normalised). For generators whose own texture came out unusable."""
    names = [v for v in ("front", "back", "left", "right") if v in views]
    if not names:
        return False
    # fresh, clean UVs
    me = obj.data
    uv = me.uv_layers.new(name="Views")
    me.uv_layers.active = uv
    _select([obj], obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")
    V = verts_np(obj)
    lo, hi = V.min(0), V.max(0)
    mat = bpy.data.materials.new("CharacterViews")
    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)

    def node(t, **kw):
        n = N.new(t)
        for key, val in kw.items():
            setattr(n, key, val)
        return n

    def math_(op, a, b):
        m = node("ShaderNodeMath", operation=op)
        for sock, val in ((m.inputs[0], a), (m.inputs[1], b)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                L.new(val, sock)
        return m.outputs[0]

    tc = node("ShaderNodeTexCoord")
    sep = node("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    geo = node("ShaderNodeNewGeometry")
    color, wsum = None, None
    for name in names:
        meta = views[name]
        axis, sgn, toward = VIEW_SPEC[name]
        S = meta["size"]
        u0, u1 = meta["x0"] / S, meta["x1"] / S
        vb, vt = 1 - meta["y1"] / S, 1 - meta["y0"] / S
        span = hi[axis] - lo[axis]
        if sgn > 0:
            mu, au = (u1 - u0) / span, u0 - (u1 - u0) * lo[axis] / span
        else:
            mu, au = -(u1 - u0) / span, u0 + (u1 - u0) * hi[axis] / span
        mv = (vt - vb) / (hi[2] - lo[2])
        av = vb - mv * lo[2]
        uu = math_("MULTIPLY_ADD", sep.outputs["XY"[axis]], mu)
        uu.node.inputs[2].default_value = au
        vv = math_("MULTIPLY_ADD", sep.outputs["Z"], mv)
        vv.node.inputs[2].default_value = av
        cxyz = node("ShaderNodeCombineXYZ")
        L.new(uu, cxyz.inputs[0])
        L.new(vv, cxyz.inputs[1])
        img = node("ShaderNodeTexImage", extension="EXTEND")
        img.image = bpy.data.images.load(meta.get("tex", meta["path"]), check_existing=True)
        L.new(cxyz.outputs[0], img.inputs[0])
        dot = node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        L.new(geo.outputs["Normal"], dot.inputs[0])
        dot.inputs[1].default_value = toward
        f = math_("MAXIMUM", dot.outputs["Value"], 0.0)
        f = math_("ADD", f, 0.03)
        f = math_("POWER", f, 3.0)
        w = math_("MULTIPLY", f, img.outputs["Alpha"])
        w = math_("ADD", w, 1e-4)
        if color is None:
            color, wsum = img.outputs["Color"], w
            continue
        tot = math_("ADD", wsum, w)
        t = math_("DIVIDE", w, tot)
        mix = node("ShaderNodeMix", data_type="RGBA")
        L.new(t, mix.inputs["Factor"])
        L.new(color, mix.inputs[6])
        L.new(img.outputs["Color"], mix.inputs[7])
        color, wsum = mix.outputs[2], tot
    emit = node("ShaderNodeEmission")
    L.new(color, emit.inputs["Color"])
    out = node("ShaderNodeOutputMaterial")
    L.new(emit.outputs[0], out.inputs["Surface"])
    baked = bpy.data.images.new("character_views", size, size)
    target = node("ShaderNodeTexImage")
    target.image = baked
    uvn = node("ShaderNodeUVMap", uv_map="Views")
    L.new(uvn.outputs["UV"], target.inputs["Vector"])
    N.active = target
    me.materials.clear()
    me.materials.append(mat)
    sc = bpy.context.scene
    prev = sc.render.engine
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.device = "CPU"
    sc.render.bake.margin = 6
    _select([obj], obj)
    bpy.ops.object.bake(type="EMIT")
    sc.render.engine = prev
    baked.pack()
    # final material: principled reading the baked map
    for n in list(N):
        N.remove(n)
    bsdf = node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.65
    tex = node("ShaderNodeTexImage")
    tex.image = baked
    uvn = node("ShaderNodeUVMap", uv_map="Views")
    L.new(uvn.outputs["UV"], tex.inputs["Vector"])
    L.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    out = node("ShaderNodeOutputMaterial")
    L.new(bsdf.outputs[0], out.inputs["Surface"])
    for layer in list(me.uv_layers):
        if layer.name != "Views":
            me.uv_layers.remove(layer)
    log(f"texture baked from views ({', '.join(names)}), {size}px")
    return True


def refine_texture(obj, views, strength):
    """Bake back/left/right views into the base-colour texture where those views see the surface
    head-on. No occlusion test: a surface hidden behind another part in a view still receives
    that view's colour, which the facing-angle falloff keeps mostly to broad, exposed areas."""
    extra = [v for v in ("back", "left", "right") if v in views]
    if not extra or strength <= 0 or not obj.data.materials:
        return False
    mat = obj.data.materials[0]
    tex, bsdf = _base_color_node(mat)
    if tex is None or tex.image is None:
        log("texture refine skipped: no base-colour image on the mesh")
        return False
    V = verts_np(obj)
    lo, hi = V.min(0), V.max(0)
    nt = mat.node_tree
    N = nt.nodes
    L = nt.links

    created = []

    def node(t, **kw):
        n = N.new(t)
        for key, val in kw.items():
            setattr(n, key, val)
        created.append(n)
        return n

    tc = node("ShaderNodeTexCoord")
    sep = node("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    geo = node("ShaderNodeNewGeometry")
    color = tex.outputs["Color"]
    # (view, lateral axis, lateral sign, view direction toward the camera)
    spec = {"back": (0, -1, (0, 1, 0)), "left": (1, 1, (1, 0, 0)), "right": (1, -1, (-1, 0, 0))}
    for name in extra:
        meta = views[name]
        axis, sgn, toward = spec[name]
        S = meta["size"]
        u0, u1 = meta["x0"] / S, meta["x1"] / S
        vb, vt = 1 - meta["y1"] / S, 1 - meta["y0"] / S
        a_lo, a_hi = lo[axis], hi[axis]
        # u = u0 + (u1-u0) * t, t = (c - lo)/(hi - lo) for sgn=+1, (hi - c)/(hi - lo) for sgn=-1
        span = a_hi - a_lo
        if sgn > 0:
            mu, au = (u1 - u0) / span, u0 - (u1 - u0) * a_lo / span
        else:
            mu, au = -(u1 - u0) / span, u0 + (u1 - u0) * a_hi / span
        mv = (vt - vb) / (hi[2] - lo[2])
        av = vb - mv * lo[2]
        mu_n = node("ShaderNodeMath", operation="MULTIPLY_ADD")
        L.new(sep.outputs["XY"[axis]], mu_n.inputs[0])
        mu_n.inputs[1].default_value, mu_n.inputs[2].default_value = mu, au
        mv_n = node("ShaderNodeMath", operation="MULTIPLY_ADD")
        L.new(sep.outputs["Z"], mv_n.inputs[0])
        mv_n.inputs[1].default_value, mv_n.inputs[2].default_value = mv, av
        uv = node("ShaderNodeCombineXYZ")
        L.new(mu_n.outputs[0], uv.inputs[0])
        L.new(mv_n.outputs[0], uv.inputs[1])
        img = node("ShaderNodeTexImage", extension="CLIP")
        img.image = bpy.data.images.load(meta.get("tex", meta["path"]), check_existing=True)
        L.new(uv.outputs[0], img.inputs[0])
        dot = node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        L.new(geo.outputs["Normal"], dot.inputs[0])
        dot.inputs[1].default_value = toward
        ramp = node("ShaderNodeMapRange")
        L.new(dot.outputs["Value"], ramp.inputs["Value"])
        ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.35, 0.85
        w = node("ShaderNodeMath", operation="MULTIPLY")
        L.new(ramp.outputs["Result"], w.inputs[0])
        L.new(img.outputs["Alpha"], w.inputs[1])
        w2 = node("ShaderNodeMath", operation="MULTIPLY")
        L.new(w.outputs[0], w2.inputs[0])
        w2.inputs[1].default_value = strength
        mix = node("ShaderNodeMix", data_type="RGBA")
        L.new(w2.outputs[0], mix.inputs["Factor"])
        L.new(color, mix.inputs[6])
        L.new(img.outputs["Color"], mix.inputs[7])
        color = mix.outputs[2]
    emit = node("ShaderNodeEmission")
    L.new(color, emit.inputs["Color"])
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    old_surface = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].is_linked else None
    L.new(emit.outputs[0], out.inputs["Surface"])
    w_, h_ = tex.image.size
    baked = bpy.data.images.new(f"{tex.image.name}_refined", w_, h_)
    target = node("ShaderNodeTexImage")
    target.image = baked
    # bake in the same UV map the base colour uses
    if tex.inputs["Vector"].is_linked:
        L.new(tex.inputs["Vector"].links[0].from_socket, target.inputs["Vector"])
    N.active = target
    sc = bpy.context.scene
    prev = sc.render.engine
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.device = "CPU"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    sc.render.bake.margin = 8
    bpy.ops.object.bake(type="EMIT")
    sc.render.engine = prev
    baked.pack()
    # restore the BSDF, now reading the refined texture
    if old_surface:
        L.new(old_surface, out.inputs["Surface"])
    tex.image = baked
    for n in created:
        N.remove(n)
    log(f"texture refined from {', '.join(extra)} ({w_}x{h_}, strength {strength})")
    return True


# ---------------------------------------------------------------- 3. landmarks
def _runs(x, gap, minw):
    """Split sorted 1D coords into runs separated by > gap. Returns [(lo, hi)]."""
    if len(x) == 0:
        return []
    x = np.sort(x)
    cut = np.nonzero(np.diff(x) > gap)[0]
    starts = np.r_[0, cut + 1]
    ends = np.r_[cut, len(x) - 1]
    return [(x[a], x[b]) for a, b in zip(starts, ends) if x[b] - x[a] >= minw]


def _band(V, z, half):
    return V[np.abs(V[:, 2] - z) < half]


def _center(V, P, d, half, radius):
    """Centroid of the verts in a slab across axis d at P, within radius of the axis."""
    rel = V - P
    t = rel @ d
    perp = rel - np.outer(t, d)
    m = (np.abs(t) < half) & (np.linalg.norm(perp, axis=1) < radius)
    if m.sum() < 8:
        return P
    c = V[m].mean(0)
    return P + (c - P) - ((c - P) @ d) * d  # move only across the limb


def landmarks(obj):
    V = verts_np(obj)
    H = V[:, 2].max()
    dz = 0.004 * H
    gap = 0.012 * H
    minw = 0.006 * H
    notes = []

    # crotch: the first height (going up) where material appears on the centre line
    crotch = None
    for z in np.arange(0.12 * H, 0.75 * H, dz):
        b = _band(V, z, dz)
        if (np.abs(b[:, 0]) < 0.012 * H).sum() > 3:
            crotch = z
            break
    if crotch is None or crotch < 0.2 * H:
        notes.append("legs not separated (skirt/robe or legs together): crotch guessed at 0.47 H")
        crotch = 0.47 * H

    # torso half-width per side just above the crotch, below any arms
    def torso_run(z):
        b = _band(V, z, dz)
        rs = _runs(b[:, 0], gap, minw)
        return min(rs, key=lambda r: abs((r[0] + r[1]) / 2)) if rs else (-0.1 * H, 0.1 * H)

    # Scan the upper body. Below the armpit an A-posed arm is its own run beside the torso run;
    # the torso's half-width is measured only there, so arms never count as torso. A T-pose has
    # no such band, so the width comes from the waist up to halfway to the shoulders.
    scan = []
    for z in np.arange(crotch + 0.04 * H, 0.9 * H, dz):
        b = _band(V, z, dz)
        rs = _runs(b[:, 0], gap, minw)
        if not rs:
            continue
        t = min(rs, key=lambda r: abs((r[0] + r[1]) / 2))
        scan.append((z, t, any(r[0] > t[1] for r in rs), any(r[1] < t[0] for r in rs)))
    w, armpit = {}, {}
    for side, s, idx in (("L", 1, 2), ("R", -1, 3)):
        with_arm = [z for z, _, aL, aR in scan if (aL, aR)[idx - 2]]
        armpit[side] = max(with_arm) if len(with_arm) > 3 else None
        # stop well short of the armpit: there the arm-torso gap closes and the runs merge
        top_z = armpit[side] if armpit[side] else 0.8 * H
        z_hi = crotch + 0.7 * (top_z - crotch)
        half = [s * (t[1] if s > 0 else t[0]) for z, t, _, _ in scan if z <= z_hi]
        w[side] = float(np.median(half)) if half else 0.1 * H
    pose = "A" if armpit["L"] and armpit["R"] else "T"
    log(f"pose: {pose}-pose, torso half-width L {w['L'] / H:.3f}H R {w['R'] / H:.3f}H")

    # head top + neck (narrowest torso-centred slice in the upper body)
    top = H
    joints, arm_pts = {}, {}
    for side, s in (("L", 1), ("R", -1)):
        m = (s * V[:, 0] > w[side] * 1.05) & (V[:, 2] > crotch + 0.02 * H) & (V[:, 2] < 0.95 * H)
        P = V[m]
        if len(P) < 50:
            notes.append(f"{side} arm not found clear of the torso; arm joints guessed")
            P = None
        arm_pts[side] = P
    shoulder_z = []
    for side, s in (("L", 1), ("R", -1)):
        P = arm_pts[side]
        if P is None:
            continue
        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c, full_matrices=False)
        d = vt[0] * (1 if vt[0][0] * s > 0 else -1)          # outward
        t = (P - c) @ d
        tip = P[np.argmax(t)]
        # medial axis: centroid + mean radius of slabs across the arm, shoulder -> fingertips
        step = 0.012 * H
        axis = []
        for t0 in np.arange(t.min(), t.max(), step):
            sl = P[(t >= t0) & (t < t0 + step)]
            if len(sl) >= 8:
                m = sl.mean(0)
                axis.append((m, float(np.linalg.norm(sl - m, axis=1).mean())))
        if len(axis) < 6:
            notes.append(f"{side} arm too short to trace; arm joints guessed")
            arm_pts[side] = None
            continue
        pts = np.array([a[0] for a in axis])
        rad = np.array([a[1] for a in axis])
        # shoulder joint: where the medial axis crosses the chest's half-width
        sx = s * pts[:, 0]
        i = int(np.argmax(sx >= w[side])) if (sx >= w[side]).any() else 0
        S = pts[i].copy()
        S[0] = s * w[side]
        pts, rad = np.vstack([S, pts[i:], tip]), np.r_[rad[i], rad[i:], rad[-1]]
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        arc = np.r_[0, np.cumsum(seg)]
        frac = arc / arc[-1]
        # wrist: the narrowest cross-section 62-90% of the way out (the hand widens past it)
        win = (frac > 0.62) & (frac < 0.9)
        wi = int(np.flatnonzero(win)[np.argmin(rad[win])]) if win.any() else int(np.searchsorted(frac, 0.76))
        joints[f"tip.{side}"] = tip
        joints[f"shoulder.{side}"] = S
        joints[f"axis.{side}"] = (pts, frac, wi)
        shoulder_z.append(S[2])
    if not shoulder_z:
        shoulder_z = [0.8 * H]
    sz = float(np.mean(shoulder_z))

    widths = []
    for z in np.arange(sz, sz + 0.6 * (top - sz), dz):
        r = torso_run(z)
        widths.append((r[1] - r[0], z))
    neck = min(widths)[1] if widths else 0.86 * H
    if neck < sz + 0.01 * H:
        neck = sz + 0.04 * H
    nb = _band(V, neck, 2 * dz)
    neck_y = float(np.median(nb[np.abs(nb[:, 0]) < 0.05 * H][:, 1])) if len(nb) else 0.0

    for side, s in (("L", 1), ("R", -1)):
        if f"shoulder.{side}" not in joints:  # fallback proportions
            S = np.array([s * w[side] * 0.9, neck_y, sz])
            joints[f"shoulder.{side}"] = S
            joints[f"tip.{side}"] = S + np.array([s * 0.33 * H, 0, -0.25 * H])
        S, T = joints[f"shoulder.{side}"], joints[f"tip.{side}"]
        S[2] = min(S[2], neck - 0.02 * H)
        ax = joints.pop(f"axis.{side}", None)
        if ax is not None:
            pts, frac, wi = ax
            W = pts[wi].copy()
            # elbow: upper arm : forearm ~ 0.56 : 0.44 of shoulder-to-wrist along the axis
            fe = frac[wi] * 0.56
            E = np.array([np.interp(fe, frac, pts[:, j]) for j in range(3)])
        else:
            E, W = S + (T - S) * 0.42, S + (T - S) * 0.76
        E[1] += 0.012 * H          # elbow slightly back: Rigify needs a bend to aim the IK pole
        joints.update({f"elbow.{side}": E, f"wrist.{side}": W, f"hand_tip.{side}": T})

    # legs
    for side, s in (("L", 1), ("R", -1)):
        # legs live inside the torso's width; A-posed hands hanging past the crotch do not
        inside = (s * V[:, 0] > 0) & (s * V[:, 0] < w[side] * 1.15)
        leg = V[inside & (V[:, 2] < crotch)]
        if len(leg) < 50:
            leg = V[inside & (V[:, 2] < 0.5 * H)]
        top_band = leg[leg[:, 2] > crotch - 0.06 * H]
        hip = top_band.mean(0) if len(top_band) else np.array([s * 0.09 * H, 0, crotch])
        hip[2] = crotch * 1.12     # hip joint sits ~0.06 H above the crotch on an adult
        # ankle: lowest height where the leg's forward extent stops being foot
        shin = leg[(leg[:, 2] > 0.12 * H) & (leg[:, 2] < 0.2 * H)]
        shin_front = shin[:, 1].min() if len(shin) else 0.0
        ankle_z = 0.045 * H
        for z in np.arange(0.01 * H, 0.12 * H, dz):
            b = _band(leg, z, dz)
            if len(b) and b[:, 1].min() > shin_front - 0.025 * H:
                ankle_z = max(z, 0.03 * H)
                break
        ab = _band(leg, ankle_z, 2 * dz)
        ankle = ab.mean(0) if len(ab) else np.array([hip[0], 0, ankle_z])
        foot = leg[leg[:, 2] < ankle_z]
        if len(foot) < 10:
            foot = leg[leg[:, 2] < 0.06 * H]
        toe_tip = foot[np.argmin(foot[:, 1])].copy()
        heel = foot[np.argmax(foot[:, 1])].copy()
        toe_tip[2] = heel[2] = 0.0
        ball = ankle + (toe_tip - ankle) * 0.62
        ball[2] = min(ball[2], 0.25 * ankle_z + 0.005 * H)
        toe_tip[2] = ball[2]
        dleg = (ankle - hip) / np.linalg.norm(ankle - hip)
        knee = _center(leg, (hip + ankle) / 2, dleg, 0.015 * H, 0.08 * H)
        knee[1] -= 0.012 * H       # knee slightly forward for the IK pole
        joints.update({f"hip.{side}": hip, f"knee.{side}": knee, f"ankle.{side}": ankle,
                       f"ball.{side}": ball, f"toe.{side}": toe_tip, f"heel.{side}": heel})

    hips_z = (joints["hip.L"][2] + joints["hip.R"][2]) / 2
    pelvis = np.array([0.0, (joints["hip.L"][1] + joints["hip.R"][1]) / 2, hips_z - 0.04 * H])
    joints.update({"pelvis": pelvis, "neck": np.array([0.0, neck_y, neck]),
                   "chest": np.array([0.0, neck_y, sz - 0.02 * H]), "head_top": np.array([0.0, neck_y, top])})
    for n in notes:
        log("warning:", n)
    log(f"landmarks: crotch {crotch / H:.2f}H, shoulders {sz / H:.2f}H, neck {neck / H:.2f}H, "
        f"arm span {abs(joints['hand_tip.L'][0] - joints['hand_tip.R'][0]) / H:.2f}H")
    return symmetrize({k_: [float(x) for x in v] for k_, v in joints.items()}), notes


# ---------------------------------------------------------------- 4. rig
def build_rig(J, H):
    import addon_utils
    addon_utils.enable("rigify", default_set=True, persistent=False)
    from rigify.metarigs.Basic import basic_human

    data = bpy.data.armatures.new("metarig")
    meta = bpy.data.objects.new("metarig", data)
    bpy.context.scene.collection.objects.link(meta)
    bpy.ops.object.select_all(action="DESELECT")
    meta.select_set(True)
    bpy.context.view_layer.objects.active = meta
    bpy.ops.object.mode_set(mode="EDIT")
    basic_human.create(meta)  # leaves us in edit mode with rigify types assigned
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    zaxis = {b.name: b.z_axis.copy() for b in eb}
    s0 = H / 1.98                                      # metarig is ~1.98 m tall
    v = lambda key: Vector(J[key])

    def put(name, head, tail):
        b = eb[name]
        b.head, b.tail = Vector(head), Vector(tail)
        b.align_roll(zaxis[name])

    # spine chain: pelvis -> chest -> neck -> head top, split like the metarig
    pel, chest, neck, top = v("pelvis"), v("chest"), v("neck"), v("head_top")
    sp = [pel.lerp(chest, f) for f in (0.0, 0.27, 0.52, 0.76)] + [chest]
    put("spine", sp[0], sp[1])
    put("spine.001", sp[1], sp[2])
    put("spine.002", sp[2], sp[3])
    put("spine.003", sp[3], sp[4])
    head_base = neck.lerp(top, 0.1)
    put("spine.004", chest, chest.lerp(head_base, 0.5))
    put("spine.005", chest.lerp(head_base, 0.5), head_base)
    put("spine.006", head_base, top)
    for side, s in (("L", 1), ("R", -1)):
        S, E, W, T = v(f"shoulder.{side}"), v(f"elbow.{side}"), v(f"wrist.{side}"), v(f"hand_tip.{side}")
        clav = Vector((s * 0.01 * H, chest.y - 0.03 * H, chest.z - 0.005 * H))
        put(f"shoulder.{side}", clav, Vector((S.x * 0.92, S.y, S.z + 0.005 * H)))
        put(f"upper_arm.{side}", S, E)
        put(f"forearm.{side}", E, W)
        put(f"hand.{side}", W, W.lerp(T, 0.55))
        hip, kn, an, ball, toe, heel = (v(f"{n}.{side}") for n in ("hip", "knee", "ankle", "ball", "toe", "heel"))
        put(f"thigh.{side}", hip, kn)
        put(f"shin.{side}", kn, an)
        put(f"foot.{side}", an, ball)
        put(f"toe.{side}", ball, toe)
        hw = 0.022 * H
        put(f"heel.02.{side}", Vector((heel.x - s * hw, heel.y, 0)), Vector((heel.x + s * hw, heel.y, 0)))
        put(f"pelvis.{side}", pel, pel + Vector((s * 0.056, -0.05, 0.072)) * s0)
        bz = sp[3].z
        put(f"breast.{side}", Vector((S.x * 0.6, chest.y - 0.01 * H, bz)),
            Vector((S.x * 0.6, chest.y - 0.08 * H, bz)))
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.pose.rigify_generate()
    rig = data.rigify_target_rig or bpy.data.objects.get("rig") or bpy.data.objects.get("RIG-metarig")
    meta.hide_set(True)
    meta.hide_render = True
    log(f"rigify rig: {rig.name}, {sum(b.use_deform for b in rig.data.bones)} deform bones")
    return meta, rig


# ---------------------------------------------------------------- 5. skin
def _select(objs, active):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _unweighted(obj):
    n = 0
    for v in obj.data.vertices:
        if not any(g.weight > 1e-4 for g in v.groups):
            n += 1
    return n / max(1, len(obj.data.vertices))


def distance_weights(obj, rig, power=7.0, keep=3):
    """Weights from each vertex's distance to every deform bone segment: w ~ (d_min / d)^power over
    the `keep` nearest bones, normalised. Needs no closed surface (bone heat does), so it is the
    fallback for open, holey generated meshes; with joints placed well it bends cleanly."""
    bones = [b for b in rig.data.bones if b.use_deform]
    M = rig.matrix_world
    A_ = np.array([tuple(M @ b.head_local) for b in bones])
    B_ = np.array([tuple(M @ b.tail_local) for b in bones])
    V = verts_np(obj)
    V = (np.array(obj.matrix_world) @ np.c_[V, np.ones(len(V))].T).T[:, :3]
    AB = B_ - A_
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    D = np.empty((len(V), len(bones)))
    for j in range(len(bones)):
        t = np.clip(((V - A_[j]) @ AB[j]) / L2[j], 0, 1)
        P = A_[j] + t[:, None] * AB[j]
        D[:, j] = np.linalg.norm(V - P, axis=1)
    D = np.maximum(D, 1e-4)
    idx = np.argsort(D, axis=1)[:, :keep]
    d = np.take_along_axis(D, idx, axis=1)
    w = (d[:, :1] / d) ** power
    w /= w.sum(1, keepdims=True)
    obj.vertex_groups.clear()
    groups = [obj.vertex_groups.new(name=b.name) for b in bones]
    q = np.round(w * 50).astype(int)          # batch vertex_group.add by quantised weight
    for k_ in range(keep):
        for j in range(len(bones)):
            sel = idx[:, k_] == j
            if not sel.any():
                continue
            for lvl in np.unique(q[sel, k_]):
                if lvl <= 0:
                    continue
                verts = np.flatnonzero(sel & (q[:, k_] == lvl)).tolist()
                groups[j].add(verts, lvl / 50.0, "REPLACE")
    log(f"distance weights: {len(bones)} bones, {keep} per vertex")


# Typical radius of each body part as a fraction of height (clothed): the "capsule" around a bone.
# Bones not listed get 0.03 H. Only the ratio between neighbours matters much.
CAPSULE_R = {"hips": 0.085, "spine": 0.085, "chest": 0.09, "neck": 0.035, "head": 0.065,
             "upper_arm": 0.032, "forearm": 0.028, "hand": 0.025,
             "thigh": 0.05, "shin": 0.038, "foot": 0.035}
# Limb -> torso bone that takes over anything hanging far off the limb near its root (bags, belts,
# coat hems): (torso bone, max distance in limb radii, fraction of the limb from its root it applies to)
ACCESSORY = {"thigh": ("hips", 1.45, 0.7), "upper_arm": ("chest", 1.9, 0.35)}


def _bone_key(name):
    return name.split(".")[0]


def mesh_edges(obj):
    e = np.empty(len(obj.data.edges) * 2, dtype=np.int64)
    obj.data.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def capsule_weights(obj, rig, H, blend=0.05, accessories=True, keep=4):
    """Skin weights that need no closed surface (generated meshes are open shells, where bone heat
    fails). 1) every vertex goes to the bone whose capsule (segment + body-part radius) it is
    nearest to, i.e. distance to the segment minus that part's radius, so the torso claims its
    sides and a thin arm doesn't; 2) accessories: anything on a thigh/upper arm but far off its axis
    near the root (a satchel, a strap, a coat hem) goes to the torso instead of swinging with the
    leg; 3) the one-hot weights diffuse ALONG THE MESH SURFACE (graph Laplacian) so joints blend
    over ~`blend` metres, and never jump across a gap the way distance weights do (hand to thigh)."""
    bones = [b for b in rig.data.bones if b.use_deform]
    M = rig.matrix_world
    A_ = np.array([tuple(M @ b.head_local) for b in bones])
    B_ = np.array([tuple(M @ b.tail_local) for b in bones])
    R_ = np.array([CAPSULE_R.get(_bone_key(b.name), 0.03) * H for b in bones])
    V = verts_np(obj)
    V = (np.array(obj.matrix_world) @ np.c_[V, np.ones(len(V))].T).T[:, :3]
    AB = B_ - A_
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    D = np.empty((len(V), len(bones)))
    T = np.empty((len(V), len(bones)))
    for j in range(len(bones)):
        t = np.clip(((V - A_[j]) @ AB[j]) / L2[j], 0, 1)
        T[:, j] = t
        D[:, j] = np.linalg.norm(V - (A_[j] + t[:, None] * AB[j]), axis=1)
    own = np.argmin(D - R_, axis=1)
    names = [b.name for b in bones]
    moved = 0
    if accessories:
        for j, b in enumerate(bones):
            rule = ACCESSORY.get(_bone_key(b.name))
            if not rule or rule[0] not in names:
                continue
            to, k_r, frac = rule
            sel = (own == j) & (D[:, j] > k_r * R_[j]) & (T[:, j] < frac)
            own[sel] = names.index(to)
            moved += int(sel.sum())
    W = np.zeros((len(V), len(bones)))
    W[np.arange(len(V)), own] = 1.0
    # diffusion on the surface graph: each step mixes a vertex with its neighbours' mean
    E = mesh_edges(obj)
    el = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    e_med = float(np.median(el)) if len(el) else 0.005
    iters = int(min(400, max(10, (blend / max(e_med, 1e-4)) ** 2 / 2)))
    src = np.r_[E[:, 0], E[:, 1]]
    dst = np.r_[E[:, 1], E[:, 0]]
    deg = np.maximum(np.bincount(dst, minlength=len(V)), 1)
    for _ in range(iters):
        nb = np.stack([np.bincount(dst, weights=W[src, c], minlength=len(V)) for c in range(len(bones))], 1)
        W = 0.5 * W + 0.5 * nb / deg[:, None]
    # keep the strongest `keep`, drop crumbs, normalise
    if keep < len(bones):
        cut = np.sort(W, axis=1)[:, -keep][:, None]
        W[W < cut] = 0
    W[W < 0.01] = 0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    obj.vertex_groups.clear()
    groups = [obj.vertex_groups.new(name=n) for n in names]
    q = np.round(W * 100).astype(int)
    for j in range(len(bones)):
        col = q[:, j]
        for lvl in np.unique(col[col > 0]):
            groups[j].add(np.flatnonzero(col == lvl).tolist(), lvl / 100.0, "REPLACE")
    log(f"capsule weights: {len(bones)} bones, {moved:,} accessory verts to the torso, "
        f"{iters} diffusion steps (edge {e_med * 1000:.1f} mm, blend {blend * 100:.0f} cm)")


def symmetrize(J, pairs=None):
    """Average every .L/.R joint pair across the body's mid-plane (x = 0): generated meshes and
    straps/bags skew landmark detection, and a lopsided skeleton shifts every mirrored motion."""
    out = {k_: list(v) for k_, v in J.items()}
    for k_ in J:
        if not k_.endswith(".L"):
            continue
        r = k_[:-2] + ".R"
        if r not in J:
            continue
        a, b = J[k_], J[r]
        x = (abs(a[0]) + abs(b[0])) / 2
        y, z = (a[1] + b[1]) / 2, (a[2] + b[2]) / 2
        out[k_] = [x if a[0] >= 0 else -x, y, z]
        out[r] = [-out[k_][0], y, z]
    return out


def _bind(obj, rig, preserve_volume=True):
    for m in [m for m in obj.modifiers if m.type == "ARMATURE"]:
        obj.modifiers.remove(m)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    # dual-quaternion skinning: bent elbows/knees keep their volume instead of collapsing
    mod.use_deform_preserve_volume = preserve_volume
    mw = obj.matrix_world.copy()
    obj.parent = rig
    obj.matrix_parent_inverse = rig.matrix_world.inverted()
    obj.matrix_world = mw


def skin(obj, rig, H, mode="auto", voxel=0.006):
    """mode: auto (bone heat on a voxel proxy, falling back to capsule weights when it fails, as it
    does on open meshes) | capsule | proxy | direct (bone heat on the real mesh) | distance."""
    if mode == "capsule":
        capsule_weights(obj, rig, H)
        _bind(obj, rig)
        return
    if mode == "distance":
        distance_weights(obj, rig)
        _bind(obj, rig)
        return
    if mode == "direct":
        _select([obj, rig], rig)
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        miss = _unweighted(obj)
        log(f"direct weights: {miss:.1%} of verts unweighted")
        if miss < 0.01:
            return
        log("falling back to capsule weights")
        obj.parent = None
        capsule_weights(obj, rig, H)
        _bind(obj, rig)
        return
    proxy = obj.copy()
    proxy.data = obj.data.copy()
    proxy.name = "WeightProxy"
    bpy.context.scene.collection.objects.link(proxy)
    rm = proxy.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel * H
    _select([proxy], proxy)
    bpy.ops.object.modifier_apply(modifier=rm.name)
    log(f"proxy: {len(proxy.data.polygons):,} faces (voxel {voxel * H * 100:.1f} cm)")
    _select([proxy, rig], rig)
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    miss = _unweighted(proxy)
    if miss > 0.02:
        log(f"bone heat left {miss:.1%} of proxy verts unweighted (open mesh?)")
    if miss > 0.2 and mode == "auto":
        bpy.data.objects.remove(proxy)
        log("using capsule weights instead")
        capsule_weights(obj, rig, H)
        _bind(obj, rig)
        return
    obj.vertex_groups.clear()
    for g in proxy.vertex_groups:
        obj.vertex_groups.new(name=g.name)
    dt = obj.modifiers.new("weights", "DATA_TRANSFER")
    dt.object = proxy
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    _select([obj], obj)
    bpy.ops.object.modifier_apply(modifier=dt.name)
    bpy.data.objects.remove(proxy)
    _bind(obj, rig)
    log(f"proxy weights transferred: {_unweighted(obj):.1%} of verts unweighted")


# ---------------------------------------------------------------- 6. check renders
def _rotate_world(rig, bone, axis, deg):
    pb = rig.pose.bones.get(bone)
    if pb is None:
        return False
    head = pb.head.copy()
    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
    pb.matrix = R @ pb.matrix
    bpy.context.view_layer.update()
    return True


def test_pose(rig):
    for p in ("upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"):
        pb = rig.pose.bones.get(p)
        if pb is not None and "IK_FK" in pb:
            pb["IK_FK"] = 1.0                       # FK
    bpy.context.view_layer.update()
    before = rig.pose.bones["DEF-upper_arm.L"].matrix.copy()
    _rotate_world(rig, "upper_arm_fk.L", "Y", -55)
    _rotate_world(rig, "forearm_fk.L", "Z", 35)
    _rotate_world(rig, "upper_arm_fk.R", "Y", 25)
    _rotate_world(rig, "thigh_fk.L", "X", -45)
    _rotate_world(rig, "shin_fk.L", "X", 60)
    _rotate_world(rig, "spine_fk.002", "Z", 12) or _rotate_world(rig, "chest", "Z", 12)
    moved = (rig.pose.bones["DEF-upper_arm.L"].matrix.translation - before.translation).length > 0 or \
        rig.pose.bones["DEF-upper_arm.L"].matrix.to_quaternion().rotation_difference(before.to_quaternion()).angle > 0.1
    log("test pose applied" if moved else "warning: test pose did not move the deform bones")


def render_checks(obj, out):
    base, ext = os.path.splitext(out)
    sc = bpy.context.scene
    k.render_settings(res=(1080, 1350))
    k.world("#202226", 0.6)
    drop = k.backdrop("#d9d5ce")
    k.studio_lights(target=obj, key=0.8)
    k.light("AREA", (0, 4, 3), obj, 300, size=3, name="BackFill")
    shots = [("front", (0.0, -1, 0.25)), ("back", (0.0, 1, 0.25)), ("three_quarter", (0.7, -0.75, 0.3))]
    paths = []
    for name, (x, y, z) in shots:
        cam = k.camera(loc=(x * 8, y * 8, 1 + z * 8), look_at=obj, lens=70, fit=[obj], margin=1.12,
                       name=f"cam_{name}")
        sc.camera = cam
        drop.hide_render = name == "back"   # the sweep's wall stands between a rear camera and the character
        p = f"{base}_{name}{ext or '.png'}"
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    return paths


def render_bones(obj, rig, out):
    """Front view with the mesh ghosted and every deform bone drawn as an orange stick, to
    check joint placement (elbows/knees/wrists inside the limbs, at the bends)."""
    H = obj.dimensions.z
    ghost = k.material("#9fb4c8", roughness=0.6)
    bsdf = ghost.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Alpha"].default_value = 0.3
    saved = list(obj.data.materials)
    obj.data.materials.clear()
    obj.data.materials.append(ghost)
    stick_mat = k.emissive("#ff7a1a", 4.0)
    sticks = []
    for b in rig.data.bones:
        if not b.use_deform:
            continue
        a = rig.matrix_world @ b.head_local
        t = rig.matrix_world @ b.tail_local
        d = t - a
        if d.length < 1e-4:
            continue
        c = k.cylinder(radius=0.006 * H, depth=d.length, loc=(a + t) / 2, mat=stick_mat)
        c.rotation_mode = "QUATERNION"
        c.rotation_quaternion = d.to_track_quat("Z", "Y")
        sticks += [c, k.sphere(radius=0.011 * H, loc=a, mat=stick_mat, segments=12, rings=6)]
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["cam_front"]
    base, ext = os.path.splitext(out)
    p = f"{base}_bones{ext or '.png'}"
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    for o in sticks:
        bpy.data.objects.remove(o)
    obj.data.materials.clear()
    for m in saved:
        obj.data.materials.append(m)
    return p


# ---------------------------------------------------------------- main
def main():
    mesh = A("mesh")
    if not mesh:
        raise SystemExit("--mesh raw.glb is required")
    height = float(A("height", 1.8))
    views = {}
    if A("views") and os.path.exists(A("views")):
        with open(A("views")) as f:
            views = json.load(f)
    k.reset()
    obj = import_mesh(os.path.abspath(mesh))
    clean(obj)
    if A("up", "auto") == "auto":
        stand_up(obj, views.get("front", {}).get("aspect"))
    orient(obj, A("facing", "auto"), views.get("front", {}).get("aspect"))
    normalize(obj, height)
    fill_small_holes(obj)
    J, notes = landmarks(obj)
    normals_outward(obj, J)
    k.shade_smooth(obj)
    tmode = A("texture", "auto")
    if tmode == "auto":
        # TRELLIS.2's CPU fallback baker shatters the UV atlas into sub-pixel islands (speckle);
        # the views make a better texture then
        meta_path = os.path.splitext(os.path.abspath(mesh))[0] + ".json"
        backend = json.load(open(meta_path)).get("bake_backend") if os.path.exists(meta_path) else None
        tmode = "views" if backend == "kdtree" and "front" in views else "mesh"
    if tmode == "views":
        texture_from_views(obj, views, int(A("texsize", 2048)))
    else:
        refine_texture(obj, views, float(A("project", 0.85)))
    outdir = os.path.dirname(os.path.abspath(A("blend") or A("out") or mesh))
    with open(os.path.join(outdir, "landmarks.json"), "w") as f:
        json.dump({"height": height, "joints": J, "notes": notes}, f, indent=2)
    meta, rig = build_rig(J, height)
    skin(obj, rig, height, A("weights", "auto"), float(A("voxel", 0.006)))
    # reference image plane behind the character, hidden from renders
    if "front" in views:
        img = bpy.data.images.load(views["front"]["path"])
        plane = k.plane(size=height * 1.15, loc=(0, 0.6, height * 0.55), rot=(90, 0, 0), name="FrontRef")
        m = bpy.data.materials.new("FrontRef")
        m.use_nodes = True
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = img
        m.node_tree.links.new(t.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        plane.data.materials.append(m)
        plane.hide_render = True
        plane.hide_set(True)
    if A("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(A("blend")), check_existing=False)
        log(f"blend: {A('blend')}")
    if A("glb"):
        _select([obj, rig], rig)
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(A("glb")), export_format="GLB",
                                  use_selection=True, export_def_bones=True, export_apply=False)
        log(f"glb: {A('glb')}")
    if not A("no-render") and A("out"):
        rest = render_checks(obj, A("out"))
        rest.append(render_bones(obj, rig, A("out")))
        test_pose(rig)
        base, ext = os.path.splitext(A("out"))
        p = f"{base}_pose{ext or '.png'}"
        bpy.context.scene.camera = bpy.data.objects["cam_three_quarter"]
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        for x in rest + [p]:
            log(f"check: {x}")


if __name__ == "__main__":
    main()
