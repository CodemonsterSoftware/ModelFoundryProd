"""
Grid-based mesh slicer with joint generation.

Uses trimesh for slicing and boolean operations.
"""
import logging
import math
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

try:
    import trimesh
    import numpy as np
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False
    logger.warning("trimesh not available. Slicing features disabled.")

# Blender service availability (checked lazily)
BLENDER_AVAILABLE = None  # None = not checked yet


def slice_mesh_grid(
    input_path: str,
    output_dir: str,
    grid: Dict[str, int],
    planes: List[Dict[str, Any]] = None,
    joint_type: str = 'none',
    joint_params: Dict[str, Any] = None,
    dovetail_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Slice a mesh into a grid using Blender (Advanced) or Trimesh (Legacy).
    """
    # Use Blender Slicer if joints are requested (for reliability) or global toggle
    use_blender_pipeline = True if joint_type in ['pins', 'dowels'] else False
    
    if use_blender_pipeline:
        try:
            from .blender_client import BlenderClient
            client = BlenderClient()
            if client.is_available():
                return _slice_with_blender_pipeline(
                    client, input_path, output_dir, grid, joint_type, joint_params
                )
        except Exception as e:
            logger.warning(f"Blender pipeline failed: {e}, falling back to Trimesh")
            # Fallback to local
    
    # ... existing local slicing code ...
    logger.info("Using Local Trimesh Slicer")
    mesh = trimesh.load(input_path)
    
    # (Existing implementation continues...)

    """
    Slice a mesh into a grid of parts or using arbitrary planes.
    
    Args:
        input_path: Path to input STL file
        output_dir: Directory to save sliced parts
        grid: Dictionary with 'x', 'y', 'z' division counts (for uniform mode)
        planes: List of plane objects [{'origin': {x,y,z}, 'rotation': {x,y,z}}, ...]
        joint_type: 'none', 'pins', 'dowels', or 'dovetails'
        joint_params: Parameters for pins/dowels
        dovetail_params: Parameters for dovetails
        
    Returns:
        Dictionary containing:
        - 'parts': List of part info dicts with filepath, filename, validation
        - 'warnings': List of warning messages
        - 'blender_required': True if connectors requested but Blender unavailable
        - 'dowel_files': List of generated dowel STL files (for dowel mode)
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh is required for slicing. pip install trimesh")
    
    joint_params = joint_params or {}
    dovetail_params = dovetail_params or {}
    
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    result = {
        'parts': [],
        'warnings': [],
        'blender_required': False,
        'dowel_files': []
    }
    
    # Load mesh
    logger.info(f"Loading mesh: {input_path}")
    mesh = trimesh.load(input_path)
    
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("Input must be a single mesh, not a scene")
    
    # Store original bounds for connector calculations
    original_bounds = mesh.bounds.copy()
    
    # Perform slicing
    parts = []
    part_coords = []  # Track grid coordinates for uniform mode
    
    if planes:
        logger.info(f"Slicing with {len(planes)} arbitrary planes")
        parts = _slice_arbitrary_planes(mesh, planes)
        # Freeform mode doesn't support connectors yet
        if joint_type != 'none':
            result['warnings'].append("Connectors are not yet supported for freeform planes. Parts sliced without connectors.")
            joint_type = 'none'
    else:
        logger.info(f"Slicing with grid: {grid}")
        parts, part_coords = _slice_uniform_grid_with_coords(mesh, grid)

    # Export parts with validation
    base_name = input_path.stem
    
    for i, part in enumerate(parts):
        # Sequential naming
        filename = f"{base_name}_part_{i+1:03d}.stl"
        filepath = output_dir / filename
        part.export(str(filepath))
        
        # Validate the part
        validation_result = validate_mesh(part)
        
        # Build result dictionary
        part_info = {
            'filepath': str(filepath),
            'filename': filename,
            'validation': validation_result,
            'coord': part_coords[i] if i < len(part_coords) else None
        }
        
        result['parts'].append(part_info)
        
        # Log validation results
        status = "✓ Valid" if validation_result['valid'] else f"⚠ Issues: {', '.join(validation_result['issues'])}"
        logger.info(f"Exported part {i+1}/{len(parts)}: {filename} - {status}")
    
    # Apply connectors if requested (uniform grid mode only)
    if joint_type != 'none' and len(parts) > 1 and part_coords:
        connector_result = _apply_connectors(
            output_dir=output_dir,
            parts=result['parts'],
            part_coords=part_coords,
            grid=grid,
            original_bounds=original_bounds,
            joint_type=joint_type,
            joint_params=joint_params,
            dovetail_params=dovetail_params,
            base_name=base_name
        )
        
        # Merge connector results
        if connector_result.get('blender_required'):
            result['blender_required'] = True
        if connector_result.get('warnings'):
            result['warnings'].extend(connector_result['warnings'])
        if connector_result.get('dowel_files'):
            result['dowel_files'].extend(connector_result['dowel_files'])
        if connector_result.get('modified_parts'):
            result['parts'] = connector_result['modified_parts']
    
    return result


def _slice_arbitrary_planes(mesh: 'trimesh.Trimesh', planes: List[Dict]) -> List['trimesh.Trimesh']:
    """
    Iteratively slice mesh with arbitrary planes.
    Each plane splits every existing part into two (Positive/Negative).
    
    Args:
        mesh: Input mesh to slice
        planes: List of plane definitions, each with 'origin' and 'rotation' dicts
        
    Returns:
        List of sliced mesh parts
    """
    if not planes:
        logger.warning("No planes provided for slicing")
        return [mesh]
    
    current_parts = [mesh]
    
    for i, plane_def in enumerate(planes):
        next_parts = []
        
        # Validate plane data structure
        if 'origin' not in plane_def or 'rotation' not in plane_def:
            logger.error(f"Plane {i+1} missing 'origin' or 'rotation' key. Skipping.")
            continue
            
        try:
            origin_dict = plane_def['origin']
            rot_dict = plane_def['rotation']
            
            # Calculate mesh center to match frontend visualization logic
            # The frontend centers the model at (0,0,0) based on bounding box
            mesh_center = mesh.bounds.mean(axis=0)
            
            # Validate origin coordinates and apply offset
            # Plane Origin (Original Space) = Plane Origin (Visual Space) + Mesh Center
            origin = [
                float(origin_dict.get('x', 0)) + mesh_center[0],
                float(origin_dict.get('y', 0)) + mesh_center[1],
                float(origin_dict.get('z', 0)) + mesh_center[2]
            ]
            
            # Validate rotation angles
            normal = _euler_to_normal(
                float(rot_dict.get('x', 0)),
                float(rot_dict.get('y', 0)),
                float(rot_dict.get('z', 0))
            )
            
            logger.info(f"Processing Plane {i+1}/{len(planes)}: VisualOrigin=[{origin_dict.get('x')}, {origin_dict.get('y')}, {origin_dict.get('z')}], AdjustedOrigin={origin}, Normal={normal}")
            
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Invalid plane data at index {i}: {e}. Skipping this plane.")
            continue
        
        for part_idx, part in enumerate(current_parts):
            try:
                # Slice logic: slice_mesh_plane returns the portion in the direction of the normal
                # To get both sides, we slice twice with opposite normals
                
                # Positive Side (in direction of normal)
                pos_part = part.slice_plane(plane_origin=origin, plane_normal=normal, cap=True)
                
                # Negative Side (opposite direction)
                neg_normal = [-n for n in normal]
                neg_part = part.slice_plane(plane_origin=origin, plane_normal=neg_normal, cap=True)
                
                # Keep non-empty parts
                if pos_part is not None and len(pos_part.vertices) > 0:
                    next_parts.append(pos_part)
                    logger.debug(f"  Part {part_idx+1}: Positive side has {len(pos_part.vertices)} vertices")
                
                if neg_part is not None and len(neg_part.vertices) > 0:
                    next_parts.append(neg_part)
                    logger.debug(f"  Part {part_idx+1}: Negative side has {len(neg_part.vertices)} vertices")
                    
                # If both slices failed, keep original part
                if (pos_part is None or len(pos_part.vertices) == 0) and \
                   (neg_part is None or len(neg_part.vertices) == 0):
                    logger.warning(f"  Plane {i+1} did not intersect part {part_idx+1}, keeping original")
                    next_parts.append(part)
                    
            except Exception as e:
                msg = str(e)
                logger.error(f"Error slicing part {part_idx+1} with plane {i+1}: {msg}")
                # Check for known critical errors
                if "triangulation engine" in msg.lower():
                    raise ImportError(f"Missing triangulation engine: {msg}. Please install 'mapbox-earcut' or 'triangle'.")
                
                # For other errors, keep the original part but warn?
                # Actually, raising here might be better to alert the user, but let's stick to safe fallback 
                # and maybe we should propagate this warning up. 
                # But _slice_arbitrary_planes currently returns a list, not a dict with warnings.
                # Changing the return signature is risky for compatibility.
                # For now, we'll log it as error and keep the part.
                next_parts.append(part)
        
        if not next_parts:
            logger.error(f"No valid parts after plane {i+1}, returning current parts")
            return current_parts
            
        current_parts = next_parts
        logger.info(f"After plane {i+1}: {len(current_parts)} parts")
        
    logger.info(f"Slicing complete: {len(current_parts)} total parts created")
    return current_parts



def _slice_with_blender_pipeline(
    client, input_path: str, output_dir: str, grid: Dict[str, int], 
    joint_type: str, joint_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the pure Blender slicing pipeline."""
    import json
    
    logger.info("Executing Pure Blender Slicing Pipeline")
    
    # Prepare params
    base_name = Path(input_path).stem
    
    context = {
        "input_file": input_path,
        "output_dir": output_dir, # Relative handled by client
        "base_name": base_name,
        "params": {
            "grid": grid,
            "joint_type": joint_type,
            "joint_params": joint_params or {}
        }
    }
    
    # Run script
    response = client.run_script('slicer_advanced.py', context)
    
    # Read manifest - now includes connector data from Blender
    manifest_path = Path(output_dir) / f"{base_name}_manifest.json"
    
    parts = []
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            generated_files = json.load(f)
            
        for i, f in enumerate(generated_files):
            part_path = Path(output_dir) / f['filename']
            
            # Connector data comes directly from Blender manifest
            has_connectors = f.get('has_connectors', False)
            connectors = f.get('connectors', [])
            
            parts.append({
                'filename': f['filename'],
                'filepath': str(part_path),
                'url': f"/media/jobs/{Path(output_dir).name}/{f['filename']}",
                'download_url': f"/media/jobs/{Path(output_dir).name}/{f['filename']}",
                'size': os.path.getsize(part_path) if part_path.exists() else 0,
                'has_connectors': has_connectors,
                'connector_positions': connectors
            })
            
            logger.info(f"Part {i+1}: {f['filename']} with {len(connectors)} connectors")
            
    else:
        logger.warning("Manifest not found, Blender slicing might have failed silently")
        
    return {
        'parts': parts,
        'dowel_files': [],
        'warnings': [],
        'blender_required': False
    }

def _slice_uniform_grid(mesh: 'trimesh.Trimesh', grid: Dict[str, int]) -> List['trimesh.Trimesh']:

    """
    Original grid slicing logic preserved for compatibility.
    """
    bounds = mesh.bounds
    min_pt = bounds[0]
    size = bounds[1] - min_pt
    
    grid_x = grid.get('x', 1)
    grid_y = grid.get('y', 1)
    grid_z = grid.get('z', 1)
    
    x_cuts = [min_pt[0] + size[0] * i / grid_x for i in range(1, grid_x)]
    y_cuts = [min_pt[1] + size[1] * i / grid_y for i in range(1, grid_y)]
    z_cuts = [min_pt[2] + size[2] * i / grid_z for i in range(1, grid_z)]
    
    parts = [mesh]
    
    # Simple recursive slicing for now, losing the strict grid coordinates for simplicity in this shared return format
    # If we need strict coordinate naming for grid, we'd need to refactor logic to support hybrid returns.
    # For now, uniform grid will just act as a set of axis-aligned cuts.
    
    for x_cut in x_cuts:
        new_parts = []
        for p in parts:
            new_parts.extend(_split_by_axis(p, x_cut, 0))
        parts = new_parts
        
    for y_cut in y_cuts:
        new_parts = []
        for p in parts:
            new_parts.extend(_split_by_axis(p, y_cut, 1))
        parts = new_parts
        
    for z_cut in z_cuts:
        new_parts = []
        for p in parts:
            new_parts.extend(_split_by_axis(p, z_cut, 2))
        parts = new_parts
        
    return parts


def _split_by_axis(mesh, pos, axis_idx):
    """Helper to split a mesh along an axis-aligned plane"""
    normal = [0, 0, 0]
    normal[axis_idx] = 1
    origin = [0, 0, 0]
    origin[axis_idx] = pos
    
    res = []
    # Positive
    p1 = mesh.slice_plane(plane_origin=origin, plane_normal=normal, cap=True)
    if p1 and len(p1.vertices) > 0: res.append(p1)
    
    # Negative
    normal[axis_idx] = -1
    p2 = mesh.slice_plane(plane_origin=origin, plane_normal=normal, cap=True)
    if p2 and len(p2.vertices) > 0: res.append(p2)
    
    return res


def _slice_uniform_grid_with_coords(
    mesh: 'trimesh.Trimesh', 
    grid: Dict[str, int]
) -> Tuple[List['trimesh.Trimesh'], List[Tuple[int, int, int]]]:
    """
    Slice mesh into uniform grid and track coordinates for each part.
    
    Args:
        mesh: Input mesh
        grid: Grid divisions {x, y, z}
        
    Returns:
        Tuple of (parts list, coordinates list)
        Each coordinate is (x_idx, y_idx, z_idx) identifying position in grid
    """
    bounds = mesh.bounds
    min_pt = bounds[0]
    size = bounds[1] - min_pt
    
    grid_x = grid.get('x', 1)
    grid_y = grid.get('y', 1)
    grid_z = grid.get('z', 1)
    
    # Calculate cut positions
    x_cuts = [min_pt[0] + size[0] * i / grid_x for i in range(1, grid_x)]
    y_cuts = [min_pt[1] + size[1] * i / grid_y for i in range(1, grid_y)]
    z_cuts = [min_pt[2] + size[2] * i / grid_z for i in range(1, grid_z)]
    
    # Track parts and their coordinates
    # Start with mesh at all coords
    parts_with_coords = [(mesh, (0, 0, 0))]  # (mesh, (x_idx, y_idx, z_idx))
    
    # Split along X axis
    next_parts = []
    for part, (xi, yi, zi) in parts_with_coords:
        if not x_cuts:
            next_parts.append((part, (xi, yi, zi)))
        else:
            slices = [part]
            for cut_idx, x_cut in enumerate(x_cuts):
                temp = []
                for s in slices:
                    split_result = _split_by_axis(s, x_cut, 0)
                    temp.extend(split_result)
                slices = temp
            
            # Assign X coordinates based on centroid position
            for s in slices:
                centroid_x = s.centroid[0]
                x_coord = sum(1 for xc in x_cuts if centroid_x > xc)
                next_parts.append((s, (x_coord, yi, zi)))
    
    parts_with_coords = next_parts
    
    # Split along Y axis
    next_parts = []
    for part, (xi, yi, zi) in parts_with_coords:
        if not y_cuts:
            next_parts.append((part, (xi, yi, zi)))
        else:
            slices = [part]
            for y_cut in y_cuts:
                temp = []
                for s in slices:
                    split_result = _split_by_axis(s, y_cut, 1)
                    temp.extend(split_result)
                slices = temp
            
            for s in slices:
                centroid_y = s.centroid[1]
                y_coord = sum(1 for yc in y_cuts if centroid_y > yc)
                next_parts.append((s, (xi, y_coord, zi)))
    
    parts_with_coords = next_parts
    
    # Split along Z axis
    next_parts = []
    for part, (xi, yi, zi) in parts_with_coords:
        if not z_cuts:
            next_parts.append((part, (xi, yi, zi)))
        else:
            slices = [part]
            for z_cut in z_cuts:
                temp = []
                for s in slices:
                    split_result = _split_by_axis(s, z_cut, 2)
                    temp.extend(split_result)
                slices = temp
            
            for s in slices:
                centroid_z = s.centroid[2]
                z_coord = sum(1 for zc in z_cuts if centroid_z > zc)
                next_parts.append((s, (xi, yi, z_coord)))
    
    parts_with_coords = next_parts
    
    # Sort by coordinates for consistent ordering
    parts_with_coords.sort(key=lambda x: x[1])
    
    parts = [p for p, c in parts_with_coords]
    coords = [c for p, c in parts_with_coords]
    
    logger.info(f"Grid slicing produced {len(parts)} parts with coordinates")
    return parts, coords


def _get_profile_connector_positions(
    mesh: 'trimesh.Trimesh',
    axis: int,
    interface_pos: float,
    count: int,
    margin: float = 5.0
) -> List[np.ndarray]:
    """
    Get connector positions by finding vertices on the cut face directly in 3D.
    
    This simpler approach avoids 2D projection issues by:
    1. Finding all vertices within tolerance of the interface plane
    2. Calculating their centroid directly in 3D
    
    Args:
        mesh: The mesh to analyze
        axis: Cut axis (0=X, 1=Y, 2=Z)
        interface_pos: Position along the axis where the cut was made
        count: Number of connectors to place
        margin: Minimum distance from edge for connectors
        
    Returns:
        List of 3D positions for connector centers
    """
    tolerance = 0.1  # Tolerance for finding vertices on the cut plane
    
    try:
        # Get all vertices
        vertices = mesh.vertices
        
        # Find vertices that lie on the cut plane (within tolerance)
        on_plane_mask = np.abs(vertices[:, axis] - interface_pos) < tolerance
        plane_vertices = vertices[on_plane_mask]
        
        if len(plane_vertices) == 0:
            logger.warning(f"No vertices found on interface plane at axis {axis}, pos {interface_pos:.2f}")
            return _fallback_connector_positions(mesh, axis, interface_pos, count)
        
        logger.info(f"Found {len(plane_vertices)} vertices on cut plane")
        
        # Get the perpendicular axes
        perp_axes = [i for i in range(3) if i != axis]
        ax1, ax2 = perp_axes
        
        # Calculate bounds on the perpendicular axes
        min_1 = plane_vertices[:, ax1].min()
        max_1 = plane_vertices[:, ax1].max()
        min_2 = plane_vertices[:, ax2].min()
        max_2 = plane_vertices[:, ax2].max()
        
        logger.info(f"Cut face bounds: axis{ax1}=[{min_1:.2f}, {max_1:.2f}], axis{ax2}=[{min_2:.2f}, {max_2:.2f}]")
        
        # Apply margin
        usable_min_1 = min_1 + margin
        usable_max_1 = max_1 - margin
        usable_min_2 = min_2 + margin
        usable_max_2 = max_2 - margin
        
        # Check if margin leaves enough space
        if usable_min_1 >= usable_max_1 or usable_min_2 >= usable_max_2:
            # Margin too large, reduce it
            margin = min((max_1 - min_1) / 4, (max_2 - min_2) / 4)
            usable_min_1 = min_1 + margin
            usable_max_1 = max_1 - margin
            usable_min_2 = min_2 + margin
            usable_max_2 = max_2 - margin
        
        positions_3d = []
        
        if count == 1:
            # Single connector at centroid
            centroid = np.zeros(3)
            centroid[axis] = interface_pos
            centroid[ax1] = (min_1 + max_1) / 2
            centroid[ax2] = (min_2 + max_2) / 2
            positions_3d.append(centroid)
        else:
            # Distribute connectors in a grid pattern
            width = usable_max_1 - usable_min_1
            height = usable_max_2 - usable_min_2
            
            # Check if there's enough space for multiple connectors
            # Each connector needs at least 2x diameter of space
            min_spacing = margin * 2  # Minimum space between connector centers
            max_per_axis_1 = max(1, int(width / min_spacing)) if width > 0 else 1
            max_per_axis_2 = max(1, int(height / min_spacing)) if height > 0 else 1
            max_connectors = max_per_axis_1 * max_per_axis_2
            
            if count > max_connectors:
                logger.warning(f"Requested {count} connectors but only room for {max_connectors}. Reducing count.")
                count = max_connectors
            
            # If space is too small, just use 1 connector at center
            if width < margin or height < margin:
                logger.warning(f"Cut face too small for multiple connectors ({width:.1f}x{height:.1f}), using single centered connector")
                centroid = np.zeros(3)
                centroid[axis] = interface_pos
                centroid[ax1] = (min_1 + max_1) / 2
                centroid[ax2] = (min_2 + max_2) / 2
                positions_3d.append(centroid)
            else:
                if width > height:
                    n_cols = min(count, max(2, int(np.sqrt(count * 2))))
                    n_rows = max(1, (count + n_cols - 1) // n_cols)
                else:
                    n_rows = min(count, max(2, int(np.sqrt(count * 2))))
                    n_cols = max(1, (count + n_rows - 1) // n_rows)
                
                step_1 = width / max(n_cols, 1)
                step_2 = height / max(n_rows, 1)
                
                found = 0
                for row in range(n_rows):
                    for col in range(n_cols):
                        if found >= count:
                            break
                        
                        pos = np.zeros(3)
                        pos[axis] = interface_pos
                        pos[ax1] = usable_min_1 + (col + 0.5) * step_1
                        pos[ax2] = usable_min_2 + (row + 0.5) * step_2
                        
                        positions_3d.append(pos)
                        found += 1
                    if found >= count:
                        break
                
                # Fallback to centroid if no positions found
                if len(positions_3d) == 0:
                    centroid = np.zeros(3)
                    centroid[axis] = interface_pos
                    centroid[ax1] = (min_1 + max_1) / 2
                    centroid[ax2] = (min_2 + max_2) / 2
                    positions_3d.append(centroid)
        
        logger.info(f"Calculated {len(positions_3d)} connector positions: {positions_3d}")
        return positions_3d
        
    except Exception as e:
        logger.warning(f"Profile analysis failed: {e}, using fallback")
        return _fallback_connector_positions(mesh, axis, interface_pos, count)


def _fallback_connector_positions(
    mesh: 'trimesh.Trimesh',
    axis: int,
    interface_pos: float,
    count: int
) -> List[np.ndarray]:
    """
    Fallback connector placement using mesh bounds when profile analysis fails.
    """
    bounds = mesh.bounds
    perp_axes = [a for a in range(3) if a != axis]
    
    positions = []
    
    # Simple linear distribution along the longest perpendicular axis
    main_perp = perp_axes[0]
    other_perp = perp_axes[1]
    
    if bounds[1][perp_axes[1]] - bounds[0][perp_axes[1]] > bounds[1][perp_axes[0]] - bounds[0][perp_axes[0]]:
        main_perp, other_perp = other_perp, main_perp
    
    for i in range(count):
        t = (i + 0.5) / count
        pos = np.zeros(3)
        pos[axis] = interface_pos
        
        # Position along main perpendicular axis (with 20% margin)
        margin = 0.2
        pos[main_perp] = bounds[0][main_perp] + (bounds[1][main_perp] - bounds[0][main_perp]) * (margin + t * (1 - 2 * margin))
        
        # Center on other perpendicular axis
        pos[other_perp] = (bounds[0][other_perp] + bounds[1][other_perp]) / 2
        
        positions.append(pos)
    
    logger.info(f"Fallback placement: {len(positions)} positions")
    return positions


def _apply_connectors(
    output_dir: Path,
    parts: List[Dict[str, Any]],
    part_coords: List[Tuple[int, int, int]],
    grid: Dict[str, int],
    original_bounds: np.ndarray,
    joint_type: str,
    joint_params: Dict[str, Any],
    dovetail_params: Dict[str, Any],
    base_name: str
) -> Dict[str, Any]:
    """
    Apply connectors to sliced parts using Blender service.
    
    Args:
        output_dir: Directory containing part files
        parts: List of part info dicts
        part_coords: Grid coordinates for each part
        grid: Grid dimensions
        original_bounds: Original mesh bounds
        joint_type: 'pins', 'dowels', or 'dovetails'
        joint_params: Parameters for pins/dowels
        dovetail_params: Parameters for dovetails
        base_name: Base name for output files
        
    Returns:
        Dictionary with:
        - 'modified_parts': Updated parts list
        - 'warnings': Warning messages
        - 'blender_required': True if Blender unavailable
        - 'dowel_files': Generated dowel STL files
    """
    result = {
        'modified_parts': None,
        'warnings': [],
        'blender_required': False,
        'dowel_files': []
    }
    
    # Check Blender service availability
    try:
        from .blender_client import BlenderClient
        client = BlenderClient()
        if not client.is_available():
            logger.warning("Blender service not available for connectors")
            result['blender_required'] = True
            result['warnings'].append(
                "Blender service is not available. Connectors could not be applied. "
                "Would you like to continue without connectors?"
            )
            return result
    except ImportError as e:
        logger.error(f"Could not import BlenderClient: {e}")
        result['blender_required'] = True
        result['warnings'].append("Blender client not available. Connectors skipped.")
        return result
    
    logger.info(f"Applying {joint_type} connectors to {len(parts)} parts")
    
    # Find adjacent part pairs
    coord_to_idx = {coord: idx for idx, coord in enumerate(part_coords)}
    adjacent_pairs = []  # List of ((idx_a, idx_b), axis, interface_position)
    
    for i, coord in enumerate(part_coords):
        for axis in range(3):
            neighbor_coord = list(coord)
            neighbor_coord[axis] += 1
            neighbor_coord = tuple(neighbor_coord)
            
            if neighbor_coord in coord_to_idx:
                j = coord_to_idx[neighbor_coord]
                
                # Calculate interface position (where the cut was made)
                bounds_a = original_bounds
                size = bounds_a[1] - bounds_a[0]
                grid_vals = [grid.get('x', 1), grid.get('y', 1), grid.get('z', 1)]
                
                cut_idx = coord[axis] + 1  # Which cut number (1-indexed)
                interface_pos = bounds_a[0][axis] + size[axis] * cut_idx / grid_vals[axis]
                
                adjacent_pairs.append(((i, j), axis, interface_pos))
    
    logger.info(f"Found {len(adjacent_pairs)} adjacent pairs")
    
    # Build connector definitions for each part
    part_connectors = {i: [] for i in range(len(parts))}
    
    diameter = joint_params.get('diameter', 4.0)
    height = joint_params.get('height', 5.0)
    clearance = joint_params.get('clearance', 0.2)
    count = joint_params.get('count', 2)
    shape = joint_params.get('shape', 'circle')  # Shape support
    if count == 0:
        count = 2  # Default to 2 connectors per interface
    
    # Calculate connector positions for each interface using profile-based placement
    for (idx_a, idx_b), axis, _ in adjacent_pairs:  # Ignore original interface_pos
        # Load Part A's mesh to calculate connector positions
        part_a_path = parts[idx_a]['filepath']
        part_a_mesh = trimesh.load(part_a_path)
        
        # Part A's interface is at its MAX bound (positive side, facing Part B)
        part_a_bounds = part_a_mesh.bounds
        interface_pos_a = part_a_bounds[1][axis]
        
        # Part B's interface should be at the same position (or very close)
        # We'll verify this but use Part A's calculation for both
        part_b_path = parts[idx_b]['filepath']
        part_b_mesh = trimesh.load(part_b_path)
        part_b_bounds = part_b_mesh.bounds
        interface_pos_b = part_b_bounds[0][axis]
        
        logger.info(f"Parts {idx_a+1}-{idx_b+1}: A interface at {interface_pos_a:.2f}, B interface at {interface_pos_b:.2f}")
        
        # Get connector positions from PART A ONLY
        # These will be used for BOTH parts to ensure perfect alignment
        connector_positions = _get_profile_connector_positions(
            mesh=part_a_mesh,
            axis=axis,
            interface_pos=interface_pos_a,
            count=count,
            margin=diameter
        )
        
        if not connector_positions:
            logger.warning(f"No connector positions found for parts {idx_a+1}-{idx_b+1}")
            continue
        
        logger.info(f"Found {len(connector_positions)} connector positions for interface")
        
        # Normal pointing in positive axis direction (from part A toward part B)
        normal_a = [0.0, 0.0, 0.0]
        normal_a[axis] = 1.0
        
        # Normal for Part B points in negative axis direction (toward Part A)
        normal_b = [0.0, 0.0, 0.0]
        normal_b[axis] = -1.0
        
        # Calculate safe depth to prevent holes from intersecting in the center
        # Use the MINIMUM dimension to prevent holes from different faces meeting
        # (e.g., X-axis hole and Y-axis hole meeting in a corner)
        part_size = part_a_bounds[1] - part_a_bounds[0]  # [x, y, z] dimensions
        min_dimension = min(part_size[0], part_size[1], part_size[2])
        
        # Safe depth is 25% of minimum dimension
        # This ensures holes from ANY face (X, Y, or Z) won't meet in the center
        # With 25%, even if 4 holes meet at a corner point, they won't intersect
        max_safe_depth = min_dimension * 0.25
        
        # Also cap at user-requested height if smaller
        effective_height = min(height, max_safe_depth)
        if effective_height < height:
            logger.warning(f"Reducing connector depth from {height} to {effective_height:.1f} to prevent intersection (min dim: {min_dimension:.1f})")
        
        for pos in connector_positions:
            pos_list = list(pos)
            
            # Create position for Part B with the same perpendicular coordinates
            # but using Part B's interface position for the cut axis
            pos_b_list = pos_list.copy()
            pos_b_list[axis] = interface_pos_b  # Use Part B's interface coordinate
            
            if joint_type == 'pins':
                # Part A gets holes
                # Hole depth = pin_half + margin + overlap_compensation
                # Pin half = effective_height / 2 (since pin is centered, half sticks out)
                # We use effective_height + 1.5 to ensure: 
                #   - 1mm deeper than pin for easy insertion
                #   - 0.5mm to compensate for positioning overlap in Blender
                part_connectors[idx_a].append({
                    'position': pos_list,
                    'normal': normal_a.copy(),
                    'diameter': diameter + clearance,  # Hole slightly larger
                    'depth': effective_height + 1.5,  # Hole deeper to fit pin + margin
                    'type': 'hole',
                    'shape': shape
                })
                
                # Part B gets pins at the SAME perpendicular position
                part_connectors[idx_b].append({
                    'position': pos_b_list,
                    'normal': normal_b.copy(),
                    'diameter': diameter,
                    'depth': effective_height,
                    'type': 'pin',
                    'shape': shape
                })
            elif joint_type == 'dowels':
                # Both parts get holes for external dowel
                part_connectors[idx_a].append({
                    'position': pos_list,
                    'normal': normal_a.copy(),
                    'diameter': diameter + clearance,
                    'depth': effective_height / 2 + 1,
                    'type': 'hole',
                    'shape': shape
                })
                
                part_connectors[idx_b].append({
                    'position': pos_b_list,
                    'normal': normal_b.copy(),
                    'diameter': diameter + clearance,
                    'depth': effective_height / 2 + 1,
                    'type': 'hole',
                    'shape': shape
                })
    
    # Generate printable dowel files if using dowels
    if joint_type == 'dowels' and adjacent_pairs:
        dowel_count = len(adjacent_pairs) * count
        logger.info(f"Generating {dowel_count} printable dowels (shape={shape})")
        
        # Map shape to section count for trimesh.creation.cylinder
        shape_sections = {
            'circle': 32,
            'square': 4,
            'triangle': 3,
            'hexagon': 6
        }
        sections = shape_sections.get(shape, 32)
        
        # Create a single dowel mesh
        dowel = trimesh.creation.cylinder(
            radius=diameter / 2,
            height=height,
            sections=sections
        )
        
        # Export single dowel
        dowel_path = output_dir / f"{base_name}_dowel_{shape}_d{diameter}mm_h{height}mm.stl"
        dowel.export(str(dowel_path))
        
        result['dowel_files'].append({
            'filepath': str(dowel_path),
            'filename': dowel_path.name,
            'count_needed': dowel_count,
            'diameter': diameter,
            'height': height
        })
        
        logger.info(f"Created dowel template: {dowel_path.name} (need {dowel_count} copies)")
    
    # Call Blender service to apply connectors to each part
    modified_parts = list(parts)  # Copy
    
    for idx, connectors in part_connectors.items():
        if not connectors:
            continue
            
        part_info = parts[idx]
        input_path = part_info['filepath']
        output_path = input_path.replace('.stl', '_conn.stl')
        
        try:
            logger.info(f"Applying {len(connectors)} connectors to part {idx + 1}")
            
            # Call Blender service to add connectors
            response = client.process_file(
                input_path=input_path,
                output_path=output_path,
                operation='script',
                script_path='connectors.py',
                params={'connectors': connectors}
            )
            
            if response.get('status') == 'success':
                # NOTE: Skipping repair step as it was destroying connector holes
                # The Blender boolean operations produce clean enough geometry
                
                # Read connector manifest to get failure info
                manifest_path = output_path.replace('.stl', '_manifest.json')
                connector_results = []
                if os.path.exists(manifest_path):
                    import json
                    with open(manifest_path, 'r') as f:
                        manifest_data = json.load(f)
                        connector_results = manifest_data.get('connectors', [])
                        if manifest_data.get('failed', 0) > 0:
                            logger.warning(f"Part {idx + 1}: {manifest_data['failed']} connector(s) failed")
                
                # Merge failure info into connector positions
                updated_connectors = []
                for i, conn in enumerate(connectors):
                    conn_copy = dict(conn)  # Make a copy
                    # Find matching result by index
                    for res in connector_results:
                        if res.get('index') == i:
                            conn_copy['failed'] = res.get('failed', False)
                            break
                    else:
                        conn_copy['failed'] = False  # Default to not failed if no match
                    updated_connectors.append(conn_copy)
                
                # Update part info with connector path and positions for visualization
                modified_parts[idx] = {
                    **part_info,
                    'filepath': output_path,
                    'filename': Path(output_path).name,
                    'has_connectors': True,
                    'connector_positions': updated_connectors  # Include positions with failure flags
                }
                logger.info(f"  Successfully applied connectors to part {idx + 1}")
            else:
                result['warnings'].append(f"Failed to apply connectors to part {idx + 1}: {response.get('message', 'Unknown error')}")
                logger.warning(f"Connector application failed: {response}")
                
        except Exception as e:
            logger.error(f"Error applying connectors to part {idx + 1}: {e}")
            result['warnings'].append(f"Error applying connectors to part {idx + 1}: {str(e)}")
    
    result['modified_parts'] = modified_parts
    return result


def _euler_to_normal(x_deg, y_deg, z_deg):
    """Convert Euler angles (degrees) to Normal Vector"""
    # Assuming XYZ order
    x = math.radians(x_deg)
    y = math.radians(y_deg)
    z = math.radians(z_deg)
    
    # Rotation Matrices
    rx = np.array([
        [1, 0, 0],
        [0, np.cos(x), -np.sin(x)],
        [0, np.sin(x), np.cos(x)]
    ])
    
    ry = np.array([
        [np.cos(y), 0, np.sin(y)],
        [0, 1, 0],
        [-np.sin(y), 0, np.cos(y)]
    ])
    
    rz = np.array([
        [np.cos(z), -np.sin(z), 0],
        [np.sin(z), np.cos(z), 0],
        [0, 0, 1]
    ])
    
    # Initial normal (Plane starts default normal usually Z=1 or Y=1 depending on definition)
    # THREE.PlaneGeometry is X-Y plane facing Z.
    # So initial normal is (0, 0, 1)
    
    v = np.array([0, 0, 1])
    
    # Rotate: Rz * Ry * Rx * v
    r_comb = rz @ ry @ rx
    v_rot = r_comb @ v
    
    return v_rot.tolist()


def calculate_model_dimensions(mesh: 'trimesh.Trimesh') -> Dict[str, float]:
    """
    Calculate the dimensions of a mesh from its bounding box.
    
    Args:
        mesh: Input trimesh mesh
        
    Returns:
        Dictionary with x, y, z dimensions in mm
    """
    bounds = mesh.bounds
    dimensions = {
        'x': float(bounds[1][0] - bounds[0][0]),
        'y': float(bounds[1][1] - bounds[0][1]),
        'z': float(bounds[1][2] - bounds[0][2]),
    }
    return dimensions


def calculate_fit_planes(
    model_dims: Dict[str, float],
    printer_dims: Dict[str, float],
    model_units: str = 'mm',
    desired_size: float = None
) -> Dict[str, int]:
    """
    Calculate the number of cutting planes needed to fit a model into a printer's build volume.
    
    Args:
        model_dims: Model dimensions dict with x, y, z in model units
        printer_dims: Printer build volume dict with x, y, z in mm
        model_units: Units of the model ('mm', 'cm', or 'in')
        desired_size: Optional target size for the longest dimension in mm
        
    Returns:
        Dictionary with number of planes needed per axis {x, y, z}
    """
    # Unit conversion factors to mm
    unit_factors = {
        'mm': 1.0,
        'cm': 10.0,
        'in': 25.4,
        'm': 1000.0,
        'ft': 304.8,
    }
    
    # Convert model dimensions to mm
    factor = unit_factors.get(model_units, 1.0)
    model_dims_mm = {
        'x': model_dims['x'] * factor,
        'y': model_dims['y'] * factor,
        'z': model_dims['z'] * factor,
    }
    
    # Apply scaling if desired size is specified
    if desired_size is not None and desired_size > 0:
        # Find longest dimension
        max_dim = max(model_dims_mm.values())
        if max_dim > 0:
            scale_factor = desired_size / max_dim
            model_dims_mm = {
                axis: dim * scale_factor
                for axis, dim in model_dims_mm.items()
            }
            logger.info(f"Scaling model by {scale_factor:.3f}x to achieve desired size of {desired_size}mm")
    
    # Calculate planes needed per axis
    # If model_dim <= printer_dim: 0 planes (no cutting needed)
    # If model_dim > printer_dim: ceil(model_dim / printer_dim) - 1 planes
    planes = {}
    for axis in ['x', 'y', 'z']:
        model_dim = model_dims_mm[axis]
        printer_dim = printer_dims[axis]
        
        if model_dim <= printer_dim:
            planes[axis] = 0
        else:
            # Number of sections needed
            sections_needed = math.ceil(model_dim / printer_dim)
            # Number of cuts = sections - 1
            planes[axis] = sections_needed - 1
        
        logger.info(f"Axis {axis.upper()}: Model={model_dim:.1f}mm, Printer={printer_dim:.1f}mm, Planes={planes[axis]}")

    return planes


def validate_mesh(mesh: 'trimesh.Trimesh') -> Dict[str, Any]:
    """
    Validate mesh for common 3D printing issues.
    
    Args:
        mesh: Input trimesh mesh to validate
        
    Returns:
        Dictionary containing:
        - valid (bool): True if mesh passes all checks
        - issues (List[str]): List of human-readable issue descriptions
    """
    if not TRIMESH_AVAILABLE:
        return {'valid': True, 'issues': ['Validation unavailable']}
    
    issues = []
    
    try:
        # Check if mesh is empty
        if mesh.is_empty:
            issues.append("Empty geometry")
            return {'valid': False, 'issues': issues}
        
        # Check if watertight (no open edges/holes)
        if not mesh.is_watertight:
            issues.append("Open edges detected (not watertight)")
        
        # Check for split bodies (disconnected meshes)
        try:
            # only_watertight=False ensures we split even if parts have holes
            split_meshes = mesh.split(only_watertight=False)
            
            # Filter out noise (tiny artifacts with few faces)
            # Slicing can sometimes create tiny floating shards
            significant_bodies = [m for m in split_meshes if len(m.faces) > 50]
            
            if len(significant_bodies) > 1:
                issues.append(f"Contains {len(significant_bodies)} disconnected bodies")
        except Exception as e:
            logger.debug(f"Could not check for split bodies: {e}")
        
        # Check if it's a valid volume
        if not mesh.is_volume:
            issues.append("Not a valid volume")
        
        # Additional basic checks
        if len(mesh.vertices) == 0:
            issues.append("No vertices")
        
        if len(mesh.faces) == 0:
            issues.append("No faces")
            
    except Exception as e:
        logger.error(f"Error during mesh validation: {e}")
        issues.append(f"Validation error: {str(e)}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues
    }

