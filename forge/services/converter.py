"""
STL to STEP Converter Service

Uses pythonocc-core for OpenCASCADE-based conversion.
Falls back to trimesh mesh repair if pythonocc is not available.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import pythonocc-core
PYTHONOCC_AVAILABLE = False
try:
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.StlAPI import StlAPI_Reader
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCC.Core.TopoDS import TopoDS_Shape
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    PYTHONOCC_AVAILABLE = True
    logger.info("pythonocc-core is available for STL to STEP conversion")
except ImportError:
    logger.warning("pythonocc-core not available. STL to STEP conversion will be limited.")


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
        ImportError: If pythonocc-core is not available
    """
    if not PYTHONOCC_AVAILABLE:
        raise ImportError(
            "pythonocc-core is required for STL to STEP conversion. "
            "Install with: conda install -c conda-forge pythonocc-core"
        )
    
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Optionally repair mesh first
    working_path = input_path
    if repair:
        repaired_path = input_path.parent / f"{input_path.stem}_repaired.stl"
        if repair_mesh_with_trimesh(str(input_path), str(repaired_path)):
            working_path = repaired_path
    
    try:
        # Step 1: Read STL file
        logger.info(f"Reading STL file: {working_path}")
        stl_reader = StlAPI_Reader()
        shape = TopoDS_Shape()
        
        if not stl_reader.Read(shape, str(working_path)):
            raise RuntimeError(f"Failed to read STL file: {working_path}")
        
        # Step 2: Sew the faces together
        logger.info(f"Sewing faces with tolerance {tolerance}")
        sewer = BRepBuilderAPI_Sewing(tolerance)
        sewer.Add(shape)
        sewer.Perform()
        sewn_shape = sewer.SewedShape()
        
        # Step 3: Try to create a solid
        logger.info("Creating solid from sewn shape")
        try:
            solid_maker = BRepBuilderAPI_MakeSolid()
            solid_maker.Add(sewn_shape)
            if solid_maker.IsDone():
                final_shape = solid_maker.Solid()
            else:
                logger.warning("Could not create solid, using sewn shell instead")
                final_shape = sewn_shape
        except Exception as e:
            logger.warning(f"Solid creation failed: {e}, using sewn shell")
            final_shape = sewn_shape
        
        # Step 4: Write STEP file
        logger.info(f"Writing STEP file: {output_path}")
        step_writer = STEPControl_Writer()
        step_writer.Transfer(final_shape, STEPControl_AsIs)
        
        status = step_writer.Write(str(output_path))
        if status != 1:  # IFSelect_RetDone = 1
            raise RuntimeError(f"Failed to write STEP file, status: {status}")
        
        logger.info(f"Successfully converted {input_path} to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"STL to STEP conversion failed: {e}")
        raise RuntimeError(f"Conversion failed: {e}")
    
    finally:
        # Clean up repaired file if created
        if repair and working_path != input_path:
            try:
                working_path.unlink()
            except:
                pass
