"""
STL to STEP Converter Service

Uses pythonocc-core for OpenCASCADE-based conversion.
Falls back to trimesh mesh repair if pythonocc is not available.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import BlenderClient
try:
    from forge.services.blender_client import BlenderClient
    BLENDER_CLIENT_AVAILABLE = True
except ImportError:
    BLENDER_CLIENT_AVAILABLE = False
    logger.warning("BlenderClient could not be imported")




def repair_mesh_with_trimesh(input_path: str, output_path: str) -> bool:
    """
    Repair a mesh using trimesh.
    
    Args:
        input_path: Path to input STL file
        output_path: Path to save repaired STL
        
    Returns:
        True if repair was successful
    """
    try:
        import trimesh
        
        mesh = trimesh.load(input_path)
        
        # Repair operations
        if hasattr(mesh, 'fill_holes'):
            mesh.fill_holes()
        if hasattr(mesh, 'fix_normals'):
            mesh.fix_normals()
        
        # Remove duplicate vertices
        mesh.merge_vertices()
        
        # Remove degenerate faces
        mesh.remove_degenerate_faces()
        
        mesh.export(output_path)
        logger.info(f"Mesh repaired and saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Mesh repair failed: {e}")
        return False


def repair_mesh_with_blender(input_path: str, output_path: str) -> bool:
    """
    Repair a mesh using Blender service.
    
    Args:
        input_path: Path to input STL file
        output_path: Path to save repaired STL
        
    Returns:
        True if repair was successful
    """
    if not BLENDER_CLIENT_AVAILABLE:
        return False
        
    try:
        client = BlenderClient()
        if not client.is_available():
            logger.debug("Blender service unavailable")
            return False
            
        logger.info(f"Attempting mesh repair with Blender: {input_path}")
        client.process_file(
            input_path=input_path,
            output_path=output_path,
            operation='script',
            script_path='repair.py'
        )
        
        # Verify output exists
        if Path(output_path).exists():
            logger.info("Blender repair successful")
            return True
        else:
            logger.warning("Blender repair reported success but output file missing")
            return False
            
    except Exception as e:
        logger.warning(f"Blender repair failed: {e}")
        return False



def convert_stl_to_step(
    input_path: str,
    output_path: str,
    repair: bool = True,
    tolerance: float = 0.1
) -> bool:
    """
    Convert an STL file to STEP format.
    
    Args:
        input_path: Path to input STL file
        output_path: Path to save STEP file
        repair: Whether to repair the mesh before conversion
        tolerance: Sewing tolerance for face merging
        
    Returns:
        True if conversion was successful
        
    Raises:
        RuntimeError: If conversion fails
        RuntimeError: If conversion fails
    """
    
    
    if not BLENDER_CLIENT_AVAILABLE:
        raise RuntimeError("BlenderClient module not found")

    try:
        client = BlenderClient()
        if client.is_available():
            logger.info(f"Delegating conversion to Blender service: {input_path}")
            result = client.process_file(
                input_path=str(input_path),
                output_path=str(output_path),
                operation='script',
                script_path='convert.py',
                params={
                    'repair_mesh': repair,
                    'tolerance': tolerance
                }
            )
            
            if Path(output_path).exists():
                logger.info(f"Blender conversion successful: {output_path}")
                return True
            else:
                raise RuntimeError("Blender service reported success but output file missing")
        else:
            raise RuntimeError("Blender service unavailable, cannot convert.")
    except Exception as e:
        logger.error(f"Blender conversion failed: {e}")
        raise RuntimeError(f"Blender conversion failed: {e}")

    

