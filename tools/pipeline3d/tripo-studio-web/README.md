# Tripo Studio Web automation

Uses the authenticated **Tripo Studio web account and Studio credits**, not the separate Developers API balance.

## First login

```bash
pnpm install
pnpm run login
```

Log in once in the opened Chrome window. The persistent session stays in `.profile/` (gitignored).

## Generate from FRONT / SIDE / BACK

Default files come from the current bucket run. Override them for another asset:

```bash
FRONT=/abs/front.png \
SIDE=/abs/left.png \
BACK=/abs/back.png \
pnpm run generate
```

The command chooses Smart Mesh, selects multiview, uploads FRONT to `Спереди`, SIDE to `Слева`, and BACK to `Обратная сторона`. The right-side slot remains empty. It refuses a paid run unless the create button visibly includes zero; set `ALLOW_PAID=1` only when paid Studio-credit usage is intentional.

## Download latest result as GLB

```bash
DO_DOWNLOAD=1 OUTPUT=/abs/result.glb pnpm run download
```

## Audit a downloaded GLB

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b \
  --python render_glb_audit.py -- /abs/result.glb /abs/audit-dir
```

Artifacts, screenshots, network logs, and browser downloads are written to `artifacts/` (gitignored).
