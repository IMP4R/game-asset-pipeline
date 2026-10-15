# Детерминированный генератор: Asset Spec v2 -> геометрия + рендер (узлы N5–N7).
# LLM не касается координат: все числа выводятся из спеки. Повторный запуск = байт в байт.
#
# Запуск:
#   blender --background --python generate_blender.py -- specs/bucket_paintloop.json \
#           --out /Users/user0/godot-hybrid-casual/assets/pipeline3d/bucket_paintloop
#
# Конвенции clay_lib (pipeline3d.md §5): azimuth от +X, RGB материалов 0–1 (sRGB->linear 2.2),
# дуги = rings+bridge, полный тор в теле = баг.

import json, math, os, sys

import bpy, bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def srgb(c):
    return tuple(v ** 2.2 if v > 0.04045 else v / 12.92 for v in c)


def hex1(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def interp(t, knots):
    ts = [k[0] for k in knots]
    if t <= ts[0]:
        return knots[0][1]
    if t >= ts[-1]:
        return knots[-1][1]
    for (t0, r0), (t1, r1) in zip(knots, knots[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return r0 + (r1 - r0) * u
    return knots[-1][1]


def setup_scene(spec, style):
    S = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            S.render.engine = eng
            break
        except TypeError:
            continue
    res = spec.get("camera", {}).get("resolution", 512)
    S.render.resolution_x = S.render.resolution_y = res
    if hasattr(S, "eevee"):
        S.eevee.taa_render_samples = int(os.environ.get("SAMPLES", "32"))
    outline_px = float(spec.get("style_refs", {}).get("outline_px", os.environ.get("OUTLINE_PX", "5")))
    if outline_px <= 0:  # состояние без toon-обводки (полное ведро в игре)
        S.render.use_freestyle = False
        print("freestyle выключен: outline_px=0 (в этом состоянии обводки нет)")
    try:  # обводка как в рефе (N6-lite)
        S.render.use_freestyle = S.render.use_freestyle
        vl = bpy.context.view_layer
        vl.use_freestyle = outline_px > 0
        if outline_px <= 0:
            raise StopIteration
        if vl.freestyle_settings.linesets:
            ls = vl.freestyle_settings.linesets[0]
            ls.linestyle.thickness = outline_px
            oh = spec.get("style_refs", {}).get("outline_hex", "#050507")
            ls.linestyle.color = tuple(int(oh.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
            # toon-обводка игры рисуется ТОЛЬКО по внешнему силуэту: внутренние
            # рёбра (обод, пол полости) в игре чёрной линией не обведены.
            # select_silhouette ловит и внутренние силуэтные рёбра, поэтому берём
            # внешний контур и гасим всё остальное.
            ls.select_external_contour = True
            ls.select_silhouette = False
            ls.select_border = False
            ls.select_crease = False
            ls.select_contour = False
            ls.select_edge_mark = False
            ls.select_material_boundary = False
            ls.select_ridge_valley = False
            ls.select_suggestive_contour = False
    except Exception as e:
        print("freestyle недоступен:", e)
    S.view_settings.view_transform = style["render_conventions"]["view_transform"]
    S.view_settings.look = style["render_conventions"]["look"]
    rc = style["render_conventions"]
    wh = spec.get("style_refs", {}).get("world_hex")
    w = (lambda h: [int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)])(wh) if wh \
        else list(rc.get("world_rgb_0_255", [16, 16, 32]))
    wld = bpy.data.worlds.new("W")
    S.world = wld
    wld.use_nodes = True
    wld.node_tree.nodes["Background"].inputs[0].default_value = (*srgb((w[0] / 255, w[1] / 255, w[2] / 255)), 1)
    return S


def make_material(name, props, grad_h):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[1].default_value = 1.0
    stops = props.get("gradient_stops")
    if stops:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.0
        mr.clamp = True
        mr.inputs["From Max"].default_value = float(grad_h)
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "LINEAR"
        while len(ramp.color_ramp.elements) < len(stops):
            ramp.color_ramp.elements.new(0.5)
        for e, st in zip(ramp.color_ramp.elements, stops):
            e.position = st["pos"]
            e.color = (*srgb(hex1(st["hex"])), 1)
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], mr.inputs[0])
        nt.links.new(mr.outputs[0], ramp.inputs[0])
        nt.links.new(ramp.outputs["Color"], em.inputs[0])
    else:
        em.inputs[0].default_value = (*srgb(hex1(props["hex"])), 1)
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def build_lathe_shell(bm, unit, dims):
    b = unit["build"]
    H, R = dims["H"], dims["R_top"]
    seg = b["segments"]
    wall = b["wall"] * R
    nrings = max(len(b["profile_knots"]) * 3, 24)
    rings = []
    for i in range(nrings + 1):
        t = i / nrings
        r = interp(t, b["profile_knots"]) * R
        z = t * H
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * j / seg),
                                    r * math.sin(2 * math.pi * j / seg), z)) for j in range(seg)])
    for i in range(nrings):
        for j in range(seg):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % seg],
                          rings[i + 1][(j + 1) % seg], rings[i + 1][j]))
    # донный веер, если профиль не сходится к оси
    r0 = interp(0.0, b["profile_knots"]) * R
    if r0 > 0.01:
        tip = bm.verts.new((0, 0, 0))
        for j in range(seg):
            bm.faces.new((rings[0][j], rings[0][(j + 1) % seg], tip))
    # внутренняя полость + дно (открытый зев)
    if b.get("open_top", True):
        floor_t = float(os.environ.get("FLOOR_T", "0.55"))
        inner = []
        steps = 8
        for i in range(steps + 1):
            t = 1.0 - i / steps * (1.0 - floor_t)
            r = max(interp(t, b["profile_knots"]) * R - wall, 0.02)
            z = t * H
            inner.append([bm.verts.new((r * math.cos(2 * math.pi * j / seg),
                                        r * math.sin(2 * math.pi * j / seg), z)) for j in range(seg)])
        for i in range(steps):
            for j in range(seg):
                bm.faces.new((inner[i][j], inner[i][(j + 1) % seg],
                              inner[i + 1][(j + 1) % seg], inner[i + 1][j]))
        fr = max(interp(floor_t, b["profile_knots"]) * R - wall, 0.02)
        fz = floor_t * H
        ctr = bm.verts.new((0, 0, fz))
        for j in range(seg):
            bm.faces.new((inner[-1][j], ctr, inner[-1][(j + 1) % seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def build_lathe_path(bm, unit, dims):
    b = unit["build"]
    H, R, seg = dims["H"], dims["R_top"], b["segments"]
    src = list(b["path"])  # z-доли абсолютны относительно H; нормализация ломает ленты (пояс/обод)
    pts = []
    for (z0, r0), (z1, r1) in zip(src, src[1:]):  # 4x сглаживание сегментов против crease-линий
        for k in range(4):
            u0, u1 = k / 4, (k + 1) / 4
            pts.append((z0 + (z1 - z0) * u0, r0 + (r1 - r0) * u0))
    pts.append(src[-1])
    rings = []
    for zf, rf in pts:
        z, r = zf * H, rf * R
        rings.append(([bm.verts.new((r * math.cos(2 * math.pi * j / seg),
                                     r * math.sin(2 * math.pi * j / seg), z)) for j in range(seg)], r))
    def ring_ring(A, B):
        for j in range(seg):
            bm.faces.new((A[0][j], A[0][(j + 1) % seg], B[0][(j + 1) % seg], B[0][j]))
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        ra, rb = A[1], B[1]
        if ra <= 1e-4 and rb <= 1e-4:
            continue
        if ra <= 1e-4:
            c = bm.verts.new((0, 0, A[0][0].co.z))
            for j in range(seg):
                bm.faces.new((c, B[0][(j + 1) % seg], B[0][j]))
        elif rb <= 1e-4:
            c = bm.verts.new((0, 0, B[0][0].co.z))
            for j in range(seg):
                bm.faces.new((A[0][j], A[0][(j + 1) % seg], c))
        else:
            ring_ring(A, B)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # раздельные материалы: внутренняя полость темнее (нормаль смотрит на ось)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        c = f.calc_center_median()
        radial = __import__("mathutils").Vector((c.x, c.y, 0))
        d = f.normal.dot(radial.normalized()) if radial.length > 1e-6 else 0.0
        f.material_index = 1 if d < -0.35 else 0


def build_arc_bridge(bm, unit, dims):
    """Дуга rings+bridge (style_constants.modeling_conventions.arcs).

    Частичная дуга вокруг оси Z: сечение [w,h] — скруглённый прямоугольник в
    плоскости (радиус, z), swept на sweep_deg. Полный тор = баг: кольцо шире тела
    всегда показывает свою дальнюю дугу над силуэтом, а в игре её нет.
    """
    b = unit["build"]
    R = b["radius"]
    w, h = b["section"]
    sweep = math.radians(float(b.get("sweep_deg", 180)))
    start = -sweep / 2.0                      # дуга симметрична относительно +X
    cw, ch = w * 0.34, h * 0.34              # фаски сечения
    sec = [(R - w / 2, -h / 2 + ch), (R - w / 2, h / 2 - ch), (R - w / 2 + cw, h / 2),
           (R + w / 2 - cw, h / 2), (R + w / 2, h / 2 - ch), (R + w / 2, -h / 2 + ch),
           (R + w / 2 - cw, -h / 2), (R - w / 2 + cw, -h / 2)]
    rings, steps = [], max(int(sweep / math.radians(10)), 6)
    for i in range(steps + 1):
        a = start + sweep * i / steps
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((r * ca, r * sa, z)) for r, z in sec])
    n = len(sec)
    for i in range(steps):
        A, B = rings[i], rings[i + 1]
        for j in range(n):
            bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j]))
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(tuple(sum(v.co[k] for v in ring) / n for k in range(3)))
        for j in range(n):
            f = (c, ring[j], ring[(j + 1) % n]) if flip else (c, ring[(j + 1) % n], ring[j])
            bm.faces.new(f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def build_box(bm, unit, dims):
    b = unit["build"]
    s = b["size"]
    sx, sy, sz = (s * k for k in b["scale"])
    ox, oy, oz = b.get("offset", [0, 0, 0])
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * sx + ox, v.co.y * sy + oy, v.co.z * sz + oz + s * 0.5)


