"""
Slicer Advanced v3 - Master Reference Pattern
Implements:
- Island detection for disconnected cut surfaces
- Peg Registry for collision prevention
- Raycast validation for wall thickness
- Shape support (Circle, Square, Triangle, Hexagon)
- Master Reference pattern for zero-tolerance alignment
"""
import bpy
import bmesh
import os
import json
import math
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_line

# =============================================================================
# Configuration
# =============================================================================
DEFAULT_PEG_DIAMETER = 5.0
DEFAULT_PEG_DEPTH = 10.0
DEFAULT_CLEARANCE_SCALE = 1.05  # 5% scale for cutter peg
MIN_WALL_THICKNESS = 2.0  # mm - minimum wall thickness for peg placement
MIN_ISLAND_AREA = 20.0  # mm² - ignore tiny islands

SHAPE_VERTICES = {
    'circle': 32,
    'square': 4,
    'triangle': 3,
    'hexagon': 6,
}

# =============================================================================
# Logging
# =============================================================================
def log(msg):
    print(f"[SlicerAdvanced-v3] {msg}", flush=True)


# =============================================================================
# Peg Registry - Collision Prevention (Phase 3)
# =============================================================================
class PegRegistry:
    """
    Tracks all placed pegs to prevent collisions (Swiss Cheese Guard).
    Each peg is stored as a line segment with radius.
    """
    def __init__(self):
        self.pegs = []  # List of {'start': Vector, 'end': Vector, 'radius': float}
    
    def register(self, start: Vector, end: Vector, radius: float):
        """Register a new peg."""
        self.pegs.append({'start': start.copy(), 'end': end.copy(), 'radius': radius})
        log(f"Registered peg: start={start}, end={end}, radius={radius}")
    
    def _closest_point_on_segment(self, point: Vector, seg_start: Vector, seg_end: Vector) -> Vector:
        """Find the closest point on a line segment to a given point."""
        seg_vec = seg_end - seg_start
        seg_len_sq = seg_vec.length_squared
        
        if seg_len_sq < 0.0001:  # Degenerate segment
            return seg_start.copy()
        
        # Project point onto line, clamped to segment
        t = max(0, min(1, (point - seg_start).dot(seg_vec) / seg_len_sq))
        return seg_start + seg_vec * t
    
    def _segment_distance(self, s1_start: Vector, s1_end: Vector, s2_start: Vector, s2_end: Vector) -> float:
        """
        Calculate the minimum distance between two line segments.
        Uses iterative closest point approach for robustness.
        """
        # First, try the line-line intersection approach
        result = intersect_line_line(s1_start, s1_end, s2_start, s2_end)
        
        if result is not None:
            p1, p2 = result
            # Check if these points are actually on the segments
            # by checking if they're within the segment bounds
            
            # Check p1 on segment 1
            s1_vec = s1_end - s1_start
            s1_len = s1_vec.length
            if s1_len > 0.0001:
                t1 = (p1 - s1_start).dot(s1_vec) / (s1_len * s1_len)
                if 0 <= t1 <= 1:
                    # Check p2 on segment 2
                    s2_vec = s2_end - s2_start
                    s2_len = s2_vec.length
                    if s2_len > 0.0001:
                        t2 = (p2 - s2_start).dot(s2_vec) / (s2_len * s2_len)
                        if 0 <= t2 <= 1:
                            # Both points are on segments, use this distance
                            return (p1 - p2).length
        
        # Fallback: check all endpoint-to-segment distances
        distances = [
            (self._closest_point_on_segment(s1_start, s2_start, s2_end) - s1_start).length,
            (self._closest_point_on_segment(s1_end, s2_start, s2_end) - s1_end).length,
            (self._closest_point_on_segment(s2_start, s1_start, s1_end) - s2_start).length,
            (self._closest_point_on_segment(s2_end, s1_start, s1_end) - s2_end).length,
        ]
        return min(distances)
    
    def check_collision(self, start: Vector, end: Vector, radius: float, margin: float = 1.0) -> bool:
        """
        Check if a candidate peg would collide with any existing pegs.
        Returns True if collision detected.
        """
        for existing in self.pegs:
            distance = self._segment_distance(start, end, existing['start'], existing['end'])
            min_distance = radius + existing['radius'] + margin
            
            if distance < min_distance:
                log(f"Collision detected: distance={distance:.2f} < min={min_distance:.2f}")
                return True
        
        return False


