import bpy
import os
import sys
import math
import time

# This script runs in BLENDER's python
# It adds connectors (holes or pins) to a mesh using boolean operations

# Expected global variables from server.py execution context:
# request_data = {
#     "input_file": "path/to/mesh.stl",
#     "output_file": "path/to/output.stl",
#     "params": {
#         "connectors": [
#             {
#                 "position": [x, y, z],
#                 "normal": [nx, ny, nz],
#                 "diameter": 5.0,
#                 "depth": 10.0,
#                 "type": "hole" | "pin"
#             },
#             ...
#         ]
#     }
# }

def log(msg):
    print(f"[Connectors] {msg}", flush=True)

def get_file_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

def create_cylinder(position, normal, diameter, depth, centered=False):
    """Create a cylinder mesh at the given position aligned to normal.
    
    IMPORTANT: We must set rotation BEFORE setting position, because
    applying rotation to matrix_world also rotates the position!
    """
    from mathutils import Vector
    
    # Calculate rotation to align Z-up cylinder with target normal
    z_axis = Vector((0, 0, 1))
    target = Vector(normal).normalized()
    
    # Calculate the rotation quaternion
    if z_axis.dot(target) < -0.9999:
        # Nearly opposite - rotate 180 around X axis
        rotation = z_axis.rotation_difference(-z_axis)
        rotation = (1, 0, 0, 0)  # 180 deg around any perpendicular
    elif z_axis.dot(target) > 0.9999:
        # Same direction - no rotation needed
        rotation = (1, 0, 0, 0)  # Identity quaternion
    else:
        rotation = z_axis.rotation_difference(target)
    
    # Calculate final position
    # For holes: offset so the cylinder is buried into the part
    # For pins (centered): keep at position so half sticks out
    pos = Vector(position)
    if not centered:
        # Offset backwards along normal so cylinder end is at position
        offset = target * (depth / 2)
        pos = pos - offset
    
    # Create cylinder at ORIGIN first (to avoid rotation issues)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2,
        depth=depth,
        vertices=32,
        location=(0, 0, 0)  # Create at origin
    )
    cylinder = bpy.context.active_object
    
    # Apply rotation FIRST (while at origin)
    if hasattr(rotation, 'to_euler'):
        cylinder.rotation_euler = rotation.to_euler()
    
    # NOW set the position (after rotation is applied)
    cylinder.location = pos
    
    return cylinder

def apply_boolean(target_obj, tool_obj, operation):
    """Apply boolean modifier to target using tool object."""
    # Make sure target is active
    bpy.context.view_layer.objects.active = target_obj
    target_obj.select_set(True)
    
    # Add boolean modifier
    bool_mod = target_obj.modifiers.new(name='Connector', type='BOOLEAN')
    bool_mod.operation = operation  # 'DIFFERENCE' or 'UNION'
    bool_mod.object = tool_obj
    bool_mod.solver = 'FAST'  # FAST solver is more forgiving on non-manifold meshes
    
    # Apply modifier
    try:
        bpy.ops.object.modifier_apply(modifier='Connector')
        return True
    except Exception as e:
        # If application fails, remove modifier
        if bool_mod in target_obj.modifiers:
            target_obj.modifiers.remove(bool_mod)
        return False

