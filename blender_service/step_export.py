import sys
import os
import argparse
import time

# This script runs in SYSTEM PYTHON (not Blender's python)
# It expects an input STL and output STEP path.

def log(msg):
    print(f"[OCP] {msg}", flush=True)

def get_file_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

try:
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCP.StlAPI import StlAPI_Reader
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.TopoDS import TopoDS_Shape, TopoDS
    from OCP.IFSelect import IFSelect_RetDone
except ImportError as e:
    log(f"Failed to import OCP: {e}")
    sys.exit(1)

def convert(input_stl, output_step, tolerance=0.1):
    if not os.path.exists(input_stl):
        log(f"Input file not found: {input_stl}")
        return False
        
    try:
        total_start = time.time()
        
        # Step 1: Read STL
        log(f"Reading STL ({get_file_size_mb(input_stl):.2f} MB)...")
        read_start = time.time()
        stl_reader = StlAPI_Reader()
        shape = TopoDS_Shape()
        if not stl_reader.Read(shape, input_stl):
            log("Failed to read STL")
            return False
        log(f"  Read completed in {time.time() - read_start:.2f}s")
            
        # Step 2: Sew
        log(f"Sewing faces (tolerance={tolerance})...")
        sew_start = time.time()
        sewer = BRepBuilderAPI_Sewing(tolerance)
        sewer.Add(shape)
        sewer.Perform()
        sewn_shape = sewer.SewedShape()
        log(f"  Sewing completed in {time.time() - sew_start:.2f}s")
        
        # Step 3: Make Solid
        log("Creating solid from sewn shell...")
        solid_start = time.time()
        solid_maker = BRepBuilderAPI_MakeSolid()
        
        # Try to cast to Shell
        try:
            shell = TopoDS.Shell_s(sewn_shape)
            solid_maker.Add(shell)
            log("  Successfully cast to Shell")
        except Exception as ex:
            log(f"  Warning: Could not cast to Shell ({ex})")
            pass

        if solid_maker.IsDone():
            final_shape = solid_maker.Solid()
            log("  Solid created successfully")
        else:
            log("  Using sewn shape (solid creation incomplete)")
            final_shape = sewn_shape
        log(f"  Solid step completed in {time.time() - solid_start:.2f}s")
            
        # Step 4: Write STEP
        log(f"Writing STEP file...")
        write_start = time.time()
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_step), exist_ok=True)
        
        step_writer = STEPControl_Writer()
        step_writer.Transfer(final_shape, STEPControl_AsIs)
        status = step_writer.Write(output_step)
        
        if status == IFSelect_RetDone:
            log(f"  Write completed in {time.time() - write_start:.2f}s")
            log(f"  Output size: {get_file_size_mb(output_step):.2f} MB")
            log(f"OCP total time: {time.time() - total_start:.2f}s")
            return True
        else:
            log(f"Write failed with status {status}")
            return False
            
    except Exception as e:
        log(f"Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input STL file")
    parser.add_argument("output", help="Output STEP file")
    parser.add_argument("--tolerance", type=float, default=0.1, help="Tolerance")
    
    args = parser.parse_args()
    
    success = convert(args.input, args.output, args.tolerance)
    sys.exit(0 if success else 1)