# =============================================================================
# Utility Functions
# =============================================================================
def cleanup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_stl(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    bpy.ops.import_mesh.stl(filepath=path)
    obj = bpy.context.selected_objects[0]
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


def get_shape_vertices(shape: str) -> int:
    """Get vertex count for a shape."""
    return SHAPE_VERTICES.get(shape.lower(), 32)


# =============================================================================
# Phase 1: Slice & Cap Analysis with Island Detection
# =============================================================================
def find_islands(bm, cut_edges):
    """
    Find disconnected islands in the cut geometry using graph traversal.
    Returns list of lists of BMEdges, one per island.
    """
    if not cut_edges:
        return []
    
    edge_set = set(cut_edges)
    visited = set()
    islands = []
    
    for start_edge in cut_edges:
        if start_edge in visited:
            continue
        
        # BFS to find connected edges
        island = []
        queue = [start_edge]
        
        while queue:
            edge = queue.pop(0)
            if edge in visited:
                continue
            
            visited.add(edge)
            island.append(edge)
            
            # Find connected edges via shared vertices
            for vert in edge.verts:
                for linked_edge in vert.link_edges:
                    if linked_edge in edge_set and linked_edge not in visited:
                        queue.append(linked_edge)
        
        if island:
            islands.append(island)
    
    log(f"Found {len(islands)} island(s) in cut geometry")
    return islands


def calculate_island_centroid(island_edges, matrix_world):
    """
    Calculate centroid of an island in world space.
    Returns (centroid_world, area_estimate).
    """
    if not island_edges:
        return None, 0
    
    # Collect unique vertices
    verts = set()
    for edge in island_edges:
        for vert in edge.verts:
            verts.add(vert)
    
    if not verts:
        return None, 0
    
    # Calculate centroid in local space
    centroid_local = sum((v.co.copy() for v in verts), Vector()) / len(verts)
    centroid_world = matrix_world @ centroid_local
    
    # Rough area estimate: bounding box of vertices
    coords = [v.co for v in verts]
    if len(coords) < 3:
        return centroid_world, 0
    
    min_x = min(v.x for v in coords)
    max_x = max(v.x for v in coords)
    min_y = min(v.y for v in coords)
    max_y = max(v.y for v in coords)
    min_z = min(v.z for v in coords)
    max_z = max(v.z for v in coords)
    
    # 2D area estimate (ignore the axis with smallest range)
    ranges = [(max_x - min_x), (max_y - min_y), (max_z - min_z)]
    ranges.sort()
    area = ranges[1] * ranges[2]  # Use the two larger dimensions
    
    return centroid_world, area


def bisect_object_bmesh(obj, plane_co, plane_no, clear_inner=False, clear_outer=True):
    """
    Bisect an object using bmesh.ops.bisect_plane with Island Detection.
    Returns (list of island centroids, is_valid) where each centroid is in WORLD space.
    """
    log(f"Bisecting {obj.name} at plane_co={plane_co}, plane_no={plane_no}")
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    log(f"Pre-bisect: {len(bm.verts)} verts, {len(bm.faces)} faces")
    
    result = bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        plane_co=plane_co,
        plane_no=plane_no,
        clear_inner=clear_inner,
        clear_outer=clear_outer
    )
    
    log(f"Post-bisect: {len(bm.verts)} verts, {len(bm.faces)} faces")
    
    cut_edges = [elem for elem in result['geom_cut'] if isinstance(elem, bmesh.types.BMEdge)]
    log(f"geom_cut contains: {len(cut_edges)} edges")
    
    island_centroids = []
    
    if cut_edges:
        # Find islands
        islands = find_islands(bm, cut_edges)
        
        for i, island in enumerate(islands):
            centroid, area = calculate_island_centroid(island, obj.matrix_world)
            if centroid and area >= MIN_ISLAND_AREA:
                island_centroids.append(centroid)
                log(f"Island {i+1}: centroid={centroid}, area={area:.1f} mm²")
            elif centroid:
                log(f"Island {i+1}: SKIPPED (area={area:.1f} mm² < {MIN_ISLAND_AREA} mm²)")
        
        # Fill the cut holes
        try:
            bmesh.ops.contextual_create(bm, geom=cut_edges)
            log("Filled cut hole successfully")
        except Exception as e:
            log(f"Warning: Could not fill cut: {e}")
            try:
                bmesh.ops.triangle_fill(bm, edges=cut_edges)
            except:
                pass
    else:
        log("WARNING: No cut edges found!")
    
    # Recalculate normals (Edge Case #2 from Req)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    if len(obj.data.vertices) == 0:
        log(f"Object {obj.name} has no vertices after bisect")
        return [], False
    
    log(f"Object {obj.name} has {len(obj.data.vertices)} vertices, {len(island_centroids)} valid islands")
    return island_centroids, True


