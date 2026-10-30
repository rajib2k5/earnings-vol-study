# Blender hero render

`event_terrain.py` renders the "event-time IV terrain" as one hero image: company by event day by abnormal log IV.
It is the same grid as the app's 3D terrain view, drawn once with Cycles or Eevee for the README and the report.

## Status: renders are pending

**2026-10-29 (milestone 5): not rendered: Blender unreachable.** The Blender MCP answered "Could not connect to
Blender" in the owner's session, and this machine has no `blender` binary. The README and the report use three.js
stills of the app's 3D terrain view instead (`docs/images/terrain-*.png`, made by `tools/screenshots.py`).

**No render has been made yet.** The machine that wrote the script (aarch64 Linux) has no Blender, so the script has
never run inside Blender. What was checked:

- it compiles (`python -m py_compile tools/blender/event_terrain.py`);
- its pure helpers (reading `terrain.json`, the seeded synthetic grid, mesh arrays, colours, choosing the engine and
  file format from a list of ids) were tested with plain Python, outside Blender;
- its control flow was exercised against a fake `bpy`. That fake accepts any call, so it shows the logic is sound and
  says nothing about whether each Blender API call is correct.

Until someone runs it in a real Blender, treat the `bpy` calls as untested. Likely first failures, if any, are in
`add_label` (text object placement) and `make_surface_material` (vertex-colour node). Expect to adjust the camera
(`add_camera`) and the label position after the first look at an image. `docs/images/terrain_hero.png` does not exist
yet; the script creates the folder when it writes.

## Run

From the repository root:

```bash
blender -b -P tools/blender/event_terrain.py -- \
    --in app/public/data/terrain.json --out docs/images/terrain_hero.png
```

Everything after the lone `--` is read by the script. Options:

| Option | Default | Meaning |
|---|---|---|
| `--in PATH` | none | `terrain.json` written by `tools/export_app_data.py` (data-model.md section 4) |
| `--out PATH` | `terrain_hero.png` | image to write; the extension picks the format if this Blender supports it |
| `--engine auto\|cycles\|eevee` | `auto` | `auto` prefers Cycles, then Eevee, from the engines this Blender lists |
| `--samples N` | 128 | render samples |
| `--res-x`, `--res-y` | 1920, 1080 | image size |
| `--seed N` | 7 | seed of the synthetic grid |

## Real data and the synthetic fallback

- With a valid `--in`, the render shows that file. Blue is below the baseline (the crush), orange is above it (the
  run-up). Null cells become holes.
- With no `--in`, or a path that does not exist, the script prints a warning and renders a **synthetic grid** from a
  seeded random generator. The image carries the words "SYNTHETIC ILLUSTRATIVE GRID - NOT DATA", so it cannot be
  mistaken for a result.
- A file that exists but is malformed is an error (exit code 2). It never falls back silently.

`app/public/data/terrain.json` does not exist yet: the per-view files arrive with schema 0.2.0. Until then only the
synthetic render is possible.

## Rules the script follows

- The render engine, colour transform and file format are read from what the running Blender offers. No engine id is
  assumed.
- Shader nodes are looked up by `type`, never by name.
- Colours are per-vertex, so they follow the sign of the value. Nothing in the render is computed beyond the grid to
  mesh transform; the statistics come from Python.
