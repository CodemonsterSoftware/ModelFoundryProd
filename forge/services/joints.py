"""
Joint generation for sliced mesh parts.

Supports:
- Pins (peg + hole)
- Dowels (hole + hole)
- Dovetails (interlocking profile)
"""
import logging
import math
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

try:
    import trimesh
    import numpy as np
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


def apply_joints_to_parts(
    parts: List['trimesh.Trimesh'],
    coords: List[Tuple[int, int, int]],
    joint_type: str,
    joint_params: Dict[str, Any],
    dovetail_params: Dict[str, Any],
    grid: Dict[str, int]
) -> List['trimesh.Trimesh']:
    """
    Apply joints between adjacent parts based on their grid coordinates.
    
    Args:
        parts: List of mesh parts
        coords: List of (x, y, z) grid coordinates for each part
        joint_type: 'pins', 'dowels', or 'dovetails'
        joint_params: Parameters for pins/dowels
        dovetail_params: Parameters for dovetails
        grid: Grid dimensions
        
    Returns:
        List of modified mesh parts with joints
    """
    if not TRIMESH_AVAILABLE:
        logger.warning("trimesh not available, skipping joints")
        return parts
    
    # Create coordinate lookup for efficient neighbor finding
    coord_to_idx = {c: i for i, c in enumerate(coords)}
    
    # Track which parts have been modified
    modified_parts = [p.copy() for p in parts]
    
    # Find adjacent pairs and apply joints
    processed_pairs = set()
    
    for i, (part, coord) in enumerate(zip(parts, coords)):
        # Check each axis direction for neighbors
        for axis in range(3):
            neighbor_coord = list(coord)
            neighbor_coord[axis] += 1
            neighbor_coord = tuple(neighbor_coord)
            
            if neighbor_coord in coord_to_idx:
                j = coord_to_idx[neighbor_coord]
                pair_key = (min(i, j), max(i, j))
                
                if pair_key not in processed_pairs:
                    processed_pairs.add(pair_key)
                    
                    # Apply joints between parts i and j
                    if joint_type == 'pins':
                        modified_parts[i], modified_parts[j] = _apply_pins(
                            modified_parts[i], 
                            modified_parts[j],
                            axis,
                            joint_params,
                            is_positive_side=True
                        )
                    elif joint_type == 'dowels':
                        modified_parts[i], modified_parts[j] = _apply_dowels(
                            modified_parts[i],
                            modified_parts[j],
                            axis,
                            joint_params
                        )
                    elif joint_type == 'dovetails':
                        modified_parts[i], modified_parts[j] = _apply_dovetails(
                            modified_parts[i],
                            modified_parts[j],
                            axis,
                            dovetail_params
                        )
    
    logger.info(f"Applied {joint_type} joints to {len(processed_pairs)} interfaces")
    return modified_parts


def _get_interface_center(
    mesh: 'trimesh.Trimesh',
    axis: int,
    positive_side: bool
) -> np.ndarray:
    """Get the center point of the interface face."""
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2
    
    if positive_side:
        center[axis] = bounds[1][axis]
    else:
        center[axis] = bounds[0][axis]
    
    return center


