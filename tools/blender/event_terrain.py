# =============================================================================
# event_terrain.py — Blender script: hero render of the "event-time IV terrain".
#
# Run (headless, from the repository root):
#   blender -b -P tools/blender/event_terrain.py -- \
#       --in app/public/data/terrain.json --out docs/images/terrain_hero.png
#
# Everything after the lone "--" belongs to this script; Blender ignores it.
#
# WHAT IT DRAWS
#   The same grid as the app's EventTerrain3D view: one row per company, one
#   column per event day (rel_day, day 0 = first close after the news), height
#   = mean abnormal log IV. Blue is below the baseline (the crush), orange is
#   above it (the run-up). The box is the same 10 x 6 x 3 as
#   app/src/lib/terrain.ts, so the render and the app look alike.
#
# INPUT
#   terrain.json as written by tools/export_app_data.py (data-model.md section 4):
#   {"data": {"rel_days": [...], "rows": [{"ticker": ...}, ...],
#             "values": [[...], ...], "measure": ..., "units": ...}}
#   `values[company][event_day]`; null means "not computed" and leaves a hole.
#   A bare {"rel_days", "values", ...} object (no envelope) is accepted too.
#
# IF THE FILE IS MISSING
#   Without --in, or when the path does not exist, the script renders a
#   SYNTHETIC grid from a seeded random generator and prints a warning. The
#   image then carries the words "SYNTHETIC ILLUSTRATIVE GRID - NOT DATA", so
#   it cannot be mistaken for a result. A file that exists but is malformed is
#   an error, never a silent fallback.
#
# BLENDER VERSION RULES (the script runs in someone else's Blender)
#   - Render engine, colour transform and file format are read from what this
#     Blender offers. No engine id is assumed: Cycles is preferred, then Eevee.
#   - Shader nodes are looked up by their `type`, never by name (names are
#     localised).
#   - The pure helpers (grid loading, synthetic grid, mesh arrays, colours) do
#     not need bpy, so they can be tested with plain Python.
#
# STATUS
#   Not yet run inside Blender: there is no Blender on the machine that wrote
#   it. See tools/blender/README.md.
# =============================================================================

import argparse
import json
import math
import os
import random
import re
import sys
from dataclasses import dataclass

# bpy only exists inside Blender. Without it the pure helpers below still work
# (tests, py_compile); main() refuses to run.
try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

# Same box as app/src/lib/terrain.ts (event days -> x, companies -> y, value -> z).
WIDTH, DEPTH, HEIGHT = 10.0, 6.0, 3.0

# Diverging colours: blue below the baseline, orange above it, pale grey at 0.
NEG_RGB = (0.13, 0.40, 0.67)
POS_RGB = (0.84, 0.38, 0.05)
MID_RGB = (0.93, 0.93, 0.91)

SYNTHETIC_LABEL = "SYNTHETIC ILLUSTRATIVE GRID - NOT DATA"
COLOR_LAYER = "terrain_col"

# Output extension -> Blender's file-format name. The name is only used when the
# running Blender lists it (pick_file_format checks).
FORMAT_BY_EXT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".exr": "OPEN_EXR",
}


# ----------------------------------------------------------------------------
# Pure helpers (no bpy)
# ----------------------------------------------------------------------------


@dataclass
class Grid:
    """values[company][event_day]; None marks a missing cell."""

    rel_days: list
    row_labels: list
    values: list
    measure: str
    units: str
    synthetic: bool = False


def script_args(argv=None):
    """The part of the command line after the lone "--" (empty if there is none)."""
    argv = sys.argv if argv is None else argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def parse_args(args):
    p = argparse.ArgumentParser(
        prog="blender -b -P tools/blender/event_terrain.py --",
        description="Render the event-time IV terrain as a hero image.",
    )
    p.add_argument("--in", dest="src", default=None,
                   help="terrain.json path; a synthetic grid is used when it is missing")
    p.add_argument("--out", default="terrain_hero.png", help="image to write (default: terrain_hero.png)")
    p.add_argument("--seed", type=int, default=7, help="seed of the synthetic grid (default 7)")
    p.add_argument("--samples", type=int, default=128, help="render samples (default 128)")
    p.add_argument("--res-x", type=int, default=1920)
    p.add_argument("--res-y", type=int, default=1080)
    p.add_argument("--engine", choices=("auto", "cycles", "eevee"), default="auto",
                   help="auto prefers Cycles, then Eevee, from what this Blender offers")
    return p.parse_args(args)


def _cell(x, where):
    """One grid cell: a finite number, or None for null / NaN / infinity."""
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{where}: expected a number or null, got {x!r}")
    return float(x) if math.isfinite(x) else None


