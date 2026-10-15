#!/usr/bin/env python3
"""Валидатор Asset Spec v2 — гейты N2–N4 (ontology/pipeline3d.md) в коде.

Использование:
  python3 validate_spec.py specs/bucket_paintloop.json [--style style_constants.json]

Гейты:
  G0 схема JSON Schema            G4 монотонность профиля lathe
  G1 единица во всех 3 проекциях  G5 референсы существуют на диске
  G2 у каждой единицы L2-свойства G6 ref-lock: камера + двойная поза
  G3 провенанс: нет вымышленных   G7 бюджет треугольников (оценка)
  G8 H/D сверка с замером
"""
import json, math, os, sys

from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "asset_spec.schema.json")


def load(p):
    with open(p) as f:
        return json.load(f)


def tri_estimate(unit):
    b = unit["build"]
    if b["prim"] == "lathe_path":
        rings = len(b["path"]) * 3 + 6
        return rings * b["segments"] * 2
    if b["prim"] == "lathe_shell":
        rings = max(len(b["profile_knots"]) * 3, 24)  # раннер ресемплирует так же
        seg = b["segments"]
        outer = rings * seg * 2 + seg          # бока + веер дна
        if b.get("open_top", True):
            outer += 8 * seg * 2 + seg         # внутренняя полость + дно полости
        return outer
    if b["prim"] == "box":
        return 12
    if b["prim"] == "arc_bridge":
        return 720  # консервативная оценка дуги rings+bridge
    return 0


def validate(spec_path, style_path=None):
    spec, schema = load(spec_path), load(SCHEMA)
    style = load(style_path or os.path.join(HERE, "style_constants.json"))
    fails, warns = [], []

    def gate(gid, ok, msg):
        (print(f"  PASS {gid}: {msg}") if ok else fails.append(f"{gid}: {msg}"))
        if not ok:
            print(f"  FAIL {gid}: {msg}")

    print(f"== Валидация {os.path.basename(spec_path)} ==")
    schema_errs = sorted(Draft202012Validator(schema).iter_errors(spec), key=lambda e: list(e.path))
    for e in schema_errs:
        print(f"  FAIL G0 схема: {'/'.join(map(str, e.path))}: {e.message}")
        fails.append(f"G0: {e.message}")

    units = {u["id"]: u for u in spec["units"]}
    # G1 единица во всех трёх проекциях (правило прослойки L3)
    for layer in ("front", "top", "side"):
        present = {p["unit"] for p in spec["projections"][layer]}
        missing = set(units) - present
        gate(f"G1[{layer}]", not missing, f"все единицы в проекции {layer}" +
             ("" if not missing else f"; нет: {sorted(missing)} — примитив запрещён (L0–L3 правило)"))
    # G2 L2-свойства
    no_props = [u for u in units if u not in spec["properties"]]
    gate("G2", not no_props, "у каждой единицы есть карта свойств (L2)" +
         ("" if not no_props else f"; нет: {no_props}"))
    # G3 вымышленные части (§8)
    invented = [u for u in spec["units"] if not u["provenance"]["visible_in_poses"]]
    gate("G3", not invented, "нет частей вне референсных состояний" +
         ("" if not invented else f"; вымышлены: {[u['id'] for u in invented]}"))
    # G4 профиль/путь вращения
    for u in spec["units"]:
        b = u["build"]
        if b["prim"] == "lathe_path":
            zs = [k[0] for k in b["path"]]
            rs = [k[1] for k in b["path"]]
            closed = rs[0] <= 0.01 or rs[-1] <= 0.01
            band = rs[0] >= 0.03 and rs[-1] >= 0.03  # лента (обод-вал): открыта с обоих концов
            gate(f"G4[{u['id']}]", all(0 <= z <= 1 for z in zs) and all(0 <= r <= 1.05 for r in rs)
                 and zs[-1] <= 1 and len(zs) >= 6 and (closed or band),
                 "путь в пределах; замкнут по оси ИЛИ лента (концы r>=0.03)")
            continue
        if b["prim"] == "lathe_shell":
            ts = [k[0] for k in b["profile_knots"]]
            rs = [k[1] for k in b["profile_knots"]]
            gate(f"G4[{u['id']}]", all(b >= a for a, b in zip(ts, ts[1:])) and all(0 <= r <= 1 for r in rs)
                 and 0 <= ts[0] and ts[-1] <= 1,
                 "профиль монотонен по t, r в [0,1]")
            if not (ts[0] == 0 and ts[-1] == 1) and u["role"] == "ёмкость":
                warns.append(f"G4[{u['id']}]: единица-ёмкость не покрывает t 0..1 — профиль не полный силуэт")
    # G5 референсы
    missing_refs = [r["path"] for r in spec["refs"] if not os.path.exists(r["path"])]
    gate("G5", not missing_refs, "файлы референсов существуют" +
         ("" if not missing_refs else f"; нет файла: {missing_refs} (N0: чистые изолированные кропы)"))
    # G6 ref-lock: камера + двойная поза
    gate("G6.cam", "camera" in spec, "камера референса задана (узел N1)")
    if style.get("ncmp_gates", {}).get("dual_pose_required"):
        ref_poses = {r["pose"] for r in spec["refs"]} - {"other"}
        pose_names = {p.get("transform") for p in spec.get("poses", [])}
        ok = ("identity" in pose_names and "flip_180_x" in pose_names) or len(ref_poses) == 1
        gate("G6.pose", ok, "двойная поза (прямая + перевёрнутая) присутствует")
    # G7 бюджет
    total = sum(tri_estimate(u) for u in spec["units"])
    gate("G7", total <= spec["budget"]["tris_max"], f"оценка {total} tris <= {spec['budget']['tris_max']}")
    # G8 H/D
    dims = spec.get("dimensions", {})
    if "H_over_D" in dims:
        hd = dims["H"] / (2 * dims["R_top"])
        gate("G8", abs(hd - dims["H_over_D"]) / dims["H_over_D"] <= 0.05,
             f"H/D построенного {hd:.2f} против замера {dims['H_over_D']} (±5%)")

    print(f"\nИТОГ: {'FAIL' if fails else 'PASS'} — {len(fails)} нарушений")
    for f in fails:
        print("  ✗ " + f)
    for w in warns:
        print("  ⚠ " + w)
    return 0 if not fails else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    spec = next((a for a in args if not a.startswith("--")), None)
    style = None
    if "--style" in args:
        style = args[args.index("--style") + 1]
    if not spec:
        print(__doc__)
        sys.exit(2)
    sys.exit(validate(spec, style))
