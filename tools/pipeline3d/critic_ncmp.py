#!/usr/bin/env python3
"""N-CMP критик (pipeline3d.md §3): пиксельно-палитровый гейт без Blender.

  python3 critic_ncmp.py compare RENDER.png REF.png          # гейт: рендер vs реф
  python3 critic_ncmp.py albedo HEX.png '#ED6800'            # albedo-гейт палитры
  python3 critic_ncmp.py selftest                            # самопроверка метрик

Гейты берутся из style_constants.json (ncmp_gates): IoU >= 0.85, палитра top-5
<= 10 ΔE, bbox ±4%. Палитровый гейт продакшена — по albedo, не по рендеру (§7).
"""
import json, os, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def style():
    with open(os.path.join(HERE, "style_constants.json")) as f:
        return json.load(f)["ncmp_gates"]


def load_rgb(p):
    return np.array(Image.open(p).convert("RGB"))


def mask_by_bg(img, tol=38.0):
    bg = np.median(np.concatenate([img[:8, :8].reshape(-1, 3), img[:8, -8:].reshape(-1, 3),
                                   img[-8:, :8].reshape(-1, 3), img[-8:, -8:].reshape(-1, 3)]), axis=0)
    return ~(((img - bg) ** 2).sum(axis=2) < tol ** 2)


def iou(m_render, m_ref):
    if m_render.shape != m_ref.shape:
        m_render = np.array(Image.fromarray(m_render.astype(np.uint8) * 255).resize(
            (m_ref.shape[1], m_ref.shape[0]), Image.NEAREST)) > 127
    inter = (m_render & m_ref).sum()
    union = (m_render | m_ref).sum()
    return float(inter / union) if union else 0.0