def parse_grid(doc):
    """Turn a parsed terrain.json (with or without the envelope) into a Grid."""
    data = doc.get("data", doc) if isinstance(doc, dict) else None
    if not isinstance(data, dict):
        raise ValueError("terrain.json must be a JSON object")
    rel_days, values = data.get("rel_days"), data.get("values")
    if not isinstance(rel_days, list) or not isinstance(values, list):
        raise ValueError("terrain.json needs 'rel_days' and 'values' arrays")
    if len(rel_days) < 2 or len(values) < 2:
        raise ValueError(f"need at least a 2 x 2 grid, got {len(values)} rows x {len(rel_days)} columns")
    grid = []
    for i, row in enumerate(values):
        if not isinstance(row, list) or len(row) != len(rel_days):
            raise ValueError(f"values[{i}] must be a list of {len(rel_days)} cells "
                             f"(one per rel_day), got {row!r:.60}")
        grid.append([_cell(x, f"values[{i}][{j}]") for j, x in enumerate(row)])
    rows = data.get("rows")
    if rows is None:
        labels = [str(i) for i in range(len(values))]
    else:
        if not isinstance(rows, list) or len(rows) != len(values):
            raise ValueError(f"'rows' must have one entry per row of 'values' ({len(values)})")
        labels = [str(r.get("ticker", r.get("security_id", i))) if isinstance(r, dict) else str(r)
                  for i, r in enumerate(rows)]
    return Grid(
        rel_days=list(rel_days),
        row_labels=labels,
        values=grid,
        measure=str(data.get("measure", "mean abnormal log IV")),
        units=str(data.get("units", "")),
    )


def load_grid(path):
    with open(path, encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from None
    return parse_grid(doc)


def synthetic_grid(seed=7, n_rows=40, first_day=-10, last_day=10):
    """A made-up terrain with the textbook shape: run-up, crush on day 0, decay.

    Seeded, so the same seed gives the same grid. It is illustration only and
    the render says so.
    """
    rng = random.Random(seed)
    days = list(range(first_day, last_day + 1))
    rows = []
    for _ in range(n_rows):
        runup = rng.uniform(0.02, 0.10)      # height just before the news
        crush = rng.uniform(0.08, 0.30)      # depth of the day-0 drop
        tau = rng.uniform(2.0, 6.0)          # how fast it recovers, in sessions
        row = []
        for d in days:
            if d < 0:
                level = runup * ((d - first_day + 1) / (-first_day)) ** 2
            else:
                level = -crush * math.exp(-d / tau)
            row.append(level + rng.gauss(0.0, 0.01))
        rows.append(row)
    return Grid(
        rel_days=days,
        row_labels=[f"SYN{i + 1:02d}" for i in range(n_rows)],
        values=rows,
        measure="mean abnormal log IV (synthetic)",
        units="log points",
        synthetic=True,
    )


def diverging_colour(t):
    """RGBA for t in [-1, 1]: blue below 0, pale at 0, orange above 0 (t is clamped)."""
    t = max(-1.0, min(1.0, t))
    end = POS_RGB if t > 0 else NEG_RGB
    k = abs(t)
    return tuple(m + (e - m) * k for m, e in zip(MID_RGB, end)) + (1.0,)


def build_surface(grid, width=WIDTH, depth=DEPTH, height=HEIGHT):
    """Grid -> flat mesh data: (vertices, quad faces, vertex colours, scale).

    One vertex per cell, one quad per grid square. A square that touches a
    missing cell is left out, so gaps show as holes (as in the app). The tallest
    |value| maps to `height`; the same scale colours the vertices, so colour
    follows the sign of the value.
    """
    n_rows, n_cols = len(grid.values), len(grid.rel_days)
    finite = [v for row in grid.values for v in row if v is not None]
    scale = max((abs(v) for v in finite), default=0.0)
    if scale == 0.0:
        scale = 1.0
    verts, colours = [], []
    for i, row in enumerate(grid.values):
        y = (i / (n_rows - 1) - 0.5) * depth
        for j, v in enumerate(row):
            x = (j / (n_cols - 1) - 0.5) * width
            t = 0.0 if v is None else v / scale
            verts.append((x, y, t * height))
            colours.append(diverging_colour(t))
    faces = []
    for i in range(n_rows - 1):
        for j in range(n_cols - 1):
            corners = ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))
            if any(grid.values[r][c] is None for r, c in corners):
                continue
            a = i * n_cols + j
            faces.append((a, a + 1, a + n_cols + 1, a + n_cols))
    return verts, faces, colours, scale


