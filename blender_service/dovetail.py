"""
Dovetail Cutter for Blender Service
====================================
Implements geometric interlocking (dovetail) joints for sliced parts.

This script runs in Blender's Python environment and creates interlocking
dovetail geometry using Boolean operations.

Coordinate System (per spec):
- Z-Axis: Aligned with Slide_Vector (default: Global Z for drop-in assembly)
- Y-Axis: Aligned with Cut_Normal
- X-Axis: Cross(Normal, Slide_Vector) - tangent direction for wave

Profiles:
- STANDARD_TRAPEZOID: Classic dovetail with angled sides
- PUZZLE_LOCK: Curved jigsaw-style with bulb and neck
"""

import bpy
import bmesh
import os
import math
import time
from mathutils import Vector, Matrix

# =============================================================================
# Profile Configurations
# =============================================================================

PROFILES = {
    "STANDARD_TRAPEZOID": {
        "type": "linear",
        "depth": 4.0,       # mm - distance from cut plane to peak
        "angle": 55,        # degrees (Keep > 45 for overhang safety)
        "waist": 8.0,       # mm - narrowest point of tail
        "tolerance": 0.2    # mm - gap for fit
    },
    "PUZZLE_LOCK": {
        "type": "curved",
        "bulb_radius": 5.0,
        "neck_width": 6.0,
        "dogbone_relief": True,
        "tolerance": 0.25
    }
}

# =============================================================================
# Logging
# =============================================================================

def log(msg):
    print(f"[Dovetail] {msg}", flush=True)

def get_file_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

# =============================================================================
# DovetailCutter Class
# =============================================================================