# =============================================================================
# Phase 2: Raycast Validation for Wall Thickness
# =============================================================================
def validate_peg_placement(obj, position: Vector, normal: Vector, radius: float) -> tuple:
    """
    Validate peg placement using raycasting to check wall thickness.
    Returns (is_valid, adjusted_radius).
    """
    log(f"Validating peg at {position}, normal={normal}, radius={radius}")
    
    # Cast rays perpendicular to the normal
    # Build orthonormal basis
    normal = normal.normalized()
    
    if abs(normal.z) < 0.9:
        perp1 = normal.cross(Vector((0, 0, 1))).normalized()
    else:
        perp1 = normal.cross(Vector((1, 0, 0))).normalized()
    
    perp2 = normal.cross(perp1).normalized()
    
    min_distance = float('inf')
    hit_count = 0
    
    # Cast rays in 8 directions perpendicular to normal
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        direction = perp1 * math.cos(rad) + perp2 * math.sin(rad)
        
        # Cast ray from peg center outwards
        result, location, face_normal, index = obj.ray_cast(position, direction)
        if result:
            hit_count += 1
            dist = (location - position).length
            if dist < min_distance:
                min_distance = dist
    
    log(f"  Raycast: {hit_count}/8 hits, min_distance={min_distance:.2f}")
    
    # If no rays hit, the peg is probably valid (position might be on the edge)
    if hit_count == 0 or min_distance == float('inf'):
        log(f"  No raycast hits - allowing peg (edge placement?)")
        return True, radius
    
    # Check if we have enough wall thickness
    required_clearance = radius + MIN_WALL_THICKNESS
    
    if min_distance < required_clearance:
        # Try to shrink the peg
        max_radius = min_distance - MIN_WALL_THICKNESS
        if max_radius > 1.0:  # Minimum viable peg radius
            log(f"  Wall check: shrinking peg from {radius:.1f} to {max_radius:.1f}")
            return True, max_radius
        else:
            # Be more lenient - only reject if really too close
            if min_distance < radius:
                log(f"  Wall check FAILED: distance={min_distance:.1f} < radius={radius:.1f}")
                return False, 0
            else:
                log(f"  Wall check: marginal but allowing (distance={min_distance:.1f})")
                return True, radius
    
    log(f"  Validation passed")
    return True, radius


# =============================================================================
# Phase 4: Geometry Generation with Shape Support & Master Reference Pattern
# =============================================================================
def create_peg(position: Vector, normal: Vector, diameter: float, depth: float, shape: str = 'circle'):
    """
    Create a peg (cylinder/prism) at the specified position aligned to normal.
    Returns the created object.
    """
    vertices = get_shape_vertices(shape)
    
    # Create at origin
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2,
        depth=depth,
        vertices=vertices,
        location=(0, 0, 0)
    )
    peg = bpy.context.active_object
    peg.name = f"Peg_{shape}"
    
    # Align to normal
    up = Vector((0, 0, 1))
    target = normal.normalized()
    quat = up.rotation_difference(target)
    peg.rotation_euler = quat.to_euler()
    
    # Position - center the peg at the interface
    peg.location = position
    
    # Apply transforms
    bpy.ops.object.select_all(action='DESELECT')
    peg.select_set(True)
    bpy.context.view_layer.objects.active = peg
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    
    return peg


