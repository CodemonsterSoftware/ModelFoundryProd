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

SHAPE_VERTICES = {
    'circle': 32,
    'square': 4,
    'triangle': 3,
    'hexagon': 6,
}

def create_pyramid(position, normal, edge_length, height, tolerance=0.0, double_sided=False, for_socket=True):
    """Create a square-base pyramid mesh for tenon/socket operations.
    
    For socket cutting (for_socket=True):
      - Base is at the surface (position)
      - Tip extends INTO the part (opposite of normal)
      - Normal points toward mating part (outward from this part)
    
    Args:
        position: [x, y, z] center position at surface
        normal: [nx, ny, nz] direction toward mating part (outward)
        edge_length: Length of square base edge
        height: Height from base to tip
        tolerance: Gap to add for socket cutters (0 for exact fit pins)
        double_sided: If True, create octahedron (double pyramid) for printable tenon
        for_socket: If True, orient for boolean subtraction (tip goes into part)
    """
    import bmesh
    from mathutils import Vector
    import math
    
    # Apply tolerance to dimensions
    actual_edge = edge_length + tolerance
    actual_height = height + (tolerance / 2) if tolerance > 0 else height
    
    bm = bmesh.new()
    
    # Half edge length for vertex positioning
    w = actual_edge / 2
    
    if double_sided:
        # Double-sided pyramid (octahedron) for printable tenon
        # Tips at +height and -height from center
        verts = [
            bm.verts.new((0, 0, actual_height)),      # Top tip
            bm.verts.new((0, 0, -actual_height)),     # Bottom tip
            bm.verts.new((-w, -w, 0)),                # Base corners
            bm.verts.new((w, -w, 0)),
            bm.verts.new((w, w, 0)),
            bm.verts.new((-w, w, 0)),
        ]
        
        # Faces connecting tips to base (8 triangles)
        faces = [
            (0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 2),  # Top half
            (1, 3, 2), (1, 4, 3), (1, 5, 4), (1, 2, 5),  # Bottom half
        ]
    else:
        # Single pyramid for socket cutter
        # For socket: base at Z=0 (surface), tip at Z=-height (into part)
        # The pyramid will be rotated so that Z aligns with -normal (into part)
        verts = [
            bm.verts.new((0, 0, -actual_height)),     # Tip (pointing down = into part after rotation)
            bm.verts.new((-w, -w, 0)),                # Base corners at Z=0 (surface)
            bm.verts.new((w, -w, 0)),
            bm.verts.new((w, w, 0)),
            bm.verts.new((-w, w, 0)),
        ]
        
        # Faces: 4 triangles + 1 base quad
        faces = [
            (0, 2, 1), (0, 3, 2), (0, 4, 3), (0, 1, 4),  # Sides (reversed winding for inward tip)
            (1, 2, 3, 4),  # Base (quad)
        ]
    
    # Create faces
    for face_indices in faces:
        try:
            bm.faces.new([verts[i] for i in face_indices])
        except Exception:
            pass  # Face may already exist
    
    bm.normal_update()
    
    # Create mesh
    mesh = bpy.data.meshes.new("TenonPyramid")
    bm.to_mesh(mesh)
    bm.free()
    
    # Create object
    obj = bpy.data.objects.new("TenonPyramid", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Position and rotate to align with normal
    z_axis = Vector((0, 0, 1))
    target_normal = Vector(normal).normalized()
    pos = Vector(position)
    
    # For socket cutting, we need to position the pyramid so:
    # - The base (Z=0 in local coords) sits at the surface
    # - The tip (Z=-height in local coords) extends INTO the part
    # Since our pyramid's Z- points into the part, we align local Z+ with the outward normal
    # This makes Z- point INTO the part, which is what we want
    
    obj.location = pos
    
    # Calculate rotation to align local Z+ with the outward normal
    dot = z_axis.dot(target_normal)
    if dot < -0.9999:
        # Normal points straight down (-Z)
        obj.rotation_euler = (math.pi, 0, 0)
    elif dot > 0.9999:
        # Normal points straight up (+Z) - no rotation
        pass
    else:
        # General case - use quaternion rotation
        rotation = z_axis.rotation_difference(target_normal)
        obj.rotation_euler = rotation.to_euler()
    
    return obj

def create_cylinder(position, normal, diameter, depth, centered=False, shape='circle'):
    """Create a cylinder/prism mesh at the given position aligned to normal.
    
    IMPORTANT: We must set rotation BEFORE setting position, because
    applying rotation to matrix_world also rotates the position!
    
    Args:
        shape: 'circle', 'square', 'triangle', or 'hexagon'
    """
    from mathutils import Vector, Quaternion
    import math
    
    # Get vertex count for shape
    vertices = SHAPE_VERTICES.get(shape.lower(), 32)
    
    # Calculate rotation to align Z-up cylinder with target normal
    z_axis = Vector((0, 0, 1))
    target = Vector(normal).normalized()
    
    # Calculate final position FIRST (before creating cylinder)
    # Cylinders are created with center at `location`, so we need to offset
    # to position them correctly relative to the surface.
    pos = Vector(position)
    
    if centered:
        # For pins (centered): keep at position so half sticks out, half is in
        # The normal points toward the mating part (where pin should stick out)
        pass  # No offset needed - pin center at surface
    else:
        # For holes: position cylinder so it extends INTO the part from the surface
        # CRITICAL: The 'normal' points TOWARD the mating part (outward from this part)
        # But we need the hole to extend INWARD (opposite of normal)
        # 
        # We want the cylinder to:
        #   - Start 0.5mm OUTSIDE the surface (overlap for clean boolean cut)
        #   - Extend fully INTO the part (opposite of normal direction)
        #
        # So we move the cylinder CENTER in the NEGATIVE normal direction
        overlap = 0.5  # Small overlap to ensure clean surface cut
        # Move inward (opposite of normal) by (depth/2 - overlap)
        # This puts outer end 0.5mm outside surface, inner end (depth - 0.5) inside
        offset = target * ((depth / 2) - overlap)
        pos = pos - offset  # SUBTRACT to go opposite of normal (into the part)
    
    # Create cylinder at the FINAL position directly
    # (avoiding the origin-then-move approach which was causing issues)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2,
        depth=depth,
        vertices=vertices,
        location=pos
    )
    cylinder = bpy.context.active_object
    
    # Now apply rotation if needed (rotation around the cylinder's own center)
    dot = z_axis.dot(target)
    if dot < -0.9999:
        # Nearly opposite (pointing down) - rotate 180 around X
        cylinder.rotation_euler = (math.pi, 0, 0)
    elif dot > 0.9999:
        # Same direction (pointing up) - no rotation needed
        pass
    else:
        # General case - use quaternion rotation
        rotation = z_axis.rotation_difference(target)
        cylinder.rotation_euler = rotation.to_euler()
    
    return cylinder

