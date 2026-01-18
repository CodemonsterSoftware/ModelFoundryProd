"""
Grid-based mesh slicer with joint generation.

Uses trimesh for slicing and boolean operations.
"""
import logging
import math
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


def slice_mesh_grid(
    input_path: str,
    output_dir: str,
    grid: Dict[str, int],
    joint_type: str = 'none',
    joint_params: Dict[str, Any] = None,
    dovetail_params: Dict[str, Any] = None
) -> List[str]:
    """
    Slice a mesh into a grid of parts with optional joints.
    
    Args:
        input_path: Path to input STL file
        output_dir: Directory to save sliced parts
        grid: Dictionary with 'x', 'y', 'z' division counts
        joint_type: 'none', 'pins', 'dowels', or 'dovetails'
        joint_params: Parameters for pins/dowels
        dovetail_params: Parameters for dovetails
        
    Returns:
        List of output file paths
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh is required for slicing. pip install trimesh")
    
    joint_params = joint_params or {}
    dovetail_params = dovetail_params or {}
    
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Load mesh
    logger.info(f"Loading mesh: {input_path}")
    mesh = trimesh.load(input_path)
    
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("Input must be a single mesh, not a scene")
    
    # Get bounding box
    bounds = mesh.bounds
    min_pt = bounds[0]
    max_pt = bounds[1]
    size = max_pt - min_pt
    
    logger.info(f"Mesh bounds: {min_pt} to {max_pt}, size: {size}")
    
    # Calculate slice positions for each axis
    grid_x = grid.get('x', 1)
    grid_y = grid.get('y', 1)
    grid_z = grid.get('z', 1)
    
    x_cuts = [min_pt[0] + size[0] * i / grid_x for i in range(1, grid_x)]
    y_cuts = [min_pt[1] + size[1] * i / grid_y for i in range(1, grid_y)]
    z_cuts = [min_pt[2] + size[2] * i / grid_z for i in range(1, grid_z)]
    
    logger.info(f"Grid: {grid_x}x{grid_y}x{grid_z}, cuts: X={x_cuts}, Y={y_cuts}, Z={z_cuts}")
    
    # Perform hierarchical slicing
    output_files = []
    parts = [mesh]
    part_coords = [(0, 0, 0)]  # Track grid coordinates for naming
    
    # Slice along X axis
    if x_cuts:
        new_parts = []
        new_coords = []
        for part, coord in zip(parts, part_coords):
            sliced = _slice_along_axis(part, x_cuts, axis=0)
            for i, p in enumerate(sliced):
                new_parts.append(p)
                new_coords.append((i, coord[1], coord[2]))
        parts = new_parts
        part_coords = new_coords
    
    # Slice along Y axis
    if y_cuts:
        new_parts = []
        new_coords = []
        for part, coord in zip(parts, part_coords):
            sliced = _slice_along_axis(part, y_cuts, axis=1)
            for i, p in enumerate(sliced):
                new_parts.append(p)
                new_coords.append((coord[0], i, coord[2]))
        parts = new_parts
        part_coords = new_coords
    
    # Slice along Z axis
    if z_cuts:
        new_parts = []
        new_coords = []
        for part, coord in zip(parts, part_coords):
            sliced = _slice_along_axis(part, z_cuts, axis=2)
            for i, p in enumerate(sliced):
                new_parts.append(p)
                new_coords.append((coord[0], coord[1], i))
        parts = new_parts
        part_coords = new_coords
    
    # Apply joints if requested
    if joint_type != 'none' and len(parts) > 1:
        logger.info(f"Applying {joint_type} joints to {len(parts)} parts")
        parts = _apply_joints(
            parts, 
            part_coords,
            joint_type, 
            joint_params, 
            dovetail_params,
            grid
        )
    
    # Export parts
    base_name = input_path.stem
    for i, (part, coord) in enumerate(zip(parts, part_coords)):
        filename = f"{base_name}_part_{coord[0]}_{coord[1]}_{coord[2]}.stl"
        filepath = output_dir / filename
        part.export(str(filepath))
        output_files.append(str(filepath))
        logger.info(f"Exported part {i+1}/{len(parts)}: {filename}")
    
    return output_files


def _slice_along_axis(
    mesh: 'trimesh.Trimesh',
    cut_positions: List[float],
    axis: int
) -> List['trimesh.Trimesh']:
    """
    Slice a mesh at multiple positions along a single axis.
    
    Args:
        mesh: Input trimesh object
        cut_positions: List of positions to cut at
        axis: 0=X, 1=Y, 2=Z
        
    Returns:
        List of mesh parts
    """
    if not cut_positions:
        return [mesh]
    
    normal = [0, 0, 0]
    parts = []
    remaining = mesh
    
    for pos in sorted(cut_positions):
        origin = [0, 0, 0]
        origin[axis] = pos
        
        # Slice keeping negative side (before cut)
        normal[axis] = -1
        try:
            left = remaining.slice_mesh_plane(
                plane_origin=origin,
                plane_normal=normal,
                cap=True
            )
            if left is not None and len(left.vertices) > 0:
                parts.append(left)
        except Exception as e:
            logger.warning(f"Slice failed at {pos}: {e}")
        
        # Keep positive side for next iteration
        normal[axis] = 1
        try:
            remaining = remaining.slice_mesh_plane(
                plane_origin=origin,
                plane_normal=normal,
                cap=True
            )
        except Exception as e:
            logger.warning(f"Remaining slice failed at {pos}: {e}")
            break
    
    # Add the final remaining piece
    if remaining is not None and len(remaining.vertices) > 0:
        parts.append(remaining)
    
    return parts


def _apply_joints(
    parts: List['trimesh.Trimesh'],
    coords: List[Tuple[int, int, int]],
    joint_type: str,
    joint_params: Dict[str, Any],
    dovetail_params: Dict[str, Any],
    grid: Dict[str, int]
) -> List['trimesh.Trimesh']:
    """
    Apply joints between adjacent parts.
    
    This is a placeholder that will be expanded with actual joint generation.
    """
    from .joints import apply_joints_to_parts
    
    return apply_joints_to_parts(
        parts=parts,
        coords=coords,
        joint_type=joint_type,
        joint_params=joint_params,
        dovetail_params=dovetail_params,
        grid=grid
    )
