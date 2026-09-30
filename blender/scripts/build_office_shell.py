"""Build the office's architectural shell and export its GLB.

Run headless from the repository root:

    blender --background --factory-startup --python blender/scripts/build_office_shell.py

The shell keeps the layout dimensions and openings from src/shared/layout.ts. The office paints
the named materials at runtime, so each project floor keeps its own wall palette.
"""
import bpy
import math
import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT = os.path.join(ROOT, "src", "client", "models", "office_shell.glb")
FLOOR = (-18.0, 18.0, -13.0, 13.0)
WALL_HEIGHT = 6.8
WALL_THICKNESS = 0.3
WING_MIN_X = 13.4
LOFT_MIN_X = 9.0
LOFT_MIN_Z = 8.0
LOFT_MAX_Z = 13.0
SKIN_THICKNESS = 0.035


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (*color, 1.0)
    principled.inputs["Roughness"].default_value = 0.84
    return mat


MATERIALS = {
    "Inside": material("Inside", (0.86, 0.82, 0.72)),
    "Outside": material("Outside", (0.74, 0.30, 0.22)),
    "Trim": material("Trim", (0.90, 0.77, 0.57)),
}


def office_to_blender(x, y, z):
    return (x, -z, y)


def box(name, x, y, z, width, depth, height, mat_name, bevel=0.035):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=office_to_blender(x, y, z))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (width, depth, height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATERIALS[mat_name])
    if bevel > 0:
        modifier = obj.modifiers.new("Soft machined edges", "BEVEL")
        modifier.width = min(bevel, min(width, depth, height) * 0.45)
        modifier.segments = 2
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def wall_piece(axis, side, at, lo, hi, bottom, top):
    if hi - lo < 0.001 or top - bottom < 0.001:
        return
    along_x = axis == "x"
    middle = (lo + hi) / 2
    height = top - bottom
    if along_x:
        x, z = middle, at
        width, depth = hi - lo, WALL_THICKNESS
        outward = -1 if side == "north" else 1
        outer_z = at + outward * (WALL_THICKNESS / 2 + SKIN_THICKNESS / 2)
        outer_x = middle
        skin_width, skin_depth = width, SKIN_THICKNESS
    else:
        x, z = at, middle
        width, depth = WALL_THICKNESS, hi - lo
        outward = -1 if side == "west" else 1
        outer_x = at + outward * (WALL_THICKNESS / 2 + SKIN_THICKNESS / 2)
        outer_z = middle
        skin_width, skin_depth = SKIN_THICKNESS, depth
    center_y = (bottom + top) / 2
    box("wall_inside", x, center_y, z, width, depth, height, "Inside", 0.055)
    box("wall_exterior", outer_x, center_y, outer_z, skin_width, skin_depth, height, "Outside", 0.018)


def build_wall(side, axis, at, lo, hi, openings):
    openings = sorted(openings, key=lambda hole: hole[0])
    cursor = lo
    baseboard_runs = []
    for center, width, sill, head in openings:
        start = center - width / 2
        end = center + width / 2
        if start < lo or end > hi:
            continue
        wall_piece(axis, side, at, cursor, start, 0, WALL_HEIGHT)
        wall_piece(axis, side, at, start, end, 0, sill)
        wall_piece(axis, side, at, start, end, head, WALL_HEIGHT)
        if sill > 0:
            baseboard_runs.append((cursor, end if cursor == lo else start))
        cursor = end
    wall_piece(axis, side, at, cursor, hi, 0, WALL_HEIGHT)
    baseboard_runs.append((cursor, hi))
    if openings:
        baseboard_runs = []
        cursor = lo
        for center, width, sill, _head in openings:
            start = center - width / 2
            end = center + width / 2
            if sill == 0:
                baseboard_runs.append((cursor, start))
                cursor = end
        baseboard_runs.append((cursor, hi))
    for start, end in baseboard_runs:
        if end - start < 0.001:
            continue
        middle = (start + end) / 2
        if axis == "x":
            box("baseboard", middle, 0.13, at, end - start, WALL_THICKNESS + 0.08, 0.26, "Trim", 0.035)
        else:
            box("baseboard", at, 0.13, middle, WALL_THICKNESS + 0.08, end - start, 0.26, "Trim", 0.035)


def merge_material_meshes():
    for name in MATERIALS:
        items = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.data.materials and obj.data.materials[0].name == name]
        bpy.ops.object.select_all(action="DESELECT")
        for obj in items:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = items[0]
        bpy.ops.object.join()
        bpy.context.object.name = "office_shell_" + name.lower()


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    min_x, max_x, min_z, max_z = FLOOR
    wall_t = WALL_THICKNESS
    north = []
    south = [(-14, 3, 1.1, 3.3), (-9, 3, 1.1, 3.3), (-4, 3, 0, 2.5), (1, 3, 1.1, 3.3), (LOFT_MIN_X + 2, 2.8, 3.9, 5.5)]
    west = [(-9, 3, 1.1, 3.3), (-3, 3, 1.1, 3.3), (3, 3, 1.1, 3.3), (6.5, 1.4, 0, 2.4)]
    east = [((LOFT_MIN_Z + LOFT_MAX_Z) / 2, 2.8, 3.9, 5.5)]

    build_wall("north", "x", min_z - wall_t / 2, min_x - wall_t, WING_MIN_X, north)
    build_wall("south", "x", max_z + wall_t / 2, min_x - wall_t, max_x + wall_t, south)
    build_wall("west", "z", min_x - wall_t / 2, min_z, max_z, west)
    build_wall("east", "z", max_x + wall_t / 2, min_z, max_z, east)
    merge_material_meshes()

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.export_scene.gltf(filepath=OUTPUT, export_format="GLB", use_selection=True)
    print("Exported", OUTPUT)


if __name__ == "__main__":
    main()