def _calculate_joint_positions(
    mesh: 'trimesh.Trimesh',
    axis: int,
    count: int,
    positive_side: bool
) -> List[np.ndarray]:
    """
    Calculate evenly distributed positions for joints on an interface.
    
    Args:
        mesh: The mesh part
        axis: Cut axis (0=X, 1=Y, 2=Z)
        count: Number of joints (0 = auto)
        positive_side: Whether this is the positive side of the cut
        
    Returns:
        List of 3D positions for joint centers
    """
    bounds = mesh.bounds
    size = bounds[1] - bounds[0]
    
    # Get the two perpendicular axes
    perp_axes = [a for a in range(3) if a != axis]
    
    # Auto-calculate count if needed (roughly 1 joint per 30mm)
    if count == 0:
        min_dim = min(size[perp_axes[0]], size[perp_axes[1]])
        count = max(1, int(min_dim / 30))
    
    positions = []
    
    # Simple grid of positions
    n_per_axis = max(1, int(math.sqrt(count)))
    
    for i in range(n_per_axis):
        for j in range(n_per_axis):
            if len(positions) >= count:
                break
                
            pos = np.zeros(3)
            
            # Set position on the interface plane
            if positive_side:
                pos[axis] = bounds[1][axis]
            else:
                pos[axis] = bounds[0][axis]
            
            # Distribute across perpendicular axes
            margin = 0.15  # 15% margin from edges
            t1 = margin + (1 - 2*margin) * (i + 0.5) / n_per_axis
            t2 = margin + (1 - 2*margin) * (j + 0.5) / n_per_axis
            
            pos[perp_axes[0]] = bounds[0][perp_axes[0]] + size[perp_axes[0]] * t1
            pos[perp_axes[1]] = bounds[0][perp_axes[1]] + size[perp_axes[1]] * t2
            
            positions.append(pos)
    
    return positions


def _create_cylinder(
    center: np.ndarray,
    axis: int,
    radius: float,
    height: float,
    segments: int = 32
) -> 'trimesh.Trimesh':
    """Create a cylinder primitive aligned to an axis."""
    # Create cylinder along Z axis
    cylinder = trimesh.creation.cylinder(
        radius=radius,
        height=height,
        sections=segments
    )
    
    # Rotate to align with target axis
    if axis == 0:  # X axis
        rotation = trimesh.transformations.rotation_matrix(
            math.pi / 2, [0, 1, 0]
        )
        cylinder.apply_transform(rotation)
    elif axis == 1:  # Y axis
        rotation = trimesh.transformations.rotation_matrix(
            math.pi / 2, [1, 0, 0]
        )
        cylinder.apply_transform(rotation)
    # axis == 2 is already aligned
    
    # Translate to center position
    cylinder.apply_translation(center)
    
    return cylinder


def _apply_pins(
    part_a: 'trimesh.Trimesh',
    part_b: 'trimesh.Trimesh',
    axis: int,
    params: Dict[str, Any],
    is_positive_side: bool
) -> Tuple['trimesh.Trimesh', 'trimesh.Trimesh']:
    """
    Apply pin joints: peg on part_a, hole on part_b.
    
    Args:
        part_a: First part (gets pegs)
        part_b: Second part (gets holes)
        axis: The axis along which parts are joined
        params: Joint parameters
        is_positive_side: Whether part_a's interface is on positive side
        
    Returns:
        Tuple of modified (part_a, part_b)
    """
    diameter = params.get('diameter', 4.0)
    height = params.get('height', 5.0)
    clearance = params.get('clearance', 0.2)
    count = params.get('count', 0)
    
    radius = diameter / 2
    hole_radius = radius + clearance
    
    # Get positions on part_a's interface
    positions = _calculate_joint_positions(part_a, axis, count, is_positive_side)
    
    try:
        for pos in positions:
            # Create peg for part_a
            peg_center = pos.copy()
            if is_positive_side:
                peg_center[axis] += height / 2
            else:
                peg_center[axis] -= height / 2
                
            peg = _create_cylinder(peg_center, axis, radius, height)
            
            # Create hole for part_b (slightly larger and deeper)
            hole_center = pos.copy()
            if is_positive_side:
                hole_center[axis] -= height / 2
            else:
                hole_center[axis] += height / 2
                
            hole = _create_cylinder(hole_center, axis, hole_radius, height + clearance)
            
            # Boolean operations
            part_a = trimesh.boolean.union([part_a, peg], engine='manifold')
            part_b = trimesh.boolean.difference([part_b, hole], engine='manifold')
            
    except Exception as e:
        logger.warning(f"Pin application failed: {e}, returning original parts")
    
    return part_a, part_b


