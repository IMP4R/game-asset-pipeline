#!/usr/bin/env python3
"""Paint Loop — финальная сборка ассета: геометрия + toon-материалы + обводка + GLB.

Раннер pipeline3d (generate_blender.py) даёт детерминированную геометрию и рендер
для критика, но его материал — это Emission с градиентом по Z: плоский обод и
верх стенки получают один цвет, и toon-обводка идёт через Freestyle. Здесь тот же
ассет собирается для поставки: освещённый cel-шейдинг (Diffuse -> Shader to RGB ->
ColorRamp), чёрная обводка отдельной геометрией inverted-hull (переносится в Godot
как меш, без шейдера), оба состояния и экспорт GLB.

Запуск:
  blender --background --python present_bucket.py -- --out <dir>
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- геометрия
# Все размеры — из замеренного референса (см. runs/.../spec.json):
#   радиус обода 0.25, низ 0.2025, высота тела 0.348, отверстие 0.18,
#   дно полости 0.145 на z=0.216, купол краски до z=0.48, ремень-дуга на z=0.21.
H_BODY = 0.348
R_TOP = 0.25
R_BOT = 0.2025
R_HOLE = 0.18
R_FLOOR = 0.145
Z_FLOOR = 0.216
DOME_APEX = 0.478
DOME_R = 0.255
DOME_R_Z = 0.385
BAIL_R = 0.251
BAIL_Z = 0.21
BAIL_SECTION = (0.045, 0.062)
SEG = 32

# Палитра замерена пикселями референса (ref_open_crop.png / ref_closed_crop.png).
PAL = {
    "body": ("#C03A00", "#E46000", "#F46A00"),   # тень, тон, свет
    "rim": ("#E07200", "#F8950A", "#FFB000"),    # обод в рефе заметно желтее стенки
    "cavity": ("#B03400", "#DC4906", "#F4801A"),
    "handle": ("#2E2E36", "#3A3A42", "#4C4C57"),
    "outline": "#000000",
    "bg": "#D8D8E4",
}


def srgb(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return out


def lathe(profile, seg=SEG, name="lathe", smooth=True, inner_from=None):
    """Профиль [(r, z), ...] снизу вверх -> тело вращения. r=0 замыкает ось.

    inner_from — индекс точки профиля, начиная с которой грани относятся к
    полости (внутренняя стенка и дно). Признак задаётся по профилю, а не по
    нормали: у дна полости нормаль смотрит вверх, и проверка по радиусу
    заливала его материалом стенки.
    """
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append(("cap", bm.verts.new((0, 0, z))))
            continue
        rings.append(("ring", [bm.verts.new((r * math.cos(2 * math.pi * j / seg),
                                              r * math.sin(2 * math.pi * j / seg), z))
                               for j in range(seg)]))
    first_face = len(bm.faces)
    marks = []
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        marks.append(len(bm.faces))
        if a[0] == "cap" and b[0] == "ring":
            for j in range(seg):
                bm.faces.new((a[1], b[1][j], b[1][(j + 1) % seg]))
        elif a[0] == "ring" and b[0] == "cap":
            for j in range(seg):
                bm.faces.new((a[1][j], a[1][(j + 1) % seg], b[1]))
        elif a[0] == "ring" and b[0] == "ring":
            for j in range(seg):
                bm.faces.new((a[1][j], a[1][(j + 1) % seg], b[1][(j + 1) % seg], b[1][j]))
    if rings[0][0] == "cap" and rings[-1][0] == "cap":
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if inner_from is not None:
        for i, p in enumerate(me.polygons):
            p.material_index = 1 if i >= marks[inner_from] else 0
    return me


PAINT_PROFILE = [(R_HOLE, 0.338), (0.222, 0.358), (0.250, 0.378), (0.238, 0.412),
                 (0.196, 0.432), (0.140, 0.450), (0.082, 0.464), (0.030, 0.4745),
                 (0.0, 0.478)]


def body_profile(with_dome):
    """Замкнутое сечение ведра: дно -> наружная стенка -> обод -> полость -> дно полости."""
    pts = [(0.0, 0.0), (R_BOT, 0.0), (R_BOT + (R_TOP - R_BOT) * 0.33, H_BODY * 0.33),
           (R_TOP, H_BODY)]
    if with_dome:
        # купол краски: от обода вверх, перекрывая зев
        # купол в рефе сужается быстрее: к вершине уже 0.45 радиуса, поэтому
        # силуэт читается яйцом, а не шаром
        pts += [(R_TOP * 1.004, H_BODY + 0.012), (DOME_R, DOME_R_Z), (0.238, 0.412),
                (0.196, 0.432), (0.140, 0.450), (0.082, 0.464), (0.030, 0.4745),
                (0.0, DOME_APEX)]
    else:
        pts += [(R_HOLE, H_BODY), (R_FLOOR, Z_FLOOR), (0.0, Z_FLOOR)]
    return pts


def bail_mesh(name="Bucket_Handle", r=BAIL_R, z=BAIL_Z, section=BAIL_SECTION, sweep=180.0):
    """Дуга rings+bridge по ближней половине (полный тор — баг: его дальняя дуга
    всегда торчит над силуэтом, чего в игре нет)."""
    w, h = section
    cw, ch = w * 0.34, h * 0.34
    sec = [(r - w / 2, -h / 2 + ch), (r - w / 2, h / 2 - ch), (r - w / 2 + cw, h / 2),
           (r + w / 2 - cw, h / 2), (r + w / 2, h / 2 - ch), (r + w / 2, -h / 2 + ch),
           (r + w / 2 - cw, -h / 2), (r - w / 2 + cw, -h / 2)]
    bm = bmesh.new()
    rings, steps = [], 24
    a0 = math.radians(-sweep / 2)
    for i in range(steps + 1):
        a = a0 + math.radians(sweep) * i / steps
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((rr * ca, rr * sa, zz + z)) for rr, zz in sec])
    n = len(sec)
    for i in range(steps):
        A, B = rings[i], rings[i + 1]
        for j in range(n):
            bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j]))
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(tuple(sum(v.co[k] for v in ring) / n for k in range(3)))
        for j in range(n):
            bm.faces.new((c, ring[j], ring[(j + 1) % n]) if flip
                         else (c, ring[(j + 1) % n], ring[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def outline_mesh(src_bodies, name="Bucket_Outline", offset=0.030, outer_only=True):
    """Inverted hull: каждая вершина сдвинута наружу по своей нормали.

    outer_only — в обводку идут только грани материала 0 (наружная кожа).
    Полость в контур не входит: её нормали смотрят на ось, сдвиг выносил бы их
    внутрь полости, и чёрная дуга проступала бы сквозь дно (видно на первой
    сборке.present).
    """
    bm = bmesh.new()
    for me in src_bodies:
        keep = [p.index for p in me.polygons if (p.material_index == 0 or not outer_only)]
        if not keep:
            keep = list(range(len(me.polygons)))
        vmap = {}
        for fi in keep:
            remap = []
            for vi in me.polygons[fi].vertices:
                bv = vmap.get(vi)
                if bv is None:
                    bv = bm.verts.new(me.vertices[vi].co)
                    vmap[vi] = bv
                remap.append(bv)
            bm.faces.new(remap)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for v in bm.verts:
        v.co += v.normal * offset
    # Винтовка разворачивается ПОСЛЕ нормализации: при backface culling ближние
    # грани становятся back-facing и отсекаются, остаются дальние — они и дают
    # контур шириной offset. recalc_face_normals после разворота вернул бы их
    # наружу и закрыл бы объект чёрным пятном.
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for p in out.polygons:
        p.use_smooth = False
    return out


# --------------------------------------------------------------- материалы
def toon_material(name, dark, mid, light, pos=(0.10, 0.24)):
    """Cel-шейдинг: Diffuse -> Shader to RGB -> ColorRamp(3 ступени) -> выход."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    e = ramp.color_ramp.elements
    while len(e) > 1:
        e.remove(e[-1])
    e[0].position = 0.0
    e[0].color = (*srgb(dark), 1)
    for p, c in zip(pos, (mid, light)):
        el = e.new(p)
        el.color = (*srgb(c), 1)
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Strength"].default_value = 1.0
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emi.inputs["Color"])
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    return m


