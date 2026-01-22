import os
import sys
import logging
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_conversion")

BLENDER_URL = "http://localhost:8081"

def test_conversion():
    # 1. Check health
    try:
        resp = requests.get(f"{BLENDER_URL}/health", timeout=5)
        if resp.status_code != 200:
            logger.error("Blender service unhealthy")
            return False
        logger.info(f"Blender service UP: {resp.json()}")
    except Exception as e:
        logger.error(f"Failed to connect to Blender: {e}")
        return False

    # 2. Setup Test File
    media_dir = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    # Check for pre-generated valid STL (from container generation step)
    pre_gen_file = "test_cube_valid.stl"
    pre_gen_path = os.path.join(media_dir, pre_gen_file)
    
    if os.path.exists(pre_gen_path):
        logger.info(f"Using existing valid STL: {pre_gen_file}")
        test_file_name = pre_gen_file
        test_output_name = "test_cube_valid.step"
    else:
        # Fallback to manual creation if not found (though assume it exists from previous steps)
        test_file_name = "test_cube_manual.stl"
        test_output_name = "test_cube_manual.step"
        test_file_path = os.path.join(media_dir, test_file_name)
        logger.warning(f"Valid STL not found, creating manual ASCII STL at {test_file_path}")
        with open(test_file_path, 'w') as f:
            f.write("solid cube\n")
            f.write("facet normal 0 0 -1\nouter loop\nvertex 0 0 0\nvertex 10 0 0\nvertex 0 10 0\nendloop\nendfacet\n")
            f.write("facet normal 0 0 -1\nouter loop\nvertex 0 0 0\nvertex 0 10 0\nvertex 0 0 10\nendloop\nendfacet\n")
            f.write("facet normal 0 0 -1\nouter loop\nvertex 0 0 0\nvertex 0 0 10\nvertex 10 0 0\nendloop\nendfacet\n")
            f.write("facet normal 0 0 -1\nouter loop\nvertex 10 0 0\nvertex 0 0 10\nvertex 0 10 0\nendloop\nendfacet\n")
            f.write("endsolid cube\n")
    
    # 3. Request conversion via API
    payload = {
        "input_file": test_file_name,
        "output_file": test_output_name,
        "operation": "script",
        "script_path": "convert.py",
        "params": {
            "repair_mesh": True,
            "tolerance": 0.1
        }
    }
    
    logger.info(f"Requesting conversion for {test_file_name}...")
    try:
        start_time = time.time()
        resp = requests.post(f"{BLENDER_URL}/process", json=payload, timeout=60)
        duration = time.time() - start_time
        
        logger.info(f"Response ({duration:.2f}s): {resp.status_code}")
        logger.info(resp.text)
        
        if resp.status_code == 200:
            # Check if output exists
            output_full_path = os.path.join(media_dir, test_output_name)
            if os.path.exists(output_full_path):
                 file_size = os.path.getsize(output_full_path)
                 logger.info(f"SUCCESS: Output file created, size={file_size} bytes")
                 return True
            else:
                 logger.error("FAILURE: API returned success but file missing locally")
                 return False
        else:
            logger.error("FAILURE: API returned error")
            return False
            
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    if test_conversion():
        sys.exit(0)
    else:
        sys.exit(1)
