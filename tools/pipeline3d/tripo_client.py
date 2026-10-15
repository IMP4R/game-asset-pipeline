#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tripo3D клиент: multiview (front/left/back) -> GLB.

Использование:
  python3 tripo_client.py balance
  python3 tripo_client.py multiview FRONT.png LEFT.png BACK.png OUT_DIR
Ключ берётся из env TRIPO_API_KEY.
"""
import json, os, sys, time, urllib.request, uuid

BASE = "https://openapi.tripo3d.ai/v3"
KEY = os.environ.get("TRIPO_API_KEY", "")

def hdr(json_ct=False):
    h = {"Authorization": f"Bearer {KEY}"}
    if json_ct:
        h["Content-Type"] = "application/json"
    return h

def api(req):
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"HTTP {e.code}: {body[:500]}")

def balance():
    req = urllib.request.Request(f"{BASE}/account/balance", headers=hdr())
    print(json.dumps(api(req), ensure_ascii=False))

def upload(path):
    boundary = uuid.uuid4().hex
    name = os.path.basename(path)
    data = open(path, "rb").read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/files", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {KEY}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    out = api(req)
    if out.get("code") != 0:
        raise SystemExit(f"upload failed: {out}")
    return out["data"]["image_token"] if "image_token" in out.get("data", {}) else out["data"].get("token")

def poll(task_id, max_s=900):
    t0 = time.time()
    while time.time() - t0 < max_s:
        req = urllib.request.Request(f"{BASE}/tasks/{task_id}", headers=hdr())
        d = api(req)["data"]
        st = d.get("status"); pr = d.get("progress", 0)
        print(f"  status={st} progress={pr}", flush=True)
        if st == "success":
            return d
        if st in ("failed", "cancelled", "banned"):
            raise SystemExit(f"task {st}: {json.dumps(d)[:400]}")
        time.sleep(4)
    raise SystemExit("poll timeout")

def download(url, dst):
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr()), timeout=300) as r, open(dst, "wb") as f:
        f.write(r.read())
    return dst

def multiview(front, left, back, out_dir, model="p2.0"):
    os.makedirs(out_dir, exist_ok=True)
    toks = {k: upload(p) for k, p in (("front", front), ("left", left), ("back", back))}
    print("tokens:", json.dumps({k: v[:12] + "…" for k, v in toks.items()}))
    payload = {"images": toks, "model": model}
    req = urllib.request.Request(f"{BASE}/generation/multiview-to-model",
                                 data=json.dumps(payload).encode(), method="POST", headers=hdr(True))
    out = api(req)
    if out.get("code") != 0:
        raise SystemExit(f"create failed: {out}")
    task_id = out["data"]["task_id"]
    print("task:", task_id, flush=True)
    d = poll(task_id)
    url = d["output"].get("model_url") or (d["output"].get("model_urls") or [None])[0]
    if not url:
        raise SystemExit(f"no model_url: {json.dumps(d['output'])[:400]}")
    glb = download(url, os.path.join(out_dir, "model.glb"))
    json.dump({"task_id": task_id, "output": d["output"]},
              open(os.path.join(out_dir, "task.json"), "w"), ensure_ascii=False, indent=1)
    print("GLB:", glb)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "balance":
        balance()
    elif cmd == "multiview":
        multiview(*sys.argv[2:5], sys.argv[5] if len(sys.argv) > 5 else ".")