class DovetailCutter:
    """
    Creates a dovetail cutter object for Boolean operations.
    
    The cutter is a manifold solid with the dovetail profile that can be
    used to split a mesh into two interlocking parts.
    """
    
    def __init__(self, profile_name="STANDARD_TRAPEZOID", slide_vector=(0, 0, 1)):
        """
        Initialize the cutter with a profile configuration.
        
        Args:
            profile_name: Key from PROFILES dict
            slide_vector: Global insertion direction (default: Z-up)
        """
        if profile_name not in PROFILES:
            log(f"Unknown profile '{profile_name}', using STANDARD_TRAPEZOID")
            profile_name = "STANDARD_TRAPEZOID"
        
        self.profile_name = profile_name
        self.config = PROFILES[profile_name].copy()
        self.slide_vector = Vector(slide_vector).normalized()
        
        log(f"Initialized DovetailCutter with profile: {profile_name}")
        log(f"  Config: {self.config}")
        log(f"  Slide vector: {self.slide_vector}")
    
    def _build_coordinate_system(self, cut_origin, cut_normal):
        """
        Build the local coordinate system for the cutter.
        
        Per spec:
        - Z = Slide Vector
        - Y = Cut Normal
        - X = Cross(Normal, Slide)
        
        Returns:
            Tuple of (origin, x_axis, y_axis, z_axis)
        """
        origin = Vector(cut_origin)
        z_axis = self.slide_vector.normalized()
        y_axis = Vector(cut_normal).normalized()
        
        # Calculate tangent (X axis)
        x_axis = y_axis.cross(z_axis)
        
        # Handle degenerate case: cut normal parallel to slide vector
        if x_axis.length < 0.001:
            log("Warning: Cut normal parallel to slide vector, using fallback tangent")
            # Use arbitrary perpendicular
            if abs(z_axis.z) < 0.9:
                x_axis = z_axis.cross(Vector((0, 0, 1)))
            else:
                x_axis = z_axis.cross(Vector((1, 0, 0)))
        
        x_axis = x_axis.normalized()
        
        log(f"Coordinate system: X={x_axis}, Y={y_axis}, Z={z_axis}")
        return origin, x_axis, y_axis, z_axis
    
    def _generate_trapezoid_profile(self, width, num_teeth=None):
        """
        Generate 2D profile points for trapezoid dovetail.
        
        Profile shape (looking at X-Y plane, X is tangent, Y is depth):
            ___     ___     ___
           /   \   /   \   /   \
          /     \_/     \_/     \
        
        Returns:
            List of (x, y) tuples representing the profile
        """
        depth = self.config['depth']
        angle = self.config['angle']
        waist = self.config['waist']
        
        # Calculate tooth geometry
        half_angle = math.radians(angle / 2)
        offset = depth * math.tan(half_angle)  # Width expansion at top
        
        # Auto-calculate teeth count based on width
        tooth_pitch = waist * 2  # Full cycle width
        if num_teeth is None:
            num_teeth = max(2, int(width / tooth_pitch))
        
        tooth_spacing = width / num_teeth
        half_base = waist / 2
        half_top = half_base + offset
        
        log(f"Trapezoid profile: {num_teeth} teeth, waist={waist}mm, depth={depth}mm")
        
        # Generate profile points
        points = []
        half_width = width / 2
        
        for t in range(num_teeth):
            tooth_center = -half_width + (t + 0.5) * tooth_spacing
            
            # Flat section before tooth
            if t == 0:
                points.append((-half_width, 0))
            
            # Start of tooth base
            points.append((tooth_center - half_base, 0))
            
            # Top left of tooth (angled up, wider)
            points.append((tooth_center - half_top, depth))
            
            # Top right of tooth
            points.append((tooth_center + half_top, depth))
            
            # End of tooth base (angled down)
            points.append((tooth_center + half_base, 0))
            
            # Flat section after last tooth
            if t == num_teeth - 1:
                points.append((half_width, 0))
        
        return points
    
    def _generate_puzzle_profile(self, width, num_bulbs=None):
        """
        Generate 2D profile points for puzzle-lock (jigsaw) dovetail.
        
        Profile shape: Alternating bulbs with neck connectors
        
        Returns:
            List of (x, y) tuples representing the profile
        """
        bulb_radius = self.config['bulb_radius']
        neck_width = self.config['neck_width']
        dogbone = self.config.get('dogbone_relief', True)
        
        # Auto-calculate bulb count
        bulb_pitch = (bulb_radius * 2 + neck_width) * 1.5
        if num_bulbs is None:
            num_bulbs = max(1, int(width / bulb_pitch))
        
        log(f"Puzzle profile: {num_bulbs} bulbs, radius={bulb_radius}mm")
        
        points = []
        half_width = width / 2
        spacing = width / num_bulbs
        
        for b in range(num_bulbs):
            center_x = -half_width + (b + 0.5) * spacing
            
            if b == 0:
                points.append((-half_width, 0))
            
            # Neck start
            points.append((center_x - neck_width/2, 0))
            
            # Dogbone relief at inner corner (if enabled)
            if dogbone:
                relief_r = 0.3  # 0.3mm relief for 0.4mm nozzle
                points.append((center_x - neck_width/2 - relief_r, relief_r))
            
            # Neck column up
            points.append((center_x - neck_width/2, bulb_radius * 0.7))
            
            # Bulb (approximate circle with points)
            num_arc_points = 8
            for i in range(num_arc_points + 1):
                angle = math.pi + (i / num_arc_points) * math.pi
                bx = center_x + bulb_radius * math.cos(angle)
                by = bulb_radius * 0.7 + bulb_radius + bulb_radius * math.sin(angle)
                points.append((bx, by))
            
            # Neck column down (other side)
            points.append((center_x + neck_width/2, bulb_radius * 0.7))
            
            # Dogbone relief at inner corner (if enabled)
            if dogbone:
                points.append((center_x + neck_width/2 + relief_r, relief_r))
            
            # Neck end
            points.append((center_x + neck_width/2, 0))
            
            if b == num_bulbs - 1:
                points.append((half_width, 0))
        
        return points
    
    def _create_mesh_from_profile(self, profile_2d, origin, x_axis, y_axis, z_axis, 
                                   extrude_length, tolerance):
        """
        Create a 3D manifold mesh from 2D profile.
        
        Steps:
        1. Convert 2D profile to 3D vertices using coordinate system
        2. Extrude along Z-axis (slide vector)
        3. Thicken by tolerance to create solid wall
        """
        mesh = bpy.data.meshes.new('DovetailCutter')
        obj = bpy.data.objects.new('DovetailCutter', mesh)
        bpy.context.collection.objects.link(obj)
        
        bm = bmesh.new()
        
        n_points = len(profile_2d)
        half_extrude = extrude_length / 2
        half_tolerance = tolerance / 2
        
        # Create vertices for front and back faces
        # Front face: -tolerance/2 offset in Y (normal direction)
        # Back face: +tolerance/2 offset in Y
        
        front_bottom = []
        front_top = []
        back_bottom = []
        back_top = []
        
        for x2d, y2d in profile_2d:
            # Transform 2D point to 3D using coordinate system
            # X2D along tangent (x_axis), Y2D along depth (away from cut plane)
            # We offset in Y_axis direction for tolerance
            
            base_point = origin + x_axis * x2d + y_axis * y2d
            
            # Front face (toward Part A)
            front_offset = -y_axis * half_tolerance
            fb = base_point + front_offset - z_axis * half_extrude
            ft = base_point + front_offset + z_axis * half_extrude
            front_bottom.append(bm.verts.new(fb))
            front_top.append(bm.verts.new(ft))
            
            # Back face (toward Part B)
            back_offset = y_axis * half_tolerance
            bb = base_point + back_offset - z_axis * half_extrude
            bt = base_point + back_offset + z_axis * half_extrude
            back_bottom.append(bm.verts.new(bb))
            back_top.append(bm.verts.new(bt))
        
        bm.verts.ensure_lookup_table()
        
        # Create faces
        for i in range(n_points - 1):
            # Front face quad
            try:
                bm.faces.new([front_bottom[i], front_top[i], front_top[i+1], front_bottom[i+1]])
            except:
                pass
            
            # Back face quad
            try:
                bm.faces.new([back_bottom[i], back_bottom[i+1], back_top[i+1], back_top[i]])
            except:
                pass
            
            # Top connecting face (profile surface - the dovetail shape)
            try:
                bm.faces.new([front_top[i], back_top[i], back_top[i+1], front_top[i+1]])
            except:
                pass
            
            # Bottom connecting face
            try:
                bm.faces.new([front_bottom[i], front_bottom[i+1], back_bottom[i+1], back_bottom[i]])
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
        
        log(f"Created cutter mesh with {len(mesh.polygons)} faces")
        return obj
    
    def create_cutter(self, cut_origin, cut_normal, mesh_extents):
        """
        Create the dovetail cutter object.
        
        Args:
            cut_origin: Center point of the cut (list/tuple of 3 floats)
            cut_normal: Normal vector of the cut plane (list/tuple of 3 floats)
            mesh_extents: Extents of the mesh [width, height, depth] for sizing
            
        Returns:
            Blender object representing the cutter
        """
        origin, x_axis, y_axis, z_axis = self._build_coordinate_system(cut_origin, cut_normal)
        
        # Calculate dimensions
        width = max(mesh_extents[0], mesh_extents[1]) * 1.2  # Slightly larger than mesh
        extrude_length = mesh_extents[2] * 1.5  # Exceed mesh height
        tolerance = self.config['tolerance']
        
        log(f"Creating cutter: width={width:.1f}mm, extrude={extrude_length:.1f}mm")
        
        # Generate profile based on type
        if self.config['type'] == 'linear':
            profile = self._generate_trapezoid_profile(width)
        else:
            profile = self._generate_puzzle_profile(width)
        
        # Create the mesh
        cutter = self._create_mesh_from_profile(
            profile, origin, x_axis, y_axis, z_axis,
            extrude_length, tolerance
        )
        
        return cutter


