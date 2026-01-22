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

def create_connector_shape(position, normal, diameter, depth, centered=False, profile='cylinder'):
    """Create a connector mesh at the given position aligned to normal.
    
    Args:
        position: [x, y, z] position for the connector
        normal: [x, y, z] direction the connector should point
        diameter: Width/diameter of the connector
        depth: Length/depth of the connector
        centered: If True, center on position; if False, offset so end is at position
        profile: Shape profile - 'cylinder', 'square', 'hexagon', or 'star'
    
    Returns:
        The created Blender object
    """
    from mathutils import Vector, Quaternion
    import math
    
    # Calculate rotation to align Z-up shape with target normal
    z_axis = Vector((0, 0, 1))
    target = Vector(normal).normalized()
    
    # Step 1: Create shape at ORIGIN (so rotations work correctly)
    if profile == 'square':
        # Create a cube/box at origin
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        shape = bpy.context.active_object
        # Scale to match dimensions (diameter x diameter x depth)
        shape.scale = (diameter, diameter, depth)
        
    elif profile == 'hexagon':
        # Create a cylinder with 6 vertices = hexagonal prism
        bpy.ops.mesh.primitive_cylinder_add(
            radius=diameter / 2,
            depth=depth,
            vertices=6,  # 6 sides = hexagon
            location=(0, 0, 0)
        )
        shape = bpy.context.active_object
        
    elif profile == 'star':
        # Create a star/cross shape by combining two boxes
        # First box: along X
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        box1 = bpy.context.active_object
        box1.scale = (diameter, diameter * 0.4, depth)
        
        # Second box: along Y  
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        box2 = bpy.context.active_object
        box2.scale = (diameter * 0.4, diameter, depth)
        
        # Apply scales to both boxes
        for obj in [box1, box2]:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Join the two boxes
        bpy.context.view_layer.objects.active = box1
        box2.select_set(True)
        box1.select_set(True)
        bpy.ops.object.join()
        shape = bpy.context.active_object
        
    else:  # Default: cylinder
        bpy.ops.mesh.primitive_cylinder_add(
            radius=diameter / 2,
            depth=depth,
            vertices=32,
            location=(0, 0, 0)
        )
        shape = bpy.context.active_object
    
    # Step 2: Apply any pending transforms (scale) to mesh data
    bpy.context.view_layer.objects.active = shape
    bpy.ops.object.select_all(action='DESELECT')
    shape.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Step 3: Apply rotation to align with target normal
    dot = z_axis.dot(target)
    if dot < -0.9999:
        # Nearly opposite (pointing down) - rotate 180 around X
        shape.rotation_euler = (math.pi, 0, 0)
    elif dot > 0.9999:
        # Same direction (pointing up) - no rotation needed
        pass
    else:
        # General case - use quaternion rotation
        rotation = z_axis.rotation_difference(target)
        shape.rotation_euler = rotation.to_euler()
    
    # Step 4: Apply rotation transform to mesh data
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    
    # Step 5: Calculate final position and move there
    pos = Vector(position)
    if not centered:
        # Offset backwards along normal so end is at position
        offset = target * (depth / 2)
        pos = pos - offset
    
    shape.location = pos
    
    return shape


# Keep old function name for backwards compatibility
def create_cylinder(position, normal, diameter, depth, centered=False):
    """Create a cylinder mesh at the given position aligned to normal.
    Backwards compatible wrapper for create_connector_shape.
    """
    return create_connector_shape(position, normal, diameter, depth, centered, profile='cylinder')

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
        profile = conn.get('profile', 'cylinder')  # Get profile shape
        
        log(f"Connector {i+1}/{len(connectors)}: {conn_type} ({profile}) at {position}")
        log(f"  Diameter: {diameter}, Depth: {depth}")
        
        conn_start = time.time()
        
        # Create connector shape tool
        # Pins should be centered (half in, half out)
        # Holes should be buried (starting at surface and going in)
        is_pin = (conn_type == 'pin')
        connector_shape = create_connector_shape(position, normal, diameter, depth, centered=is_pin, profile=profile)
        
        # Determine operation
        if conn_type == 'hole':
            operation = 'DIFFERENCE'
        else:  # pin
            operation = 'UNION'
        
        log(f"  Applying {operation} boolean...")
        
        success = False
        try:
            success = apply_boolean(mesh_obj, connector_shape, operation)
        except Exception as e:
            log(f"  WARNING: Boolean check failed: {e}")
        
        if success:
            log(f"  Boolean applied in {time.time() - conn_start:.2f}s")
            # Clean up connector shape
            bpy.data.objects.remove(connector_shape, do_unlink=True)
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
                    connector_shape.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_obj
                    
                    bpy.ops.object.join()
                    log("  Fallback join successful")
                    
                    # After join, connector_shape object is merged into 'mesh_obj'
                    # No need to remove it, it's gone/merged.
                    
                except Exception as ex:
                    log(f"  ERROR: Fallback join also failed: {ex}")
                    # Try to cleanup
                    if connector_shape in bpy.data.objects.values():
                        bpy.data.objects.remove(connector_shape, do_unlink=True)
            else:
                # For holes (Difference), we can't join. If it fails, we just don't have a hole.
                # Clean up connector shape
                bpy.data.objects.remove(connector_shape, do_unlink=True)
    
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