def aligned_iou(m_render, m_ref):
    """IoU с подгоном bbox (§3: вырезать по маске, вставить в позицию референсного объекта).
    Измеряет ФОРМУ; масштаб/кадрирование проверяются отдельным гейтом bbox ±4%."""
    ys, xs = np.where(m_render)
    if len(xs) == 0:
        return 0.0
    r_crop = m_render[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ys2, xs2 = np.where(m_ref)
    if len(xs2) == 0:
        return 0.0
    f_crop_h, f_crop_w = ys2.max() - ys2.min() + 1, xs2.max() - xs2.min() + 1
    r_res = np.array(Image.fromarray(r_crop.astype(np.uint8) * 255).resize(
        (f_crop_w, f_crop_h), Image.BILINEAR)) > 127
    canvas = np.zeros_like(m_ref)
    canvas[ys2.min():ys2.min() + f_crop_h, xs2.min():xs2.min() + f_crop_w] = r_res
    inter = (canvas & m_ref).sum()
    union = (canvas | m_ref).sum()
    return float(inter / union) if union else 0.0


def bbox_dims(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return 0.0, 0.0
    return float(xs.max() - xs.min()), float(ys.max() - ys.min())


def rgb2lab(img):
    img = img.astype(np.float32) / 255.0
    lin = np.where(img <= 0.04045, img / 12.92, ((img + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / (np.array([0.95047, 1.0, 1.08883]))
    eps, kap = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kap * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def hex2lab(hx):
    hx = hx.lstrip("#")
    rgb = np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)
    return rgb2lab(rgb.reshape(1, 1, 3))[0, 0]


def top_palette(img, mask, k=5):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return []
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = Image.fromarray(img[y0:y1, x0:x1]).quantize(colors=k, method=Image.MEDIANCUT)
    pal = crop.getpalette()[:3 * k]
    counts = sorted(crop.getcolors(), reverse=True)
    return [np.array(pal[i * 3:i * 3 + 3], dtype=np.float32)
            for _, i in counts[:k]]


def palette_de(pal_a, pal_b):
    """Жадное взаимное сопоставление двух палитр, ΔE76."""
    lab_a = [rgb2lab(c.reshape(1, 1, 3))[0, 0] for c in pal_a]
    lab_b = [rgb2lab(c.reshape(1, 1, 3))[0, 0] for c in pal_b]
    des = []
    used = set()
    for la in lab_a:
        best, bi = 1e9, -1
        for i, lb in enumerate(lab_b):
            if i in used:
                continue
            d = float(np.linalg.norm(la - lb))
            if d < best:
                best, bi = d, i
        if bi >= 0:
            used.add(bi)
            des.append(best)
    return des


def n0_components(mask, min_area_frac=0.01):
    """Число значимых связных компонент маски. >1 = кроп не изолирован (ломает N-CMP, §7)."""
    m = mask
    if m.shape[0] > 256:
        f = m.shape[0] // 256
        m = m[::f, ::f]
    lab = np.zeros(m.shape, dtype=np.int32)
    cur = 0
    areas = {}
    from collections import deque
    H, W = m.shape
    for y in range(H):
        for x in range(W):
            if m[y, x] and lab[y, x] == 0:
                cur += 1
                q = deque([(y, x)])
                lab[y, x] = cur
                a = 0
                while q:
                    cy, cx = q.popleft()
                    a += 1
                    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            q.append((ny, nx))
                areas[cur] = a
    big = [a for a in areas.values() if a / m.size >= min_area_frac]
    return len(big)


def n0_check(ref_path, tol=38.0):
    img = load_rgb(ref_path)
    m = mask_by_bg(img, tol)
    n = n0_components(m)
    ok = n == 1
    print(f"{'PASS' if ok else 'FAIL'} N0 изолированность: {n} значимых объект(а) в кропе "
          f"{'— чисто' if ok else '— СОСЕДНИЕ ПРЕДМЕТЫ ЛОМАЮТ МАСКУ, перекропить (§7)'}")
    return 0 if ok else 1


def compare(render_path, ref_path):
    g = style()
    r_img, f_img = load_rgb(render_path), load_rgb(ref_path)
    r_m, f_m = mask_by_bg(r_img), mask_by_bg(f_img)
    v_iou = aligned_iou(r_m, f_m)
    rw, rh = bbox_dims(r_m)
    fw, fh = bbox_dims(f_m)
    # кадро-инвариантные метрики: доля ширины кадра + аспект bbox H/W
    # (сырые пиксели некорректны: разрешение и кроп рефа != рендера)
    dw = 100 * abs(rw / r_img.shape[1] - fw / f_img.shape[1]) / max(fw / f_img.shape[1], 1e-6)
    dh = 100 * abs((rh / rw) - (fh / fw)) / max(fh / fw, 1e-6)
    des = palette_de(top_palette(r_img, r_m), top_palette(f_img, f_m))
    mean_de = float(np.mean(des)) if des else 999.0
    print(f"== N-CMP: {os.path.basename(render_path)} vs {os.path.basename(ref_path)} ==")
    n0 = n0_components(f_m)
    if n0 > 1:
        print(f"  ⚠ N0: в референсе {n0} объекта — маска рефа загрязнена, метрики занижены")
    rows = [
        ("silhouette IoU (bbox-подгон, §3)", v_iou, g["silhouette_iou_min"], ">="),
        ("кадрирование W/img_W Δ%", dw, g["bbox_dims_pct"], "<="),
        ("аспект bbox H/W Δ%", dh, g["bbox_dims_pct"], "<="),
        ("палитра top-5 ΔE (рендер)", mean_de, g["palette_top5_de_max"], "<="),
    ]
    ok = True
    for name, val, thr, op in rows:
        passed = val >= thr if op == ">=" else val <= thr
        ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'} {name}: {val:.3f} {op} {thr}")
    if not f_m.any():
        print("  ⚠ маска референса пуста — проверь кроп N0 (изолированный объект)")
    print("ИТОГ:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def albedo_de(img_path, hexcolor, tol=38.0):
    img = load_rgb(img_path)
    m = mask_by_bg(img, tol)
    if not m.any():
        print("FAIL albedo: маска пуста")
        return 1
    lab_mean = rgb2lab(img[m].reshape(-1, 1, 3)).mean(axis=0)
    d = float(np.linalg.norm(lab_mean - hex2lab(hexcolor)))
    g = style()
    ok = d <= g["zone_de_lab_max"]
    print(f"{'PASS' if ok else 'FAIL'} albedo ΔE({os.path.basename(img_path)}, {hexcolor}) = {d:.1f} "
          f"(гейт ≤ {g['zone_de_lab_max']}, режим albedo-only по §7)")
    return 0 if ok else 1


def selftest():
    img = Image.new("RGB", (256, 256), (240, 240, 240))
    px = img.load()
    for y in range(256):
        for x in range(256):
            if (x - 128) ** 2 + (y - 128) ** 2 < 80 ** 2:
                px[x, y] = (237, 104, 0)
    arr = np.array(img)
    m = mask_by_bg(arr)
    # 1: идентичная маска
    assert iou(m, m) >= 0.99, iou(m, m)
    # 2: сдвинутый круг — средний IoU
    sh = np.roll(m, 25, axis=1)
    s = iou(sh, m)
    assert 0.2 <= s <= 0.95, s
    # 3: квадрат — низкий IoU
    sq = np.zeros_like(m)
    sq[68:188, 68:188] = True
    assert iou(sq, m) <= 0.8, iou(sq, m)
    # 4: палитра — тот же цвет = 0
    des = palette_de(top_palette(arr, m), top_palette(arr, m))
    assert abs(np.mean(des)) < 2.0, des
    # 5: ΔE тот же цвет = 0
    lab = hex2lab("#ED6800")
    assert np.linalg.norm(rgb2lab(np.array([237, 104, 0], np.float32).reshape(1, 1, 3))[0, 0] - lab) < 1.0
    # 6: bbox стабильность
    w1, h1 = bbox_dims(m)
    assert abs(w1 - 2 * 80 * 0.98) < 6 and abs(h1 - 2 * 80 * 0.98) < 6, (w1, h1)
    print("SELFTEST PASS: IoU-идентичность/сдвиг/квадрат, палитра ΔE, hex2lab, bbox — метрики ведут себя как заявлено")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "selftest":
        sys.exit(selftest())
    if a and a[0] == "compare" and len(a) == 3:
        sys.exit(compare(a[1], a[2]))
    if a and a[0] == "albedo" and len(a) == 3:
        sys.exit(albedo_de(a[1], a[2]))
    if a and a[0] == "n0" and len(a) == 2:
        sys.exit(n0_check(a[1]))
    print(__doc__)
    sys.exit(2)