def flat_material(name, hexcol, cull=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (*srgb(hexcol), 1)
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = cull
    return m


# ------------------------------------------------------------------- сборка
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for mt in list(bpy.data.materials):
        bpy.data.materials.remove(mt)


def build_state(with_dome, with_outline, with_bail):
    clear_scene()
    S = bpy.context.scene
    inner_from = 4 if not with_dome else None
    body_me = lathe(body_profile(with_dome), name="Bucket_Body", inner_from=inner_from)
    body = bpy.data.objects.new("Bucket_Body", body_me)
    S.collection.objects.link(body)
    body.data.materials.append(toon_material("M_Body", *PAL["body"]))
    body.data.materials.append(toon_material("M_Cavity", *PAL["cavity"], pos=(0.19, 0.30)))
    body.data.materials.append(toon_material("M_Rim", *PAL["rim"], pos=(0.10, 0.24)))

    # обод — плоское кольцо: сглаживание с внутренней стенкой уводит его тон
    for p in body_me.polygons:
        c = p.center
        r = math.hypot(c.x, c.y)
        if R_HOLE * 0.98 < r < R_TOP * 1.02 and abs(c.z - H_BODY) < 1e-4:
            p.use_smooth = False
            p.material_index = 2
    parts = [body]
    if with_bail:
        hb = bpy.data.objects.new("Bucket_Handle", bail_mesh())
        S.collection.objects.link(hb)
        hb.data.materials.append(toon_material("M_Handle", *PAL["handle"]))
        parts.append(hb)
    if with_outline:
        ol = bpy.data.objects.new("Bucket_Outline", outline_mesh([body_me] + ([hb.data] if with_bail else [])))
        S.collection.objects.link(ol)
        ol.data.materials.append(flat_material("M_Outline", PAL["outline"], cull=True))
        parts.append(ol)
    return S, parts


def setup_world_and_light(S, elev=55.0, azim=16.0):
    wld = bpy.data.worlds.new("W")
    S.world = wld
    wld.use_nodes = True
    nt = wld.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")
    lit = nt.nodes.new("ShaderNodeBackground")      # для освещения — чёрный,
    lit.inputs[0].default_value = (0, 0, 0, 1)      # иначе светлая доска даёт
    seen = nt.nodes.new("ShaderNodeBackground")     #ambient и вся модель уходит
    seen.inputs[0].default_value = (*srgb(PAL["bg"]), 1)   # в верхний стоп рампы
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(lit.outputs[0], mix.inputs[1])
    nt.links.new(seen.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    key = bpy.data.lights.new("key", "SUN")
    key.energy = 1.0
    key.angle = math.radians(18)
    ko = bpy.data.objects.new("key", key)
    S.collection.objects.link(ko)
    th, ph = math.radians(elev), math.radians(azim)
    d = Vector((math.cos(th) * math.cos(ph), math.cos(th) * math.sin(ph), math.sin(th)))
    ko.location = d * 6
    ko.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("fill", "SUN")
    fill.energy = 0.22
    fo = bpy.data.objects.new("fill", fill)
    S.collection.objects.link(fo)
    fd = Vector((math.cos(math.radians(40)) * math.cos(math.radians(150)),
                 math.cos(math.radians(40)) * math.sin(math.radians(150)), math.sin(math.radians(40))))
    fo.location = fd * 6
    fo.rotation_euler = (-fd).to_track_quat("-Z", "Y").to_euler()


def place_camera(S, elev, dist, target_z, lens, res):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.data.lens = lens
    th = math.radians(elev)
    cam.location = (dist * math.cos(th), 0, target_z + dist * math.sin(th))
    d = Vector((0, 0, target_z)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    S.render.resolution_x = S.render.resolution_y = res


def render(S, path):
    S.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def export_glb(parts, path, root_name="Bucket"):
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH")
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                              use_selection=True, export_apply=True,
                              export_yup=True, export_materials="EXPORT")
    return path


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--out") + 1] if "--out" in argv else "/tmp/bucket_present"
    os.makedirs(out, exist_ok=True)
    S = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            S.render.engine = eng
            break
        except TypeError:
            continue
    S.render.film_transparent = False
    S.view_settings.view_transform = "Standard"
    S.view_settings.look = "None"
    if hasattr(S, "eevee"):
        S.eevee.taa_render_samples = 96

    report = {}
    # --- состояние OPEN: тело с полостью + чёрная обводка, без ремня
    S, parts = build_state(with_dome=False, with_outline=True, with_bail=False)
    setup_world_and_light(S)
    place_camera(S, 67.0, 12.0, H_BODY / 2, 607, 1024)
    report["open"] = {
        "render": render(S, os.path.join(out, "bucket_open.png")),
        "glb": export_glb(parts, os.path.join(out, "bucket_open.glb")),
        "tris": sum(len(p.data.polygons) for p in parts if p.type == "MESH"),
    }
    # --- состояние CLOSED: купол краски + ремень-дуга, без обводки
    S, parts = build_state(with_dome=True, with_outline=False, with_bail=True)
    setup_world_and_light(S)
    place_camera(S, 67.0, 12.0, DOME_APEX / 2, 610, 1024)
    report["closed"] = {
        "render": render(S, os.path.join(out, "bucket_closed.png")),
        "glb": export_glb(parts, os.path.join(out, "bucket_closed.glb")),
        "tris": sum(len(p.data.polygons) for p in parts if p.type == "MESH"),
    }
    # --- оба состояния одной моделью: корпус + переключаемая краска + ремень + обводка
    S, parts = build_state(with_dome=False, with_outline=True, with_bail=True)
    paint = bpy.data.objects.new("Bucket_Paint", lathe(PAINT_PROFILE, name="Bucket_Paint"))
    S.collection.objects.link(paint)
    paint.data.materials.append(toon_material("M_Paint", *PAL["body"], pos=(0.10, 0.24)))
    paint.location.z = 0.0
    parts_all = [parts[0], paint] + parts[1:]
    setup_world_and_light(S)
    place_camera(S, 67.0, 12.0, DOME_APEX / 2, 610, 1024)
    report["both"] = {"glb": export_glb(parts_all, os.path.join(out, "bucket_both.glb")),
                      "tris": sum(len(p.data.polygons) for p in parts_all if p.type == "MESH")}
    # превью полного состояния из этой же сборки
    S, parts = build_state(with_dome=True, with_outline=False, with_bail=True)
    setup_world_and_light(S)
    place_camera(S, 67.0, 12.0, DOME_APEX / 2, 610, 1024)
    report["closed"] = {
        "render": render(S, os.path.join(out, "bucket_closed.png")),
        "glb": export_glb(parts, os.path.join(out, "bucket_closed.glb")),
        "tris": sum(len(p.data.polygons) for p in parts if p.type == "MESH"),
    }
    # --- контрольный ракурс сбоку- сверху для проверки геометрии
    S, parts = build_state(with_dome=True, with_outline=False, with_bail=True)
    setup_world_and_light(S)
    place_camera(S, 32.0, 12.0, DOME_APEX / 2, 610, 1024)
    report["closed_side"] = {"render": render(S, os.path.join(out, "bucket_closed_side.png"))}

    json.dump(report, open(os.path.join(out, "present_report.json"), "w"), indent=2, ensure_ascii=False)
    print("PRESENT", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