def _apply_dowels(
    part_a: 'trimesh.Trimesh',
    part_b: 'trimesh.Trimesh',
    axis: int,
    params: Dict[str, Any]
) -> Tuple['trimesh.Trimesh', 'trimesh.Trimesh']:
    """
    Apply dowel joints: holes on both parts for external dowel rod.
    """
    diameter = params.get('diameter', 6.0)
    height = params.get('height', 15.0)  # Total dowel length
    clearance = params.get('clearance', 0.2)
    count = params.get('count', 0)
    
    hole_radius = diameter / 2 + clearance
    hole_depth = height / 2 + clearance  # Each hole is half the dowel depth
    
    # Get positions on the interface
    positions = _calculate_joint_positions(part_a, axis, count, True)
    
    try:
        for pos in positions:
            # Hole in part_a (on positive interface)
            hole_center_a = pos.copy()
            hole_center_a[axis] -= hole_depth / 2
            hole_a = _create_cylinder(hole_center_a, axis, hole_radius, hole_depth)
            
            # Hole in part_b (on negative interface)  
            hole_center_b = pos.copy()
            hole_center_b[axis] += hole_depth / 2
            hole_b = _create_cylinder(hole_center_b, axis, hole_radius, hole_depth)
            
            # Boolean difference on both
            part_a = trimesh.boolean.difference([part_a, hole_a], engine='manifold')
            part_b = trimesh.boolean.difference([part_b, hole_b], engine='manifold')
            
    except Exception as e:
        logger.warning(f"Dowel application failed: {e}, returning original parts")
    
    return part_a, part_b


def _apply_dovetails(
    part_a: 'trimesh.Trimesh',
    part_b: 'trimesh.Trimesh',
    axis: int,
    params: Dict[str, Any]
) -> Tuple['trimesh.Trimesh', 'trimesh.Trimesh']:
    """
    Apply dovetail joints: interlocking profile.
    
    Creates trapezoidal tails that interlock between parts.
    """
    angle = params.get('angle', 14.0)  # degrees
    width = params.get('width', 15.0)
    depth = params.get('depth', 10.0)
    count = params.get('count', 0)
    
    # Get interface dimensions
    bounds_a = part_a.bounds
    size_a = bounds_a[1] - bounds_a[0]
    
    # Determine which axis to array dovetails along
    perp_axes = [a for a in range(3) if a != axis]
    array_axis = perp_axes[0]  # Array along first perpendicular axis
    profile_axis = perp_axes[1]  # Profile extends along second
    
    # Auto-calculate count
    if count == 0:
        count = max(1, int(size_a[array_axis] / (width * 2)))
    
    # Calculate dovetail positions
    spacing = size_a[array_axis] / (count + 1)
    
    try:
        for i in range(count):
            # Position along array axis
            t = (i + 1) / (count + 1)
            
            # Create dovetail profile (trapezoid)
            angle_rad = math.radians(angle)
            half_width_base = width / 2
            half_width_top = half_width_base + depth * math.tan(angle_rad)
            
            # Profile vertices (2D trapezoid)
            profile_2d = np.array([
                [-half_width_base, 0],
                [half_width_base, 0],
                [half_width_top, depth],
                [-half_width_top, depth],
            ])
            
            # Extrude profile to 3D
            profile_height = size_a[profile_axis] * 0.8  # 80% of dimension
            dovetail = trimesh.creation.extrude_polygon(
                trimesh.path.polygons.Polygon(profile_2d),
                height=profile_height
            )
            
            # Position the dovetail
            center = (bounds_a[0] + bounds_a[1]) / 2
            center[array_axis] = bounds_a[0][array_axis] + size_a[array_axis] * t
            center[axis] = bounds_a[1][axis]  # At interface
            
            # Apply rotation and translation based on axis orientation
            # (This is simplified - full implementation would handle all axis cases)
            dovetail.apply_translation(center)
            
            # Boolean operations
            # Part A gets the tail (positive), Part B gets the pocket (negative)
            part_a = trimesh.boolean.union([part_a, dovetail], engine='manifold')
            part_b = trimesh.boolean.difference([part_b, dovetail], engine='manifold')
            
    except Exception as e:
        logger.warning(f"Dovetail application failed: {e}, returning original parts")
    
    return part_a, part_b
