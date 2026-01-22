"""
Slicer Advanced - Pure Blender Pipeline
Uses bmesh.ops.bisect_plane for reliable cut geometry detection.
"""
import bpy
import bmesh
import os
import json
import math
from mathutils import Vector, Matrix

def log(msg):
    print(f"[SlicerAdvanced] {msg}", flush=True)

def cleanup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_stl(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    bpy.ops.import_mesh.stl(filepath=path)
    obj = bpy.context.selected_objects[0]
    # Apply transforms so world == local
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def duplicate_object(obj):
    """Duplicate an object and return the new copy."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    return bpy.context.active_object


def bisect_object_bmesh(obj, plane_co, plane_no, clear_inner=False, clear_outer=True):
    """
    Bisect an object using bmesh.ops.bisect_plane.
    Returns the centroid of the cut boundary IN WORLD SPACE, or None if no cut occurred.
    """
    log(f"Bisecting {obj.name} at plane_co={plane_co}, plane_no={plane_no}")
    log(f"Object location: {obj.location}, matrix_world:\n{obj.matrix_world}")
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    
    # Collect all geometry
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    log(f"Pre-bisect: {len(bm.verts)} verts, {len(bm.faces)} faces")
    
    # Perform bisect
    result = bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        plane_co=plane_co,
        plane_no=plane_no,
        clear_inner=clear_inner,
        clear_outer=clear_outer
    )
    
    log(f"Post-bisect: {len(bm.verts)} verts, {len(bm.faces)} faces")
    
    # Get the newly created vertices on the cut boundary
    cut_verts = [elem for elem in result['geom_cut'] if isinstance(elem, bmesh.types.BMVert)]
    cut_edges = [elem for elem in result['geom_cut'] if isinstance(elem, bmesh.types.BMEdge)]
    
    log(f"geom_cut contains: {len(cut_verts)} verts, {len(cut_edges)} edges")
    
    centroid_world = None
    
    if cut_verts:
        # Calculate centroid in LOCAL space first
        centroid_local = sum((v.co.copy() for v in cut_verts), Vector()) / len(cut_verts)
        log(f"Cut centroid (LOCAL): {centroid_local}")
        
        # Convert to WORLD space
        centroid_world = obj.matrix_world @ centroid_local
        log(f"Cut centroid (WORLD): {centroid_world}")
        
        # Fill the cut hole
        if cut_edges:
            try:
                bmesh.ops.contextual_create(bm, geom=cut_edges)
                log("Filled cut hole successfully")
            except Exception as e:
                log(f"Warning: Could not fill cut with contextual_create: {e}")
                try:
                    bmesh.ops.triangle_fill(bm, edges=cut_edges)
                    log("Filled cut hole with triangle_fill")
                except Exception as e2:
                    log(f"Warning: triangle_fill also failed: {e2}")
    else:
        log("WARNING: No cut vertices found in geom_cut!")
    
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Check if object has geometry
    if len(obj.data.vertices) == 0:
        log(f"Object {obj.name} has no vertices after bisect")
        return None, False
    
    log(f"Object {obj.name} has {len(obj.data.vertices)} vertices after bisect")
    return centroid_world, True


def add_connector(obj, position, normal, connector_type, params):
    """
    Add a pin or hole connector to an object at the specified position.
    Uses proper rotation handling to avoid position drift.
    """
    diameter = params.get('diameter', 5.0)
    depth = params.get('depth', 10.0)
    clearance = params.get('clearance', 0.2) if connector_type == 'hole' else 0.0
    
    actual_diameter = diameter + clearance
    
    log(f"=== ADD CONNECTOR ===")
    log(f"Object: {obj.name}")
    log(f"Type: {connector_type}")
    log(f"Input position: {position}")
    log(f"Normal: {normal}")
    log(f"Diameter: {actual_diameter}, Depth: {depth}")
    
    # Log object bounds for context
    bbox = [obj.matrix_world @ Vector(b) for b in obj.bound_box]
    min_b = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
    max_b = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
    log(f"Object bounds: min={min_b}, max={max_b}")
    
    # Calculate rotation to align cylinder with target normal
    up = Vector((0, 0, 1))
    target = Vector(normal).normalized()
    
    # Use rotation_difference for clean quaternion rotation
    quat = up.rotation_difference(target)
    
    # Create cylinder at origin first
    bpy.ops.mesh.primitive_cylinder_add(
        radius=actual_diameter / 2,
        depth=depth,
        vertices=32,
        location=(0, 0, 0)
    )
    cylinder = bpy.context.active_object
    
    # Apply rotation (before setting position!)
    cylinder.rotation_euler = quat.to_euler()
    
    # Calculate final position
    # For holes: center the cylinder depth INTO the part
    # For pins: center the cylinder so half sticks out
    if connector_type == 'hole':
        # Move cylinder so it starts at the surface and goes inward
        offset = target * (depth / 2)
        final_pos = Vector(position) - offset
    else:
        # Pin: centered at position (half in, half out)
        final_pos = Vector(position)
    
    log(f"Final cylinder position: {final_pos}")
    cylinder.location = final_pos
    
    # Apply transforms to avoid issues with boolean
    bpy.ops.object.select_all(action='DESELECT')
    cylinder.select_set(True)
    bpy.context.view_layer.objects.active = cylinder
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    
    # Perform boolean operation
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    bool_op = 'UNION' if connector_type == 'pin' else 'DIFFERENCE'
    
    try:
        mod = obj.modifiers.new(name="Connector", type='BOOLEAN')
        mod.operation = bool_op
        mod.object = cylinder
        mod.solver = 'FAST'
        bpy.ops.object.modifier_apply(modifier="Connector")
        log(f"Boolean {bool_op} successful")
    except Exception as e:
        log(f"Boolean failed: {e}")
        if connector_type == 'pin':
            # Fallback: join objects
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            cylinder.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.join()
            log("Fallback: joined pin to object")
            return
    
    # Clean up cylinder
    if cylinder.name in bpy.data.objects:
        bpy.data.objects.remove(cylinder, do_unlink=True)


def slice_and_connect(obj, grid_config, joint_params):
    """
    Main slicing function. Slices object according to grid and adds connectors.
    Returns list of resulting part objects.
    """
    add_connectors = joint_params.get('diameter', 0) > 0
    
    # Get object bounds
    bbox = [obj.matrix_world @ Vector(b) for b in obj.bound_box]
    min_vec = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
    max_vec = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
    size = max_vec - min_vec
    
    log(f"Object bounds: min={min_vec}, max={max_vec}, size={size}")
    
    parts = [obj]
    
    # Process each axis
    axes = [('x', 0), ('y', 1), ('z', 2)]
    
    for axis_name, axis_idx in axes:
        num_sections = grid_config.get(axis_name, 1)
        if num_sections <= 1:
            continue
        
        # Calculate cut positions
        start = min_vec[axis_idx]
        step = size[axis_idx] / num_sections
        cut_positions = [start + step * i for i in range(1, num_sections)]
        
        log(f"Axis {axis_name}: {len(cut_positions)} cuts at {cut_positions}")
        
        # Process each cut
        for cut_pos in cut_positions:
            new_parts = []
            
            plane_co = Vector((0, 0, 0))
            plane_co[axis_idx] = cut_pos
            
            plane_no = Vector((0, 0, 0))
            plane_no[axis_idx] = 1.0
            
            for part in parts:
                # Duplicate for the "positive" side
                part_b = duplicate_object(part)
                part_a = part  # Original becomes "negative" side
                
                # Bisect part_a (keep negative side)
                centroid_a, valid_a = bisect_object_bmesh(
                    part_a, plane_co, plane_no,
                    clear_inner=False, clear_outer=True
                )
                
                # Bisect part_b (keep positive side)
                centroid_b, valid_b = bisect_object_bmesh(
                    part_b, plane_co, plane_no,
                    clear_inner=True, clear_outer=False
                )
                
                log(f"Cut result: A valid={valid_a}, B valid={valid_b}")
                
                # Collect valid parts
                if valid_a:
                    new_parts.append(part_a)
                else:
                    bpy.data.objects.remove(part_a, do_unlink=True)
                
                if valid_b:
                    new_parts.append(part_b)
                else:
                    bpy.data.objects.remove(part_b, do_unlink=True)
                
                # Add connectors if both parts valid and we have a centroid
                if add_connectors and valid_a and valid_b and centroid_a is not None:
                    log(f"Adding connectors at centroid: {centroid_a}")
                    
                    # Part A (negative side) gets HOLE
                    # Face normal on A points in +plane_no direction
                    add_connector(part_a, centroid_a, plane_no, 'hole', joint_params)
                    
                    # Part B (positive side) gets PIN  
                    # Face normal on B points in -plane_no direction
                    add_connector(part_b, centroid_a, -plane_no, 'pin', joint_params)
            
            parts = new_parts
    
    return parts


# =============================================================================
# Main Execution
# =============================================================================
try:
    log("Starting Slicer Advanced v2 (bmesh.ops approach)")
    
    data = request_data
    input_file = data.get('input_file')
    output_dir_rel = data.get('output_dir')
    base_name = data.get('base_name', 'slice')
    params = data.get('params', {})
    
    # Resolve paths
    base_path = "/app/media"
    
    def resolve(p):
        if not p:
            return None
        if p.startswith("/"):
            return p
        return os.path.join(base_path, p)
    
    input_path = resolve(input_file)
    output_dir = resolve(output_dir_rel)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    cleanup_scene()
    obj = import_stl(input_path)
    
    grid = params.get('grid', {'x': 1, 'y': 1, 'z': 1})
    joint_params = params.get('joint_params', {})
    
    log(f"Grid config: {grid}")
    log(f"Joint params: {joint_params}")
    
    # Perform slicing with connectors
    parts = slice_and_connect(obj, grid, joint_params)
    
    log(f"Slicing complete. {len(parts)} parts created.")
    
    # Export parts
    output_files = []
    for i, part in enumerate(parts):
        bpy.ops.object.select_all(action='DESELECT')
        part.select_set(True)
        bpy.context.view_layer.objects.active = part
        
        # Reset origin to geometry center for clean export
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        
        fname = f"{base_name}_part_{i+1}.stl"
        fpath = os.path.join(output_dir, fname)
        
        bpy.ops.export_mesh.stl(filepath=fpath, use_selection=True)
        
        output_files.append({
            "filepath": os.path.join(output_dir_rel, fname),
            "filename": fname
        })
        log(f"Exported: {fname}")
    
    # Write manifest
    manifest_path = os.path.join(output_dir, f"{base_name}_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(output_files, f)
    
    log(f"Manifest written to {manifest_path}")
    log("Slicer Advanced v2 complete!")

except Exception as e:
    log(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise e
