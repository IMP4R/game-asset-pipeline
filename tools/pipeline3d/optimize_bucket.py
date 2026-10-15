#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автозамыкание: координатный спуск параметров ведра по пиксельной близости к эпюру.

Метрика: 0.6*IoU(силуэт) + 0.4*IoU(рёбра) против FRONT-кропа assets/epure_bucket_sl3.png.
Каждая оценка = headless Blender рендер + сравнение. Лучшие параметры -> spec_opt.json.
"""
import json, math, os, subprocess, sys, time
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "..", "assets"))
EPURE = os.path.join(ASSETS, "epure_bucket_front.png")
RUN = os.path.join(HERE, "runs", "2026-09-01-bucket-v4")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
REF_UPRIGHT = os.path.join(ASSETS, "ref_clean_upright2.png")

R_TOP_M, H_M = 0.465, 0.93

# ---------------------------------------------------------------- параметры
P0 = {
    "taper":       0.80,   # r низа борта (доля R_top)
    "fillet":      0.10,   # радиус филета, м
    "rim_z0":      0.855,  # низ обода (доля H)
    "rim_inner":   0.865,  # внутренний радиус обода
    "crown_dome":  0.05,   # глубина купола короны (доля H)
    "band_z0":     0.64,   # низ ленты ручки
    "band_z1":     0.825,  # верх ленты
    "band_off":    0.045,  # отступ ленты от стенки (доля R_top)
    "elev":        18.0,   # камера, град
    "dist":        2.35,   # камера, м
    "band_arch":   0.20,   # прогиб ленты-арки: доп. отступ в середине
    "rim_bulge":   0.015,  # пухлость обода: доп. внешний радиус в середине
}
STEPS = {
    "taper": 0.02, "fillet": 0.015, "rim_z0": 0.01, "rim_inner": 0.015,
    "crown_dome": 0.015, "band_z0": 0.015, "band_z1": 0.015, "band_off": 0.008,
    "elev": 3.0, "dist": 0.12, "band_arch": 0.08, "rim_bulge": 0.006,
}
LO = {"taper": 0.70, "fillet": 0.05, "rim_z0": 0.82, "rim_inner": 0.82, "crown_dome": 0.0,
      "band_z0": 0.56, "band_z1": 0.78, "band_off": 0.02, "elev": 10.0, "dist": 2.0}
HI = {"taper": 0.88, "fillet": 0.16, "rim_z0": 0.88, "rim_inner": 0.91, "crown_dome": 0.09,
      "band_z0": 0.70, "band_z1": 0.87, "band_off": 0.07, "elev": 30.0, "dist": 2.7,
      "band_arch": 0.5, "rim_bulge": 0.04}

# ---------------------------------------------------------------- маски/метрика
def mask_from(path, bg_xy=(4, 4), thr=60):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    bg = im[bg_xy[1], bg_xy[0]]
    d = np.sqrt(((im - bg) ** 2).sum(axis=2))
    return d > thr

def norm_mask(m, size=220):
    ys, xs = np.where(m)
    if len(xs) < 50:
        return np.zeros((size, size), bool)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = m[y0:y1, x0:x1]
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)
    return np.asarray(im) > 127

def edges_of(m):
    g = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1)), float) / 255
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]; gy[1:-1, :] = g[2:, :] - g[:-2, :]
    mag = np.sqrt(gx * gx + gy * gy)
    e = mag > 0.35 * mag.max()
    return np.asarray(Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 127

def iou(a, b):
    i = (a & b).sum(); u = (a | b).sum()
    return i / u if u else 0.0

def score_pair(ref_mask, render_path):
    r = norm_mask(mask_from(render_path, bg_xy=(4, 4)))
    sil = iou(ref_mask, r)
    ed = iou(edges_of(ref_mask), edges_of(r))
    return 0.6 * sil + 0.4 * ed, sil, ed

# ---------------------------------------------------------------- генерация спеки
def make_spec(p, out_path):
    Rf_m = p["fillet"]                     # филет в метрах
    Rf_z = Rf_m / H_M                      # доля H
    Rf_r = Rf_m / R_TOP_M                  # доля R_top
    r_c = p["taper"] - Rf_r                # r центра дуги = точка касания с полом
    z_c = Rf_z                             # z центра дуги
    body = [[0.0, 0.0]]
    for i in range(1, 5):
        body.append([0.0, round(r_c * i / 5, 4)])
    for i in range(11):
        t = (math.pi / 2) * i / 10
        body.append([round(z_c - Rf_z * math.cos(t), 4), round(r_c + Rf_r * math.sin(t), 4)])
    for i in range(1, 7):
        t = i / 6
        z = Rf_z + t * (p["rim_z0"] - Rf_z)
        r = p["taper"] + t * (0.965 - p["taper"])
        body.append([round(z, 4), round(r, 4)])

    zi = p["rim_z0"]
    rim = [
        [round(zi, 4), 0.965],
        [round(zi + 0.035, 4), 0.985],
        [round(zi + 0.07, 4), round(0.997 + p["rim_bulge"], 4)],
        [round(zi + 0.105, 4), 1.0],
        [round(zi + 0.13, 4), round(0.985 + p["rim_bulge"], 4)],
        [round(zi + 0.145, 4), 0.97],
        [1.0, 0.945],
        [round(1.0 - p["crown_dome"] * 0.5, 4), 0.925],
        [round(zi + 0.06, 4), round(p["rim_inner"], 4)],
        [round(zi, 4), round(p["rim_inner"] - 0.007, 4)],
    ]
    cav = [[p["rim_z0"], round(p["rim_inner"] - 0.007, 4)], [0.80, 0.855], [0.70, 0.852],
           [0.58, 0.85], [0.45, 0.849], [0.32, 0.848], [0.26, 0.846], [0.245, 0.80],
           [0.242, 0.65], [0.245, 0.45], [0.25, 0.25], [0.253, 0.0]]
    r_at = lambda z: p["taper"] + (0.965 - p["taper"]) * (z - Rf_z) / max(p["rim_z0"] - Rf_z, 1e-3)
    band = []
    for z, add in [(p["band_z0"], 0.0), (p["band_z0"] + 0.025, p["band_off"] - 0.012),
                   ((p["band_z0"] + p["band_z1"]) / 2, p["band_off"] * (1 + p["band_arch"])),
                   (p["band_z1"] - 0.025, p["band_off"] - 0.006), (p["band_z1"], p["band_off"] - 0.032)]:
        band.append([round(z, 4), round(r_at(z) + add, 4)])

    def sphere(r_m, n=12):
        return [[round((r_m + r_m * math.sin(a)) / H_M, 4), round((r_m * math.cos(a)) / R_TOP_M, 4)]
                for a in [-math.pi / 2 + math.pi * i / n for i in range(n + 1)]]

    units = [
        {"id": "body", "role": "ёмкость — корпус", "requirement": "автоген: пол+дуговой филет+конус",
         "build": {"prim": "lathe_path", "segments": 48, "path": body},
         "provenance": {"visible_in_poses": ["upright", "flipped"], "ref": "epure"}},
        {"id": "rim", "role": "ёмкость — обод", "requirement": "автоген: наплыв с куполом короны",
         "build": {"prim": "lathe_path", "segments": 48, "path": rim},
         "provenance": {"visible_in_poses": ["upright", "flipped"], "ref": "epure"}},
        {"id": "cavity", "role": "ёмкость — полость", "requirement": "автоген: вертикальная стенка",
         "build": {"prim": "lathe_path", "segments": 48, "path": cav},
         "provenance": {"visible_in_poses": ["upright"], "ref": "epure TOP"}},
        {"id": "handle", "role": "переноска — лента", "requirement": "автоген: лента off the wall",
         "build": {"prim": "lathe_path", "segments": 48, "path": band},
         "provenance": {"visible_in_poses": ["upright", "flipped"], "ref": "epure"}},
    ]
    props = {
        "body": {"hex": "#F98A00", "gloss": 0.18, "gradient_stops": [
            {"pos": 0.0, "hex": "#E67800"}, {"pos": 0.55, "hex": "#F98A00"}, {"pos": 1.0, "hex": "#FF9D2E"}]},
        "rim": {"hex": "#F98A00", "gloss": 0.18, "gradient_stops": [
            {"pos": 0.0, "hex": "#F08200"}, {"pos": 1.0, "hex": "#FF9D2E"}]},
        "cavity": {"hex": "#F98A00", "gloss": 0.12, "gradient_stops": [
            {"pos": 0.24, "hex": "#D96F00"}, {"pos": 0.55, "hex": "#EF8300"}, {"pos": 0.86, "hex": "#F98F10"}]},
        "handle": {"hex": "#2E2E33", "gloss": 0.05, "gradient_stops": [
            {"pos": 0.0, "hex": "#26262B"}, {"pos": 0.5, "hex": "#3A3A40"}, {"pos": 1.0, "hex": "#2E2E33"}]},
    }
    knob_r = 0.042
    knob_z = (p["band_z0"] + p["band_z1"]) / 2 * H_M - knob_r
    for side, nm in ((-1, "handle_knob_l"), (1, "handle_knob_r")):
        units.append({"id": nm, "role": "переноска — ось", "requirement": "автоген: сфера-шарнир",
                      "build": {"prim": "lathe_path", "segments": 32, "path": sphere(knob_r),
                                "origin": [round(side * 0.42, 4), 0.0, round(knob_z, 4)]},
                      "provenance": {"visible_in_poses": ["upright", "flipped"], "ref": "epure"}})
        props[nm] = {"hex": "#2E2E33", "gloss": 0.25, "gradient_stops": [
            {"pos": 0.0, "hex": "#26262B"}, {"pos": 0.5, "hex": "#3F3F46"}, {"pos": 1.0, "hex": "#2E2E33"}]}
    ids = [u["id"] for u in units]
    proj = {layer: [{"unit": i, "x0": -1.0, "x1": 1.0, "y0": 0.0, "y1": 1.0} for i in ids]
            for layer in ("front", "side", "top")}
    spec = {
        "spec_version": "2.0",
        "asset": {"id": "bucket_paintloop", "game": "paint_loop", "class": "ёмкость",
                  "l0_function": "хранит и переносит краску", "notes": "автоподгон под эпюр (optimize_bucket.py)"},
        "dimensions": {"H": H_M, "R_top": R_TOP_M, "H_over_D": round(H_M / (2 * R_TOP_M), 3)},
        "units": units, "projections": proj, "properties": props,
        "poses": [
            {"name": "upright", "transform": "identity", "camera_elevation": round(p["elev"], 1), "camera_dist": round(p["dist"], 3)},
            {"name": "flipped", "transform": "flip_180_x", "camera_elevation": round(p["elev"] * 0.8, 1), "camera_dist": round(p["dist"] * 0.95, 3), "sink": 0.55},
        ],
        "camera": {"elevation": round(p["elev"], 1), "azimuth": 0, "dist": round(p["dist"], 3), "z": 0.45},
        "refs": [{"name": "epure", "path": EPURE, "pose": "other"},
                 {"name": "upright", "path": REF_UPRIGHT, "pose": "upright"}],
        "budget": {"tris_max": 26000, "one_mesh": False, "texture": "vertex_gradient"},
    }
    json.dump(spec, open(out_path, "w"), indent=2, ensure_ascii=False)

def render(spec_path, out_dir):
    env = dict(os.environ, OUTLINE_PX="3")
    r = subprocess.run([BLENDER, "--background", "--python", os.path.join(HERE, "generate_blender.py"),
                        "--", spec_path, "--out", out_dir],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
    ok = "BUILD PASS" in r.stdout
    return ok, os.path.join(out_dir, "render_upright.png")

# ---------------------------------------------------------------- оптимизация
def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    epure_mask = norm_mask(mask_from(EPURE, bg_xy=(4, 4)))
    best = dict(P0)
    tmp_spec = os.path.join(RUN, "spec_opt_tmp.json")
    out_dir = os.path.join(RUN, "opt_tmp")
    os.makedirs(out_dir, exist_ok=True)
    make_spec(best, tmp_spec)
    ok, rp = render(tmp_spec, out_dir)
    best_s, sil, ed = score_pair(epure_mask, rp)
    log = [{"phase": "init", "score": round(best_s, 4), "sil": round(sil, 4), "edge": round(ed, 4), "params": dict(best)}]
    print(f"init score={best_s:.4f} sil={sil:.4f} edge={ed:.4f}", flush=True)
    t0 = time.time()
    for rnd in range(iters):
        for k in STEPS:
            improved = True
            while improved and time.time() - t0 < 1500:
                improved = False
                for sgn in (+1, -1):
                    cand = dict(best); cand[k] = round(max(LO[k], min(HI[k], best[k] + sgn * STEPS[k])), 4)
                    if cand[k] == best[k]:
                        continue
                    make_spec(cand, tmp_spec)
                    ok, rp = render(tmp_spec, out_dir)
                    if not ok or not os.path.exists(rp):
                        continue
                    s, sil, ed = score_pair(epure_mask, rp)
                    log.append({"round": rnd, "key": k, "sgn": sgn, "score": round(s, 4)})
                    if s > best_s + 1e-4:
                        best, best_s = cand, s
                        improved = True
                        print(f"r{rnd} {k}{'+' if sgn > 0 else '-'} -> {s:.4f} (sil {sil:.3f} edge {ed:.3f})", flush=True)
                        break
        for k in STEPS:
            STEPS[k] *= 0.6
    make_spec(best, os.path.join(RUN, "spec_opt.json"))
    json.dump({"best_score": round(best_s, 4), "best": best, "log": log},
              open(os.path.join(RUN, "opt_log.json"), "w"), ensure_ascii=False, indent=1)
    print("BEST", round(best_s, 4), json.dumps(best), flush=True)

if __name__ == "__main__":
    main()
