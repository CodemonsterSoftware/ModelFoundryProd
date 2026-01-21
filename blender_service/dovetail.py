import bpy
import bmesh
import os
import sys
import math
import time
from mathutils import Vector, Matrix

# This script runs in BLENDER's python
# Creates a TRUE DOVETAIL cutting plane with trapezoidal teeth

def log(msg):
    print(f"[Dovetail] {msg}", flush=True)

def get_file_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

def create_dovetail_cutter(center, width, height, depth, tooth_width, tooth_height, angle_deg, num_teeth):
    """
    Create a dovetail cutting volume with proper trapezoidal teeth.
    
    The profile looks like:
        ___     ___     ___
       /   \   /   \   /   \
      /     \_/     \_/     \
    
    Args:
        center: Center point of the cutting plane
        width: Width of cutter (X direction - along the cut)
        height: Height of cutter (Y direction - perpendicular to cut)
        depth: How deep the cutter extends below the plane (Z direction)
        tooth_width: Width of each tooth at the base
        tooth_height: Height of tooth peaks above the baseline
        angle_deg: Angle of the dovetail sides (e.g., 60 degrees = 30 deg from vertical)
        num_teeth: Number of teeth
    """
    log(f"Creating dovetail cutter at {center}")
    log(f"  Size: {width}x{height}x{depth}")
    log(f"  Teeth: {num_teeth}, width={tooth_width}mm, height={tooth_height}mm, angle={angle_deg}°")
    
    # Calculate the dovetail geometry
    # The angle is the included angle of the dovetail (e.g., 60° means 30° from vertical on each side)
    half_angle = math.radians(angle_deg / 2)
    
    # How much the tooth widens as it goes up
    # If tooth_height is the vertical rise, the horizontal offset at top is:
    offset = tooth_height * math.tan(half_angle)
    
    # Create mesh
    mesh = bpy.data.meshes.new('DovetailCutter')
    obj = bpy.data.objects.new('DovetailCutter', mesh)
    bpy.context.collection.objects.link(obj)
    
    bm = bmesh.new()
    
    half_w = width / 2
    half_h = height / 2
    
    # Calculate positions along Y axis for the dovetail profile
    # Each tooth cycle: flat base -> angled rise -> flat top -> angled fall -> flat base
    
    # Space teeth evenly
    if num_teeth < 1:
        num_teeth = 1
    
    tooth_spacing = height / num_teeth
    gap_width = (tooth_spacing - tooth_width) / 2  # Gap between teeth
    
    if gap_width < 0:
        log(f"  Warning: teeth too wide, adjusting")
        tooth_width = tooth_spacing * 0.7
        gap_width = (tooth_spacing - tooth_width) / 2
    
    # Half-widths at base and top of tooth
    half_base = tooth_width / 2
    half_top = half_base + offset  # Wider at top (classic dovetail)
    
    log(f"  Tooth base half-width: {half_base:.1f}, top half-width: {half_top:.1f}")
    
    # Generate profile points
    y_positions = []
    z_heights = []
    
    y = -half_h
    
    for t in range(num_teeth):
        tooth_center = -half_h + (t + 0.5) * tooth_spacing
        
        # Flat section before tooth (at z=0)
        if t == 0:
            y_positions.append(-half_h)
            z_heights.append(0)
        
        # Start of tooth base
        y_positions.append(tooth_center - half_base)
        z_heights.append(0)
        
        # Top left of tooth (angled up, wider)
        y_positions.append(tooth_center - half_top)
        z_heights.append(tooth_height)
        
        # Top right of tooth
        y_positions.append(tooth_center + half_top)
        z_heights.append(tooth_height)
        
        # End of tooth base (angled down)
        y_positions.append(tooth_center + half_base)
        z_heights.append(0)
        
        # Flat section after tooth
        if t == num_teeth - 1:
            y_positions.append(half_h)
            z_heights.append(0)
    
    n_points = len(y_positions)
    log(f"  Profile has {n_points} points")
    
    # Create vertices
    # Front face (x = -half_w)
    front_bottom = []
    front_top = []
    for i in range(n_points):
        v_bot = bm.verts.new((-half_w, y_positions[i], -depth))
        v_top = bm.verts.new((-half_w, y_positions[i], z_heights[i]))
        front_bottom.append(v_bot)
        front_top.append(v_top)
    
    # Back face (x = +half_w)
    back_bottom = []
    back_top = []
    for i in range(n_points):
        v_bot = bm.verts.new((half_w, y_positions[i], -depth))
        v_top = bm.verts.new((half_w, y_positions[i], z_heights[i]))
        back_bottom.append(v_bot)
        back_top.append(v_top)
    
    bm.verts.ensure_lookup_table()
    
    # Create faces
    for i in range(n_points - 1):
        # Top face (dovetail surface)
        try:
            bm.faces.new([front_top[i], back_top[i], back_top[i+1], front_top[i+1]])
        except:
            pass
        
        # Bottom face (flat)
        try:
            bm.faces.new([front_bottom[i], front_bottom[i+1], back_bottom[i+1], back_bottom[i]])
        except:
            pass
        
        # Front face
        try:
            bm.faces.new([front_bottom[i], front_top[i], front_top[i+1], front_bottom[i+1]])
        except:
            pass
        
        # Back face
        try:
            bm.faces.new([back_bottom[i], back_bottom[i+1], back_top[i+1], back_top[i]])
        except:
            pass
    
    # End caps
    try:
        bm.faces.new([front_bottom[0], back_bottom[0], back_top[0], front_top[0]])
    except:
        pass
    try:
        bm.faces.new([front_bottom[-1], front_top[-1], back_top[-1], back_bottom[-1]])
    except:
        pass
    
    bm.to_mesh(mesh)
    bm.free()
    
    # Recalculate normals
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Position at center
    obj.location = Vector(center)
    
    log(f"  Cutter has {len(mesh.polygons)} faces")
    
    return obj

