import bpy
import os
import sys
import subprocess
import time

# This script runs in BLENDER's python
# It handles mesh repair and coordinates the next step.

# Expected global variables from server.py execution context:
# request_data = { "input_file": ..., "output_file": ..., "params": { "repair": True, "tolerance": 0.1 } }

def log(msg):
    print(f"[Blender] {msg}", flush=True)

def get_file_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

try:
    start_time = time.time()
    
    data = request_data
    input_rel = data.get('input_file')
    output_rel = data.get('output_file')
    params = data.get('params', {})
    
    repair = params.get('repair_mesh', True)
    tolerance = float(params.get('tolerance', 0.1))

    # Paths are relative to /app/media inside container
    base_path = "/app/media"
    
    # Resolve absolute paths
    if not input_rel.startswith("/"):
        input_path = os.path.join(base_path, input_rel)
    else:
        input_path = input_rel
        
    if not output_rel.startswith("/"):
        output_path = os.path.join(base_path, output_rel)
    else:
        output_path = output_rel

    log(f"=== CONVERSION STARTED ===")
    log(f"Input: {input_path}")
    log(f"Output: {output_path}")
    log(f"Repair: {repair}, Tolerance: {tolerance}")

    # Step 1: Mesh Repair with Blender
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    input_size = get_file_size_mb(input_path)
    log(f"Input file size: {input_size:.2f} MB")
    
    log("Step 1/4: Resetting Blender scene...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    log("Step 2/4: Importing STL...")
    import_start = time.time()
    bpy.ops.import_mesh.stl(filepath=input_path)
    log(f"  Import completed in {time.time() - import_start:.2f}s")
    
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    vertex_count = len(obj.data.vertices)
    face_count = len(obj.data.polygons)
    log(f"  Mesh loaded: {vertex_count:,} vertices, {face_count:,} faces")
    
    if repair:
        log("Step 3/4: Repairing mesh...")
        repair_start = time.time()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        
        log("  - Removing doubles...")
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        
        log("  - Filling holes...")
        bpy.ops.mesh.fill_holes(sides=4)
        
        log("  - Fixing normals...")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        
        log("  - Triangulating...")
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
        
        bpy.ops.object.mode_set(mode='OBJECT')
        log(f"  Repair completed in {time.time() - repair_start:.2f}s")
    else:
        log("Step 3/4: Skipping repair (disabled)")
        
    # Export intermediate STL for OCP
    temp_stl = os.path.join(base_path, f"temp_{os.path.basename(input_path)}")
    log("Step 4/4: Exporting cleaned STL for STEP conversion...")
    export_start = time.time()
    bpy.ops.export_mesh.stl(filepath=temp_stl, use_selection=True, ascii=False)
    log(f"  Export completed in {time.time() - export_start:.2f}s")
    log(f"  Temp file size: {get_file_size_mb(temp_stl):.2f} MB")
    
    # Step 2: Call System Python for OCP Conversion
    script_dir = os.getcwd()
    step_export_script = os.path.join(script_dir, "step_export.py")
    
    log("=== STARTING OCP CONVERSION ===")
    
    cmd = ["python3", step_export_script, temp_stl, output_path, "--tolerance", str(tolerance)]
    
    # Use Popen for real-time output
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Stream output in real-time
    for line in process.stdout:
        print(line, end='', flush=True)
    
    process.wait()
        
    if process.returncode != 0:
        raise RuntimeError(f"OCP process failed with code {process.returncode}")
        
    # Cleanup
    if os.path.exists(temp_stl):
        os.remove(temp_stl)
    
    total_time = time.time() - start_time
    output_size = get_file_size_mb(output_path)
    log(f"=== CONVERSION COMPLETE ===")
    log(f"Output file size: {output_size:.2f} MB")
    log(f"Total time: {total_time:.2f}s")

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e