def apply_master_reference_pattern(part_a, part_b, centroid: Vector, normal: Vector, 
                                   params: dict, registry: PegRegistry, shape: str = 'circle'):
    """
    Apply the Master Reference Pattern:
    1. Create Master Peg at centroid
    2. Union to Part A (pin side)
    3. Duplicate & Scale to create Cutter Peg
    4. Difference from Part B (hole side)
    5. Register peg in collision registry
    """
    diameter = params.get('diameter', DEFAULT_PEG_DIAMETER)
    depth = params.get('height', params.get('depth', DEFAULT_PEG_DEPTH))  # Support both 'height' and 'depth'
    
    log(f"=== MASTER REFERENCE PATTERN ===")
    log(f"Centroid: {centroid}, Normal: {normal}")
    log(f"Shape: {shape}, Diameter: {diameter}, Depth: {depth}")
    
    # Validate placement on Part A (the one getting the pin)
    is_valid, adjusted_radius = validate_peg_placement(part_a, centroid, normal, diameter / 2)
    if not is_valid:
        log("Peg placement validation FAILED, skipping this peg")
        return False
    
    if adjusted_radius < diameter / 2:
        diameter = adjusted_radius * 2
        log(f"Adjusted diameter to {diameter:.1f}")
    
    # Check collision registry
    peg_start = centroid - normal * (depth / 2)
    peg_end = centroid + normal * (depth / 2)
    
    if registry.check_collision(peg_start, peg_end, diameter / 2):
        log("Collision detected in registry, skipping peg")
        return False
    
    # Step 1: Create Master Peg at centroid
    # For Union to Part A, we want the peg extending INTO Part B (along -normal on Part A's face)
    # But Part A's face points in +normal direction at the cut
    # So we position the peg at centroid, half in, half out
    master_peg = create_peg(centroid, normal, diameter, depth, shape)
    log(f"Created master peg: {master_peg.name}")
    
    # Step 2: Boolean UNION to Part A (the one receiving the male pin)
    bpy.context.view_layer.objects.active = part_a
    try:
        mod = part_a.modifiers.new(name="MasterPeg", type='BOOLEAN')
        mod.operation = 'UNION'
        mod.object = master_peg
        mod.solver = 'FAST'
        bpy.ops.object.modifier_apply(modifier="MasterPeg")
        log(f"Union to {part_a.name} successful")
    except Exception as e:
        log(f"Union failed: {e}, using fallback join")
        bpy.ops.object.select_all(action='DESELECT')
        part_a.select_set(True)
        master_peg.select_set(True)
        bpy.context.view_layer.objects.active = part_a
        bpy.ops.object.join()
        master_peg = None  # Was merged
    
    # Step 3: Create Cutter Peg (scaled for clearance)
    scale_factor = DEFAULT_CLEARANCE_SCALE
    cutter_diameter = diameter * scale_factor
    cutter_depth = depth * scale_factor + 0.5  # Slightly longer for clean cut
    
    cutter_peg = create_peg(centroid, normal, cutter_diameter, cutter_depth, shape)
    cutter_peg.name = "CutterPeg"
    log(f"Created cutter peg: {cutter_peg.name} (scale={scale_factor})")
    
    # Step 4: Boolean DIFFERENCE from Part B (the one receiving the hole)
    bpy.context.view_layer.objects.active = part_b
    try:
        mod = part_b.modifiers.new(name="CutterPeg", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter_peg
        mod.solver = 'FAST'
        bpy.ops.object.modifier_apply(modifier="CutterPeg")
        log(f"Difference from {part_b.name} successful")
    except Exception as e:
        log(f"Difference failed: {e}")
    
    # Cleanup
    if master_peg and master_peg.name in bpy.data.objects:
        bpy.data.objects.remove(master_peg, do_unlink=True)
    if cutter_peg and cutter_peg.name in bpy.data.objects:
        bpy.data.objects.remove(cutter_peg, do_unlink=True)
    
    # Step 5: Register peg
    registry.register(peg_start, peg_end, diameter / 2)
    
    return True


# =============================================================================
# Main Slicing Function
# =============================================================================
def slice_and_connect(obj, grid_config, joint_params):
    """
    Main slicing function with advanced peg placement.
    Returns tuple of (parts_list, part_connectors_dict)
    where part_connectors_dict maps part object name to list of connector info.
    """
    add_connectors = joint_params.get('diameter', 0) > 0
    shape = joint_params.get('shape', 'circle')
    diameter = joint_params.get('diameter', DEFAULT_PEG_DIAMETER)
    depth = joint_params.get('height', joint_params.get('depth', DEFAULT_PEG_DEPTH))
    
    # Initialize peg registry for collision prevention
    registry = PegRegistry()
    
    # Connector tracking per part (by object name since objects may change)
    part_connectors = {}  # {part_name: [connector_dicts]}
    
    # Get object bounds
    bbox = [obj.matrix_world @ Vector(b) for b in obj.bound_box]
    min_vec = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
    max_vec = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
    size = max_vec - min_vec
    
    log(f"Object bounds: min={min_vec}, max={max_vec}, size={size}")
    log(f"Connectors: {add_connectors}, Shape: {shape}")
    
    parts = [obj]
    axes = [('x', 0), ('y', 1), ('z', 2)]
    
    for axis_name, axis_idx in axes:
        num_sections = grid_config.get(axis_name, 1)
        if num_sections <= 1:
            continue
        
        start = min_vec[axis_idx]
        step = size[axis_idx] / num_sections
        cut_positions = [start + step * i for i in range(1, num_sections)]
        
        log(f"Axis {axis_name}: {len(cut_positions)} cuts at {cut_positions}")
        
        for cut_pos in cut_positions:
            new_parts = []
            
            plane_co = Vector((0, 0, 0))
            plane_co[axis_idx] = cut_pos
            
            plane_no = Vector((0, 0, 0))
            plane_no[axis_idx] = 1.0
            
            for part in parts:
                # Duplicate for positive side
                part_b = duplicate_object(part)
                part_a = part
                
                # Bisect part_a (keep negative side)
                centroids_a, valid_a = bisect_object_bmesh(
                    part_a, plane_co, plane_no,
                    clear_inner=False, clear_outer=True
                )
                
                # Bisect part_b (keep positive side)
                centroids_b, valid_b = bisect_object_bmesh(
                    part_b, plane_co, plane_no,
                    clear_inner=True, clear_outer=False
                )
                
                log(f"Cut result: A valid={valid_a} ({len(centroids_a)} islands), B valid={valid_b} ({len(centroids_b)} islands)")
                
                # Collect valid parts
                if valid_a:
                    new_parts.append(part_a)
                    if part_a.name not in part_connectors:
                        part_connectors[part_a.name] = []
                else:
                    bpy.data.objects.remove(part_a, do_unlink=True)
                
                if valid_b:
                    new_parts.append(part_b)
                    if part_b.name not in part_connectors:
                        part_connectors[part_b.name] = []
                else:
                    bpy.data.objects.remove(part_b, do_unlink=True)
                
                # Add connectors for each island
                if add_connectors and valid_a and valid_b:
                    for centroid in centroids_a:
                        # Apply Master Reference Pattern
                        normal = -plane_no  # Pin points from B toward A
                        
                        success = apply_master_reference_pattern(
                            part_a=part_b,  # Pin goes to positive side
                            part_b=part_a,  # Hole goes to negative side
                            centroid=centroid,
                            normal=normal,
                            params=joint_params,
                            registry=registry,
                            shape=shape
                        )
                        
                        if success:
                            # Record connector for part_b (pin)
                            part_connectors[part_b.name].append({
                                'position': [centroid.x, centroid.y, centroid.z],
                                'normal': [normal.x, normal.y, normal.z],
                                'diameter': diameter,
                                'depth': depth,
                                'type': 'pin',
                                'shape': shape
                            })
                            # Record connector for part_a (hole)
                            hole_normal = plane_no  # Hole faces opposite direction
                            part_connectors[part_a.name].append({
                                'position': [centroid.x, centroid.y, centroid.z],
                                'normal': [hole_normal.x, hole_normal.y, hole_normal.z],
                                'diameter': diameter,
                                'depth': depth,
                                'type': 'hole',
                                'shape': shape
                            })
            
            parts = new_parts
    
    return parts, part_connectors


# =============================================================================
# Main Execution
# =============================================================================
try:
    log("Starting Slicer Advanced v3 (Master Reference Pattern)")
    
    data = request_data
    input_file = data.get('input_file')
    output_dir_rel = data.get('output_dir')
    base_name = data.get('base_name', 'slice')
    params = data.get('params', {})
    
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
    
    parts, part_connectors = slice_and_connect(obj, grid, joint_params)
    
    log(f"Slicing complete. {len(parts)} parts created.")
    
    # Export parts
    output_files = []
    for i, part in enumerate(parts):
        bpy.ops.object.select_all(action='DESELECT')
        part.select_set(True)
        bpy.context.view_layer.objects.active = part
        
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        
        fname = f"{base_name}_part_{i+1}.stl"
        fpath = os.path.join(output_dir, fname)
        
        bpy.ops.export_mesh.stl(filepath=fpath, use_selection=True)
        
        # Get connectors for this part (by name)
        connectors = part_connectors.get(part.name, [])
        
        output_files.append({
            "filepath": os.path.join(output_dir_rel, fname),
            "filename": fname,
            "has_connectors": len(connectors) > 0,
            "connectors": connectors
        })
        log(f"Exported: {fname} with {len(connectors)} connectors")
    
    # Write manifest
    manifest_path = os.path.join(output_dir, f"{base_name}_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(output_files, f, indent=2)
    
    log(f"Manifest written to {manifest_path}")
    log("Slicer Advanced v3 complete!")

except Exception as e:
    log(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise e