try:
    start_time = time.time()
    
    data = request_data
    input_rel = data.get('input_file')
    output_rel = data.get('output_file')
    params = data.get('params', {})
    
    output_b_rel = params.get('output_file_b', output_rel.replace('.stl', '_B.stl'))
    plane_origin = params.get('plane_origin', [0, 0, 0])
    tooth_height = params.get('dovetail_height', 8.0)
    tooth_width = params.get('dovetail_width', 15.0)
    angle_deg = params.get('dovetail_angle', 60.0)  # Classic dovetail angle
    num_teeth = params.get('num_teeth', 3)
    extents = params.get('mesh_extents', [100, 100])
    depth = params.get('cut_depth', 50.0)

    # Paths
    base_path = "/app/media"
    if input_rel and not input_rel.startswith("/"):
        input_path = os.path.join(base_path, input_rel)
    else:
        input_path = input_rel
        
    if output_rel and not output_rel.startswith("/"):
        output_path_a = os.path.join(base_path, output_rel)
    else:
        output_path_a = output_rel
        
    if output_b_rel and not output_b_rel.startswith("/"):
        output_path_b = os.path.join(base_path, output_b_rel)
    else:
        output_path_b = output_b_rel

    log(f"=== DOVETAIL CUT STARTED ===")
    log(f"Input: {input_path}")
    log(f"Output A: {output_path_a}")
    log(f"Output B: {output_path_b}")

    # Reset scene
    log("Resetting Blender scene...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Import STL
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    log(f"Importing STL ({get_file_size_mb(input_path):.2f} MB)...")
    bpy.ops.import_mesh.stl(filepath=input_path)
    
    mesh_obj = bpy.context.selected_objects[0]
    mesh_obj.name = 'OriginalMesh'
    initial_faces = len(mesh_obj.data.polygons)
    log(f"  Mesh has {initial_faces:,} faces")
    
    # Create dovetail cutter
    cutter_width = extents[0]
    cutter_height = extents[1]
    cutter_center = list(plane_origin)
    
    log("Creating dovetail cutter...")
    cutter = create_dovetail_cutter(
        cutter_center, 
        cutter_width, 
        cutter_height, 
        depth,
        tooth_width,
        tooth_height,
        angle_deg,
        num_teeth
    )
    
    # Create copy of mesh for second piece
    log("Duplicating mesh for piece B...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.duplicate()
    mesh_obj_b = bpy.context.active_object
    mesh_obj_b.name = 'MeshB'
    
    # Apply boolean DIFFERENCE to first mesh
    log("Applying DIFFERENCE boolean to piece A...")
    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    
    bool_mod = mesh_obj.modifiers.new(name='DovetailCut', type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    bool_mod.solver = 'EXACT'
    
    try:
        bpy.ops.object.modifier_apply(modifier='DovetailCut')
        log(f"  Piece A now has {len(mesh_obj.data.polygons):,} faces")
    except Exception as e:
        log(f"  ERROR applying boolean to A: {e}")
    
    # Apply boolean INTERSECT to second mesh
    log("Applying INTERSECT boolean to piece B...")
    bpy.context.view_layer.objects.active = mesh_obj_b
    mesh_obj_b.select_set(True)
    
    bool_mod = mesh_obj_b.modifiers.new(name='DovetailCut', type='BOOLEAN')
    bool_mod.operation = 'INTERSECT'
    bool_mod.object = cutter
    bool_mod.solver = 'EXACT'
    
    try:
        bpy.ops.object.modifier_apply(modifier='DovetailCut')
        log(f"  Piece B now has {len(mesh_obj_b.data.polygons):,} faces")
    except Exception as e:
        log(f"  ERROR applying boolean to B: {e}")
    
    # Export piece A
    log(f"Exporting piece A...")
    os.makedirs(os.path.dirname(output_path_a), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.export_mesh.stl(filepath=output_path_a, use_selection=True, ascii=False)
    
    # Export piece B
    log(f"Exporting piece B...")
    os.makedirs(os.path.dirname(output_path_b), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj_b.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj_b
    bpy.ops.export_mesh.stl(filepath=output_path_b, use_selection=True, ascii=False)
    
    # Export cutter for debugging
    debug_cutter_path = os.path.join(base_path, "debug_dovetail_cutter.stl")
    bpy.ops.object.select_all(action='DESELECT')
    cutter.select_set(True)
    bpy.context.view_layer.objects.active = cutter
    bpy.ops.export_mesh.stl(filepath=debug_cutter_path, use_selection=True, ascii=False)
    log(f"  Debug: Exported cutter to {debug_cutter_path}")
    
    # Clean up
    bpy.data.objects.remove(cutter, do_unlink=True)
    
    total_time = time.time() - start_time
    log(f"=== DOVETAIL CUT COMPLETE ===")
    log(f"Piece A: {get_file_size_mb(output_path_a):.2f} MB, {len(mesh_obj.data.polygons):,} faces")
    log(f"Piece B: {get_file_size_mb(output_path_b):.2f} MB, {len(mesh_obj_b.data.polygons):,} faces")
    log(f"Total time: {total_time:.2f}s")

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e