try:
    start_time = time.time()
    
    data = request_data
    input_rel = data.get('input_file')
    output_rel = data.get('output_file')
    params = data.get('params', {})
    
    connectors = params.get('connectors', [])

    # Paths are relative to /app/media inside container
    base_path = "/app/media"
    
    # Resolve absolute paths
    if input_rel and not input_rel.startswith("/"):
        input_path = os.path.join(base_path, input_rel)
    else:
        input_path = input_rel
        
    if output_rel and not output_rel.startswith("/"):
        output_path = os.path.join(base_path, output_rel)
    else:
        output_path = output_rel

    log(f"=== CONNECTOR OPERATION STARTED ===")
    log(f"Input: {input_path}")
    log(f"Output: {output_path}")
    log(f"Connectors to add: {len(connectors)}")

    # Reset scene
    log("Resetting Blender scene...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Import STL
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    input_size = get_file_size_mb(input_path)
    log(f"Importing STL ({input_size:.2f} MB)...")
    import_start = time.time()
    bpy.ops.import_mesh.stl(filepath=input_path)
    log(f"  Import completed in {time.time() - import_start:.2f}s")
    
    # Get imported mesh
    mesh_obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = mesh_obj
    
    initial_faces = len(mesh_obj.data.polygons)
    log(f"  Mesh has {initial_faces:,} faces")
    
    # Process each connector
    for i, conn in enumerate(connectors):
        conn_type = conn.get('type', 'hole')
        position = conn.get('position', [0, 0, 0])
        normal = conn.get('normal', [0, 0, 1])
        diameter = conn.get('diameter', 5.0)
        depth = conn.get('depth', 10.0)
        
        log(f"Connector {i+1}/{len(connectors)}: {conn_type} at {position}")
        log(f"  Diameter: {diameter}, Depth: {depth}")
        
        conn_start = time.time()
        
        # Create cylinder tool
        # Pins should be centered (half in, half out)
        # Holes should be buried (starting at surface and going in)
        is_pin = (conn_type == 'pin')
        cylinder = create_cylinder(position, normal, diameter, depth, centered=is_pin)
        
        # Determine operation
        if conn_type == 'hole':
            operation = 'DIFFERENCE'
        else:  # pin
            operation = 'UNION'
        
        log(f"  Applying {operation} boolean...")
        
        success = False
        try:
            success = apply_boolean(mesh_obj, cylinder, operation)
        except Exception as e:
            log(f"  WARNING: Boolean check failed: {e}")
        
        if success:
            log(f"  Boolean applied in {time.time() - conn_start:.2f}s")
            # Clean up cylinder
            bpy.data.objects.remove(cylinder, do_unlink=True)
        else:
            log(f"  WARNING: Boolean failed for {conn_type}")
            
            # Fallback for PINS (Union): Just join the meshes
            # This creates a single object with intersecting geometry (multi-shell).
            # Slicers handle this fine.
            if operation == 'UNION':
                log("  FALLBACK: Joining pin to mesh (multi-shell)...")
                try:
                    # Select both
                    bpy.ops.object.select_all(action='DESELECT')
                    mesh_obj.select_set(True)
                    cylinder.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_obj
                    
                    bpy.ops.object.join()
                    log("  Fallback join successful")
                    
                    # After join, 'cylinder' object is merged into 'mesh_obj'
                    # No need to remove cylinder, it's gone/merged.
                    
                except Exception as ex:
                    log(f"  ERROR: Fallback join also failed: {ex}")
                    # Try to cleanup
                    if cylinder in bpy.data.objects.values():
                        bpy.data.objects.remove(cylinder, do_unlink=True)
            else:
                # For holes (Difference), we can't join. If it fails, we just don't have a hole.
                # Clean up cylinder
                bpy.data.objects.remove(cylinder, do_unlink=True)
    
    # Report face count change
    final_faces = len(mesh_obj.data.polygons)
    log(f"Face count: {initial_faces:,} -> {final_faces:,} ({final_faces - initial_faces:+,})")
    
    # Export result
    log("Exporting result...")
    export_start = time.time()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Select mesh for export
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    
    bpy.ops.export_mesh.stl(filepath=output_path, use_selection=True, ascii=False)
    log(f"  Export completed in {time.time() - export_start:.2f}s")
    
    output_size = get_file_size_mb(output_path)
    total_time = time.time() - start_time
    
    log(f"=== CONNECTOR OPERATION COMPLETE ===")
    log(f"Output size: {output_size:.2f} MB")
    log(f"Total time: {total_time:.2f}s")

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e