def parse_enum_error(message):
    """Valid ids from the TypeError Blender raises for an impossible enum value.

    The message ends with the allowed ids in single quotes, e.g.
    ... not found in ('BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH', 'CYCLES')
    """
    return re.findall(r"'([^']+)'", message)


def pick_by_key(ids, keys):
    """First id containing the first key that matches anything (case-insensitive)."""
    for key in keys:
        for ident in ids:
            if key.upper() in ident.upper():
                return ident
    return None


def choose_engine(ids, want="auto"):
    order = {"auto": ("CYCLES", "EEVEE"), "cycles": ("CYCLES",), "eevee": ("EEVEE",)}[want]
    return pick_by_key(ids, order)


def pick_file_format(ext, available):
    """Blender's file-format id for an extension, only if this Blender lists it."""
    want = FORMAT_BY_EXT.get(ext.lower())
    return want if want in available else None


# ----------------------------------------------------------------------------
# Blender side
# ----------------------------------------------------------------------------


def enum_choices(owner, prop):
    """Every id Blender accepts for an enum property of `owner`.

    The RNA list can under-report (render engines and colour transforms register
    late), so an impossible value is assigned on purpose: Blender's TypeError
    lists the real choices. The property is put back afterwards.
    """
    try:
        ids = [i.identifier for i in owner.bl_rna.properties[prop].enum_items]
    except (KeyError, TypeError, RuntimeError):
        ids = []
    before = getattr(owner, prop)
    try:
        setattr(owner, prop, "__no_such_item__")
    except TypeError as exc:
        ids += [i for i in parse_enum_error(str(exc)) if i not in ids]
    finally:
        try:
            setattr(owner, prop, before)
        except TypeError:
            pass
    return ids


def first_node(tree, node_type):
    """The first node of a type (looked up by `type`, never by name)."""
    return next((n for n in tree.nodes if n.type == node_type), None)


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True        # needed before Blender 5; deprecated after
    except Exception:
        pass
    return mat


def make_surface_material():
    mat = new_material("terrain_material")
    tree = mat.node_tree
    bsdf = first_node(tree, "BSDF_PRINCIPLED") or tree.nodes.new("ShaderNodeBsdfPrincipled")
    out = first_node(tree, "OUTPUT_MATERIAL") or tree.nodes.new("ShaderNodeOutputMaterial")
    colour = tree.nodes.new("ShaderNodeVertexColor")
    colour.layer_name = COLOR_LAYER
    tree.links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    if not out.inputs["Surface"].links:
        tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_flat_material(name, rgb, emission=False):
    mat = new_material(name)
    tree = mat.node_tree
    out = first_node(tree, "OUTPUT_MATERIAL") or tree.nodes.new("ShaderNodeOutputMaterial")
    if emission:
        node = tree.nodes.new("ShaderNodeEmission")
        node.inputs["Color"].default_value = rgb + (1.0,)
        shader_out = node.outputs["Emission"]
    else:
        node = first_node(tree, "BSDF_PRINCIPLED") or tree.nodes.new("ShaderNodeBsdfPrincipled")
        node.inputs["Base Color"].default_value = rgb + (1.0,)
        node.inputs["Roughness"].default_value = 0.9
        shader_out = node.outputs["BSDF"]
    for link in list(out.inputs["Surface"].links):
        tree.links.remove(link)
    tree.links.new(shader_out, out.inputs["Surface"])
    return mat


