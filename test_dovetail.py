import os
import sys
import logging
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_dovetail")

BLENDER_URL = "http://localhost:8081"

def create_test_cube():
    """Create a simple cube STL using trimesh."""
    media_dir = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    test_file = os.path.join(media_dir, 'test_cube_dovetail.stl')
    
    try:
        import trimesh
        # Create a larger cube for dovetail test
        mesh = trimesh.creation.box(extents=[100, 100, 100])
        mesh.export(test_file)
        logger.info(f"Created test cube at {test_file}")
        return test_file, 'test_cube_dovetail.stl'
    except ImportError:
        logger.error("trimesh not installed - cannot create test cube")
        return None, None

def test_dovetail_cut():
    """Test cutting a cube with a dovetail plane."""
    logger.info("=== TEST: Dovetail Cutting Plane ===")
    
    # Check health
    try:
        resp = requests.get(f"{BLENDER_URL}/health", timeout=5)
        if resp.status_code != 200:
            logger.error("Blender service unhealthy")
            return False
        logger.info("Blender service is healthy")
    except Exception as e:
        logger.error(f"Failed to connect to Blender: {e}")
        return False
    
    # Create test cube
    full_path, rel_name = create_test_cube()
    if not full_path:
        return False
    
    # Define dovetail cut through the middle of the cube (Z=0 plane)
    payload = {
        "input_file": rel_name,
        "output_file": "dovetail_piece_A.stl",
        "operation": "script",
        "script_path": "dovetail.py",
        "params": {
            "output_file_b": "dovetail_piece_B.stl",
            "plane_origin": [0, 0, 0],      # Center of cube
            "plane_normal": [0, 0, 1],       # Cut along Z axis
            "dovetail_height": 8.0,          # 8mm tall teeth
            "dovetail_width": 20.0,          # 20mm wide teeth
            "dovetail_angle": 60.0,          # 60 degree angle
            "mesh_extents": [150, 150],      # Bigger than cube
            "cut_depth": 60.0                # Extend beyond cube
        }
    }
    
    logger.info("Sending dovetail cut request to Blender...")
    try:
        start = time.time()
        resp = requests.post(f"{BLENDER_URL}/process", json=payload, timeout=120)
        duration = time.time() - start
        
        logger.info(f"Response ({duration:.2f}s): {resp.status_code}")
        logger.info(resp.text)
        
        if resp.status_code == 200:
            media_dir = os.path.join(os.getcwd(), 'media')
            piece_a = os.path.join(media_dir, 'dovetail_piece_A.stl')
            piece_b = os.path.join(media_dir, 'dovetail_piece_B.stl')
            
            success = True
            if os.path.exists(piece_a):
                size = os.path.getsize(piece_a)
                logger.info(f"Piece A created: {size} bytes")
            else:
                logger.error("Piece A missing!")
                success = False
                
            if os.path.exists(piece_b):
                size = os.path.getsize(piece_b)
                logger.info(f"Piece B created: {size} bytes")
            else:
                logger.error("Piece B missing!")
                success = False
            
            if success:
                logger.info("SUCCESS: Both pieces created with dovetail cut!")
            return success
        else:
            logger.error(f"FAILURE: API returned {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dovetail_cut()
    
    print("\n=== TEST SUMMARY ===")
    print(f"  Dovetail Cut: {'PASS' if success else 'FAIL'}")
    
    sys.exit(0 if success else 1)