def apply_boolean(target_obj, tool_obj, operation):
    """Apply boolean modifier to target using tool object.
    
    Returns True only if the boolean was applied AND the mesh actually changed.
    Silent failures (modifier applied but no geometric change) return False.
    """
    # Make sure target is active
    bpy.context.view_layer.objects.active = target_obj
    target_obj.select_set(True)
    
    # Record mesh state BEFORE boolean
    bpy.context.view_layer.update()
    before_verts = len(target_obj.data.vertices)
    before_faces = len(target_obj.data.polygons)
    
    # Add boolean modifier
    bool_mod = target_obj.modifiers.new(name='Connector', type='BOOLEAN')
    bool_mod.operation = operation  # 'DIFFERENCE' or 'UNION'
    bool_mod.object = tool_obj
    bool_mod.solver = 'FAST'  # FAST solver is more forgiving on non-manifold meshes
    
    # Apply modifier
    try:
        bpy.ops.object.modifier_apply(modifier='Connector')
    except Exception as e:
        # If application fails, remove modifier
        if bool_mod.name in target_obj.modifiers:
            target_obj.modifiers.remove(bool_mod)
        log(f"  Boolean modifier apply failed: {e}")
        return False
    
    # Verify mesh actually changed (detect silent failures)
    bpy.context.view_layer.update()
    after_verts = len(target_obj.data.vertices)
    after_faces = len(target_obj.data.polygons)
    
    # Check if geometry changed significantly
    verts_changed = abs(after_verts - before_verts) > 0
    faces_changed = abs(after_faces - before_faces) > 0
    
    if not verts_changed and not faces_changed:
        log(f"  WARNING: Boolean operation had no effect (verts: {before_verts}, faces: {before_faces})")
        return False
    
    log(f"  Mesh changed: verts {before_verts}->{after_verts}, faces {before_faces}->{after_faces}")
    return True

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
    
    # Track connector results for manifest
    connector_results = []
    
    # Process each connector
    for i, conn in enumerate(connectors):
        conn_type = conn.get('type', 'hole')
        position = conn.get('position', [0, 0, 0])
        normal = conn.get('normal', [0, 0, 1])
        diameter = conn.get('diameter', 5.0)
        depth = conn.get('depth', 10.0)
        shape = conn.get('shape', 'circle')  # Shape support
        
        # Tenon-specific parameters
        edge_length = conn.get('edge_length', 12.0)
        tolerance = conn.get('tolerance', 0.2)
        
        log(f"Connector {i+1}/{len(connectors)}: {conn_type} at {position}")
        
        conn_start = time.time()
        
        # Handle different connector types
        if conn_type == 'tenon_socket':
            # Tenon socket: cut pyramid-shaped hole with tolerance
            log(f"  Edge: {edge_length}, Height: {depth}, Tolerance: {tolerance}")
            tool = create_pyramid(position, normal, edge_length, depth, tolerance=tolerance, double_sided=False)
            operation = 'DIFFERENCE'
        elif conn_type == 'tenon_pin':
            # Tenon pin: add double-sided pyramid (printable insert)
            log(f"  Edge: {edge_length}, Height: {depth}")
            tool = create_pyramid(position, normal, edge_length, depth, tolerance=0, double_sided=True)
            operation = 'UNION'
        else:
            # Standard cylindrical connectors (hole/pin)
            log(f"  Diameter: {diameter}, Depth: {depth}, Shape: {shape}")
            is_pin = (conn_type == 'pin')
            tool = create_cylinder(position, normal, diameter, depth, centered=is_pin, shape=shape)
            
            if conn_type == 'hole':
                operation = 'DIFFERENCE'
            else:  # pin
                operation = 'UNION'
        
        log(f"  Applying {operation} boolean...")
        
        success = False
        try:
            success = apply_boolean(mesh_obj, tool, operation)
        except Exception as e:
            log(f"  WARNING: Boolean check failed: {e}")
        
        # Track result for this connector
        conn_result = {
            'index': i,
            'type': conn_type,
            'position': position,
            'failed': not success
        }
        
        if success:
            log(f"  Boolean applied in {time.time() - conn_start:.2f}s")
            # Clean up tool object
            bpy.data.objects.remove(tool, do_unlink=True)
        else:
            log(f"  WARNING: Boolean failed for {conn_type}")
            
            # Fallback for PINS/UNIONS: Just join the meshes
            # This creates a single object with intersecting geometry (multi-shell).
            # Slicers handle this fine.
            if operation == 'UNION':
                log("  FALLBACK: Joining to mesh (multi-shell)...")
                try:
                    # Select both
                    bpy.ops.object.select_all(action='DESELECT')
                    mesh_obj.select_set(True)
                    tool.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_obj
                    
                    bpy.ops.object.join()
                    log("  Fallback join successful")
                    
                    # After join, 'tool' object is merged into 'mesh_obj'
                    # No need to remove tool, it's gone/merged.
                    
                except Exception as ex:
                    log(f"  ERROR: Fallback join also failed: {ex}")
                    # Try to cleanup
                    if tool in bpy.data.objects.values():
                        bpy.data.objects.remove(tool, do_unlink=True)
            else:
                # For holes (Difference), we can't join. If it fails, we just don't have a hole.
                # Clean up tool
                bpy.data.objects.remove(tool, do_unlink=True)
        
        connector_results.append(conn_result)
    
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
    
    # Write connector results manifest
    failed_count = sum(1 for r in connector_results if r.get('failed', False))
    manifest_path = output_path.replace('.stl', '_manifest.json')
    manifest_data = {
        'connectors': connector_results,
        'total': len(connector_results),
        'failed': failed_count
    }
    
    import json
    with open(manifest_path, 'w') as f:
        json.dump(manifest_data, f)
    log(f"Manifest written to: {manifest_path}")
    if failed_count > 0:
        log(f"WARNING: {failed_count} connector(s) FAILED")
    
    log(f"=== CONNECTOR OPERATION COMPLETE ===")
    log(f"Output size: {output_size:.2f} MB")
    log(f"Total time: {total_time:.2f}s")

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e