def add_object(scene, name, data):
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def add_terrain(scene, grid):
    """Mesh with per-vertex colours for the grid. Returns (object, lowest z)."""
    verts, faces, colours, _scale = build_surface(grid)
    mesh = bpy.data.meshes.new("terrain_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    flat = [c for rgba in colours for c in rgba]
    if hasattr(mesh, "color_attributes"):
        attr = mesh.color_attributes.new(name=COLOR_LAYER, type="FLOAT_COLOR", domain="POINT")
        attr.data.foreach_set("color", flat)
    else:                                                   # Blender before 3.2
        layer = mesh.vertex_colors.new(name=COLOR_LAYER)
        for loop in mesh.loops:
            layer.data[loop.index].color = colours[loop.vertex_index]
    mesh.materials.append(make_surface_material())
    return add_object(scene, "terrain", mesh), min(v[2] for v in verts)


def add_floor(scene, z):
    """A pale floor a little below the lowest valley, so the shape has something to sit on."""
    half = max(WIDTH, DEPTH) * 1.5
    mesh = bpy.data.meshes.new("floor_mesh")
    mesh.from_pydata([(-half, -half, z), (half, -half, z), (half, half, z), (-half, half, z)], [], [(0, 1, 2, 3)])
    mesh.update()
    mesh.materials.append(make_flat_material("floor_material", (0.80, 0.80, 0.79)))
    return add_object(scene, "floor", mesh)


def add_camera(scene, target):
    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 45.0
    cam = add_object(scene, "camera", cam_data)
    # Front-left, above, about 19 units back: the 10 x 6 x 3 box fits with a margin.
    offset = mathutils.Vector((-0.45, -1.0, 0.62)).normalized() * 19.0
    cam.location = mathutils.Vector(target) + offset
    look = mathutils.Vector(target) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam, cam_data


def add_label(scene, cam, cam_data, res_x, res_y, text):
    """Text pinned to the lower-left of the frame (a child of the camera)."""
    dist = 8.0
    half_w = dist * (cam_data.sensor_width / 2.0) / cam_data.lens
    half_h = half_w * res_y / res_x
    curve = bpy.data.curves.new("label", type="FONT")
    curve.body = text
    curve.size = half_h * 0.075
    obj = add_object(scene, "label", curve)
    obj.parent = cam
    obj.location = (-half_w * 0.95, -half_h * 0.80, -dist)
    obj.data.materials.append(make_flat_material("label_material", (0.08, 0.08, 0.10), emission=True))
    return obj


def add_lights_and_world(scene):
    sun_data = bpy.data.lights.new("sun", type="SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(5.0)
    sun = add_object(scene, "sun", sun_data)
    sun.rotation_euler = (math.radians(50.0), math.radians(10.0), math.radians(35.0))

    world = bpy.data.worlds.new("world")
    try:
        world.use_nodes = True
    except Exception:
        pass
    background = first_node(world.node_tree, "BACKGROUND")
    if background is not None:
        background.inputs["Color"].default_value = (0.96, 0.96, 0.95, 1.0)
        background.inputs["Strength"].default_value = 1.0
    scene.world = world


def configure_render(scene, args):
    """Pick the engine, colour transform and file format from what this Blender offers."""
    engines = enum_choices(scene.render, "engine")
    engine = choose_engine(engines, args.engine)
    if engine is None:
        raise RuntimeError(f"no usable render engine for --engine {args.engine}; this Blender offers {engines}")
    scene.render.engine = engine
    if "CYCLES" in engine.upper() and hasattr(scene, "cycles"):
        scene.cycles.samples = args.samples
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = args.samples

    # "Standard" keeps the diverging colours as authored; Filmic / AgX wash them out.
    transform = pick_by_key(enum_choices(scene.view_settings, "view_transform"), ("STANDARD",))
    if transform is not None:
        scene.view_settings.view_transform = transform

    ext = os.path.splitext(args.out)[1]
    formats = enum_choices(scene.render.image_settings, "file_format")
    file_format = pick_file_format(ext, formats)
    if file_format is None:
        raise RuntimeError(f"cannot write '{ext}' images; supported here: {formats}")
    scene.render.image_settings.file_format = file_format
    scene.render.resolution_x, scene.render.resolution_y = args.res_x, args.res_y
    scene.render.resolution_percentage = 100
    scene.render.filepath = os.path.abspath(args.out)
    return engine


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def resolve_grid(args):
    if args.src and os.path.exists(args.src):
        return load_grid(args.src)
    why = "no --in given" if not args.src else f"{args.src} does not exist"
    print(f"WARNING: {why}: rendering a SYNTHETIC grid (seed {args.seed}). "
          f"The image will be labelled '{SYNTHETIC_LABEL}'.", file=sys.stderr)
    return synthetic_grid(args.seed)


def label_text(grid, seed):
    if grid.synthetic:
        return f"{SYNTHETIC_LABEL} (seed {seed})\nx: event day   y: company   height: {grid.measure}"
    unit = f" ({grid.units})" if grid.units else ""
    return f"Event-time IV terrain: {grid.measure}{unit}\nx: event day   y: company   n={len(grid.values)} companies"


def main(argv=None):
    if bpy is None:
        sys.exit("event_terrain.py must run inside Blender: "
                 "blender -b -P tools/blender/event_terrain.py -- --in terrain.json --out terrain_hero.png")
    args = parse_args(script_args(argv))
    try:
        grid = resolve_grid(args)
        scene = bpy.context.scene
        clear_scene()
        engine = configure_render(scene, args)
        _terrain, lowest = add_terrain(scene, grid)
        add_floor(scene, lowest - 0.15 * HEIGHT)
        cam, cam_data = add_camera(scene, (0.0, 0.0, 0.15 * HEIGHT))
        add_label(scene, cam, cam_data, args.res_x, args.res_y, label_text(grid, args.seed))
        add_lights_and_world(scene)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"rendering {len(grid.values)} x {len(grid.rel_days)} grid with {engine} -> {args.out}")
    bpy.ops.render.render(write_still=True)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
