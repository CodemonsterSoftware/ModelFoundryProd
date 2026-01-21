import bpy
import sys
import os
import json
import logging
from flask import Flask, request, jsonify
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("blender_server")

app = Flask(__name__)

# Ensure we can import modules installed in Blender's python
# (Sometimes needed if path isn't perfectly set, though Dockerfile handles it)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "blender_version": bpy.app.version_string,
        "python_version": sys.version
    })

@app.route('/process', methods=['POST'])
def process():
    """
    Generic endpoint to process a file using a specified script or function.
    Expected JSON body:
    {
        "input_file": "path/to/file.stl", (relative to /app/media)
        "output_file": "path/to/output.step",
        "operation": "convert_stl_to_step" | "slice" | ...
        "params": {}
    }
    """
    data = request.json
    logger.info(f"Received task: {data}")
    
    try:
        # Clear existing scene
        bpy.ops.wm.read_factory_settings(use_empty=True)
        
        operation = data.get('operation')
        input_file = data.get('input_file')
        
        # Resolve path - assuming mounted volume at /app/media
        # The user app (Django) should provide paths relative to media root
        # Here we prepend /app/media/
        full_input_path = os.path.join("/app/media", input_file) if input_file else None
        
        if operation == 'import_stl':
            if not os.path.exists(full_input_path):
                return jsonify({"error": f"File not found: {full_input_path}"}), 404
            bpy.ops.import_mesh.stl(filepath=full_input_path)
            return jsonify({"status": "success", "message": "Imported STL"})
            
        elif operation == 'script':
            # Run a provided script content? Dangerous but flexible for this stage.
            # Better: load a script file from the shared volume or local app dir
            script_path = data.get('script_path')
            if script_path:
                # Check if script exists as provided (e.g. absolute or relative to CWD)
                if os.path.exists(script_path):
                    full_script_path = script_path
                # Check in /app/media
                elif os.path.exists(os.path.join("/app/media", script_path)):
                    full_script_path = os.path.join("/app/media", script_path)
                # Check in current directory (e.g. /app)
                elif os.path.exists(os.path.join("/app", script_path)):
                    full_script_path = os.path.join("/app", script_path)
                else:
                    return jsonify({"error": f"Script not found: {script_path}"}), 404
                
                # Execute the script
                # We can use exec(open(path).read()) 
                # passing a context allows the script to access 'data'
                global_vars = globals().copy()
                global_vars['request_data'] = data
                
                exec(open(full_script_path).read(), global_vars)
                
                return jsonify({"status": "success", "message": f"Executed script {script_path}"})
        
        # Placeholder for more native operations
        
        return jsonify({"status": "success", "message": "Task processed (dry run)"})

    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e), "traceback": traceback.format_exc()}), 500

def run_server():
    # Disable Blender's auto-save to prevent clutter
    bpy.context.preferences.filepaths.save_version = 0
    
    logger.info("Starting Flask server on port 8081 inside Blender...")
    # debug=False, threaded=True is default. 
    # use_reloader=False is critical because we are in Blender
    # threaded=False is CRITICAL because bpy is not thread-safe.
    app.run(host='0.0.0.0', port=8081, debug=False, use_reloader=False, threaded=False)

if __name__ == '__main__':
    run_server()