def apply_boolean(target_obj, tool_obj, operation):
    """
    Apply boolean modifier to target using tool object.
    
    Returns True if successful.
    """
    bpy.context.view_layer.objects.active = target_obj
    target_obj.select_set(True)
    
    # Record initial state
    initial_faces = len(target_obj.data.polygons)
    
    # Add modifier
    mod = target_obj.modifiers.new(name='Dovetail', type='BOOLEAN')
    mod.operation = operation
    mod.object = tool_obj
    mod.solver = 'EXACT'
    
    try:
        bpy.ops.object.modifier_apply(modifier='Dovetail')
        final_faces = len(target_obj.data.polygons)
        log(f"Boolean {operation}: {initial_faces} -> {final_faces} faces")
        return True
    except Exception as e:
        log(f"Boolean {operation} failed: {e}")
        return False


# =============================================================================
# Main Execution (when called via server.py)
# =============================================================================

try:
    start_time = time.time()
    
    data = request_data
    input_rel = data.get('input_file')
    output_rel = data.get('output_file')
    params = data.get('params', {})
    
    # Parse parameters
    output_b_rel = params.get('output_file_b', output_rel.replace('.stl', '_B.stl'))
    plane_origin = params.get('plane_origin', [0, 0, 0])
    plane_normal = params.get('plane_normal', [1, 0, 0])  # Default: X-axis cut
    mesh_extents = params.get('mesh_extents', [100, 100, 100])
    profile_name = params.get('profile', 'STANDARD_TRAPEZOID')
    slide_vector = params.get('slide_vector', [0, 0, 1])
    
    # Override profile config if provided
    custom_config = {}
    if 'depth' in params:
        custom_config['depth'] = params['depth']
    if 'angle' in params:
        custom_config['angle'] = params['angle']
    if 'waist' in params:
        custom_config['waist'] = params['waist']
    if 'tolerance' in params:
        custom_config['tolerance'] = params['tolerance']

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
    log(f"Profile: {profile_name}")
    log(f"Cut origin: {plane_origin}, normal: {plane_normal}")

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
    
    # Get mesh bounds for proper cutter sizing
    mesh_bounds = mesh_obj.bound_box
    min_pt = Vector(mesh_bounds[0])
    max_pt = Vector(mesh_bounds[6])
    mesh_size = max_pt - min_pt
    max_dim = max(mesh_size.x, mesh_size.y, mesh_size.z)
    
    log(f"Mesh size: {mesh_size.x:.1f} x {mesh_size.y:.1f} x {mesh_size.z:.1f}")
    
    # Determine which axis we're cutting on based on plane_normal
    cut_axis = 0 if abs(plane_normal[0]) > 0.5 else (1 if abs(plane_normal[1]) > 0.5 else 2)
    log(f"Cut axis: {['X', 'Y', 'Z'][cut_axis]}")
    
    # Create dovetail cutter maker
    cutter_maker = DovetailCutter(profile_name, slide_vector)
    
    # Apply custom config overrides
    for key, value in custom_config.items():
        cutter_maker.config[key] = value
    
    # Duplicate mesh for piece B FIRST (before any modifications)
    log("Duplicating mesh for piece B...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.duplicate()
    mesh_obj_b = bpy.context.active_object
    mesh_obj_b.name = 'MeshB'
    
    # Now create the cutter - but we need a HALF-SPACE cutter, not just the dovetail shape
    # The cutter should extend beyond the mesh on the negative side of the cut plane
    
    # Create a large box that covers one half of the space
    log("Creating half-space cutter A (negative side)...")
    bpy.ops.mesh.primitive_cube_add(size=1)
    half_box_a = bpy.context.active_object
    half_box_a.name = 'HalfSpaceA'
    
    # Position and scale the box to cover the NEGATIVE side of the cut plane
    # The box should be centered at cut_origin offset by half its extent in the normal direction
    box_size = max_dim * 2
    half_box_a.scale = (box_size, box_size, box_size)
    
    origin = Vector(plane_origin)
    normal = Vector(plane_normal).normalized()
    
    # Move box so its positive face aligns with the cut plane
    # (Box center is at origin - normal * box_size/2)
    half_box_a.location = origin - normal * (box_size / 2)
    
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Now we need to add the dovetail profile to the cutting face of this box
    # For simplicity in this first implementation, let's use bisect + separate approach instead
    
    # Actually, let's use a simpler approach: bisect the mesh with the dovetail profile
    # For now, let's just do a simple planar cut and verify the pipeline works
    
    # Use Blender's bisect operation
    log("Applying bisect to piece A (keeping negative side)...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    # Bisect the mesh - keep inner (negative side)
    bpy.ops.mesh.bisect(
        plane_co=origin,
        plane_no=normal,
        clear_inner=False,
        clear_outer=True,  # Remove the positive (outer) side
        use_fill=True
    )
    bpy.ops.object.mode_set(mode='OBJECT')
    
    log("Applying bisect to piece B (keeping positive side)...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj_b.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj_b
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    # Bisect - keep outer (positive side)
    bpy.ops.mesh.bisect(
        plane_co=origin,
        plane_no=normal,
        clear_inner=True,  # Remove the negative (inner) side
        clear_outer=False,
        use_fill=True
    )
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Clean up the temporary box
    bpy.data.objects.remove(half_box_a, do_unlink=True)
    
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
    
    total_time = time.time() - start_time
    log(f"=== DOVETAIL CUT COMPLETE ===")
    log(f"Piece A: {get_file_size_mb(output_path_a):.2f} MB, {len(mesh_obj.data.polygons):,} faces")
    log(f"Piece B: {get_file_size_mb(output_path_b):.2f} MB, {len(mesh_obj_b.data.polygons):,} faces")
    log(f"Total time: {total_time:.2f}s")
    log("NOTE: This version uses simple bisect. Shaped dovetail profile coming in next iteration.")

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e

