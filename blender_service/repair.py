import bpy
import os

# Expected global variables from server.py execution context:
# request_data = { "input_file": ..., "output_file": ..., "params": ... }

data = request_data
input_rel = data.get('input_file')
output_rel = data.get('output_file')

# Paths are relative to /app/media inside container
base_path = "/app/media"
input_path = os.path.join(base_path, input_rel)
output_path = os.path.join(base_path, output_rel)

print(f"Repairing {input_path} -> {output_path}")

# clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import STL
if not os.path.exists(input_path):
    raise FileNotFoundError(f"Input file not found: {input_path}")

try:
    bpy.ops.import_mesh.stl(filepath=input_path)
except Exception as e:
    print(f"Error importing STL: {e}")
    # Try alternate import if needed?
    raise

obj = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = obj

# Go to edit mode
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

# Remove doubles (merge by distance)
bpy.ops.mesh.remove_doubles(threshold=0.0001)

# NOTE: Do NOT fill holes - we intentionally have holes for connectors!
# bpy.ops.mesh.fill_holes(sides=4)

# Recalculate normals
bpy.ops.mesh.normals_make_consistent(inside=False)

# Triangulate
bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

# Back to object mode
bpy.ops.object.mode_set(mode='OBJECT')

# Export STL
if not os.path.exists(os.path.dirname(output_path)):
    os.makedirs(os.path.dirname(output_path))

bpy.ops.export_mesh.stl(filepath=output_path, use_selection=True)

print("Repair complete")