def build_unit(S, unit, dims):
    mesh = bpy.data.meshes.new(unit["id"])
    bm = bmesh.new()
    if unit["build"]["prim"] == "lathe_shell":
        build_lathe_shell(bm, unit, dims)
    elif unit["build"]["prim"] == "lathe_path":
        build_lathe_path(bm, unit, dims)
    elif unit["build"]["prim"] == "arc_bridge":
        build_arc_bridge(bm, unit, dims)
    elif unit["build"]["prim"] == "box":
        build_box(bm, unit, dims)
    else:
        raise ValueError(f"примитив {unit['build']['prim']} не реализован раннером")
    if "origin" in unit["build"]:
        ox, oy, oz = unit["build"]["origin"]
        bmesh.ops.translate(bm, vec=(ox, oy, oz), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(unit["id"], mesh)
    S.collection.objects.link(ob)
    props = SPEC["properties"][unit["id"]]
    ob.data.materials.append(make_material(unit["id"], props, SPEC["dimensions"]["H"]))
    if "inner_hex" in props or "inner_gradient_stops" in props:
        ip = dict(props)
        ip["hex"] = ip.get("inner_hex", props["hex"])
        ip["gradient_stops"] = ip.get("inner_gradient_stops", ip.get("gradient_stops"))
        ob.data.materials.append(make_material(unit["id"] + ".inner", ip, SPEC["dimensions"]["H"]))
    for p in mesh.polygons:
        p.use_smooth = unit["build"]["prim"] in ("lathe_shell", "arc_bridge", "lathe_path")
    return ob


def place_camera(S, elev, dist, z, lens=None):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.data.lens = float(lens or os.environ.get("LENS", "60"))
    th = math.radians(elev)
    cam.location = (dist * math.cos(th), 0, z + dist * math.sin(th))
    d = Vector((0, 0, z)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def numeric_audit(objects, spec):
    """Контакт-чек числом (Prime Directive superskill): габариты против спеки."""
    import numpy as np
    pts = []
    deps = bpy.context.evaluated_depsgraph_get()
    for ob in objects:
        me = ob.evaluated_get(deps).to_mesh()
        pts.append(np.array([ob.matrix_world @ v.co for v in me.vertices]))
        ob.evaluated_get(deps).to_mesh_clear()
    P = np.vstack(pts)
    lo, hi = P.min(0), P.max(0)
    dims = spec["dimensions"]
    got_h = float(hi[2] - lo[2])
    got_w = float(hi[0] - lo[0])
    mouth = 2 * dims["R_top"]
    checks = [
        ("высота H", abs(got_h - dims["H"]) <= 0.01 * dims["H"], f"{got_h:.3f} vs {dims['H']}"),
        ("зев 2*R_top", abs(got_w - mouth) <= 0.02 * mouth, f"{got_w:.3f} vs {mouth:.3f}"),
        ("днище на земле", abs(float(lo[2])) <= 1e-4, f"min z={lo[2]:.5f}"),
    ]
    tris = sum(len(o.data.polygons) for o in objects)
    checks.append(("бюджет tris", tris <= spec["budget"]["tris_max"], f"{tris} <= {spec['budget']['tris_max']}"))
    print("== Числовой аудит построенной геометрии ==")
    ok = True
    for name, passed, detail in checks:
        print(f"  {'PASS' if passed else 'FAIL'} {name}: {detail}")
        ok &= passed
    return ok, int(tris)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    spec_path = argv[0]
    out_dir = argv[argv.index("--out") + 1] if "--out" in argv else \
        os.path.join(os.path.dirname(spec_path), "build")
    global SPEC
    SPEC = json.load(open(spec_path))
    style = json.load(open(os.path.join(HERE, "style_constants.json")))
    os.makedirs(out_dir, exist_ok=True)

    S = setup_scene(SPEC, style)
    objects = [build_unit(S, u, SPEC["dimensions"]) for u in SPEC["units"]]

    poses = SPEC.get("poses") or [{"name": "upright", "transform": "identity",
                                   "camera_elevation": SPEC["camera"]["elevation"],
                                   "camera_dist": SPEC["camera"]["dist"]}]
    if os.environ.get("DEBUG_SCENE"):
        import mathutils
        for ob in objects:
            ws = [(ob.matrix_world @ v.co) for v in ob.data.vertices]
            xs = [w.x for w in ws]; zs = [w.z for w in ws]
            print(f"DBGW {ob.name:8s} x[{min(xs):.3f},{max(xs):.3f}] z[{min(zs):.3f},{max(zs):.3f}]")
    audit_ok, tris = numeric_audit(objects, SPEC)
    report = {"spec": os.path.basename(spec_path), "tris": tris,
              "audit_pass": audit_ok, "renders": []}
    for pose in poses:
        # флип позы: 180° вокруг X через пустышку-якорь (пивот ставится ДО парентинга, §8)
        anchor = bpy.data.objects.new("root", None)
        S.collection.objects.link(anchor)
        for ob in objects:
            ob.parent = anchor
        if pose["transform"] == "flip_180_x":
            anchor.rotation_euler = (math.pi, 0, 0)
            anchor.location.z = -float(pose.get("sink", 0.0))
        else:
            anchor.rotation_euler = (0, 0, 0)
            anchor.location.z = 0.0
        bpy.context.view_layer.update()
        import numpy as np
        corners = []
        for ob in objects:
            corners += [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
        zs = [v.z for v in corners]
        target_z = SPEC["camera"].get("z", 0.45) if pose["transform"] == "identity" else (min(zs) + max(zs)) / 2
        place_camera(S, pose.get("camera_elevation", SPEC["camera"]["elevation"]),
                     pose.get("camera_dist", SPEC["camera"]["dist"]), target_z,
                     SPEC["camera"].get("lens"))
        print(f"поза {pose['name']}: elev={pose.get('camera_elevation', SPEC['camera']['elevation'])} "
              f"dist={pose.get('camera_dist', SPEC['camera']['dist'])} transform={pose['transform']}")
        path = os.path.join(out_dir, f"render_{pose['name']}.png")
        S.render.filepath = path
        bpy.ops.render.render(write_still=True)
        report["renders"].append({"pose": pose["name"], "png": path})
        print("рендер:", path)

    json.dump(report, open(os.path.join(out_dir, "build_report.json"), "w"), indent=2, ensure_ascii=False)
    print("BUILD", "PASS" if audit_ok else "FAIL")


if __name__ == "__main__":
    main()
