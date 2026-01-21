import os
import sys
import logging
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_connectors")

BLENDER_URL = "http://localhost:8081"

def create_test_cube():
    """Create a simple cube STL using trimesh."""
    media_dir = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    test_file = os.path.join(media_dir, 'test_cube_connectors.stl')
    
    try:
        import trimesh
        mesh = trimesh.creation.box(extents=[50, 50, 50])
        mesh.export(test_file)
        logger.info(f"Created test cube at {test_file}")
        return test_file, 'test_cube_connectors.stl'
    except ImportError:
        logger.error("trimesh not installed - cannot create test cube")
        return None, None

def test_hole():
    """Test subtracting a hole from a cube."""
    logger.info("=== TEST: Hole Subtraction ===")
    
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
    
    # Define hole connector at center of top face
    payload = {
        "input_file": rel_name,
        "output_file": "test_cube_with_hole.stl",
        "operation": "script",
        "script_path": "connectors.py",
        "params": {
            "connectors": [
                {
                    "position": [0, 0, 25],  # Top of 50x50x50 cube centered at origin
                    "normal": [0, 0, -1],     # Pointing down into cube
                    "diameter": 10.0,
                    "depth": 20.0,
                    "type": "hole"
                }
            ]
        }
    }
    
    logger.info("Sending hole request to Blender...")
    try:
        start = time.time()
        resp = requests.post(f"{BLENDER_URL}/process", json=payload, timeout=120)
        duration = time.time() - start
        
        logger.info(f"Response ({duration:.2f}s): {resp.status_code}")
        logger.info(resp.text)
        
        if resp.status_code == 200:
            output_path = os.path.join(os.getcwd(), 'media', 'test_cube_with_hole.stl')
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                logger.info(f"SUCCESS: Output file created, size={size} bytes")
                return True
            else:
                logger.error("FAILURE: API returned success but file missing")
                return False
        else:
            logger.error(f"FAILURE: API returned {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return False

def test_pin():
    """Test adding a pin to a cube."""
    logger.info("=== TEST: Pin Union ===")
    
    # Check health
    try:
        resp = requests.get(f"{BLENDER_URL}/health", timeout=5)
        if resp.status_code != 200:
            logger.error("Blender service unhealthy")
            return False
    except Exception as e:
        logger.error(f"Failed to connect to Blender: {e}")
        return False
    
    # Create test cube
    full_path, rel_name = create_test_cube()
    if not full_path:
        return False
    
    # Define pin connector at center of top face
    payload = {
        "input_file": rel_name,
        "output_file": "test_cube_with_pin.stl",
        "operation": "script",
        "script_path": "connectors.py",
        "params": {
            "connectors": [
                {
                    "position": [0, 0, 25],  # Top of 50x50x50 cube centered at origin
                    "normal": [0, 0, 1],      # Pointing up out of cube
                    "diameter": 10.0,
                    "depth": 20.0,
                    "type": "pin"
                }
            ]
        }
    }
    
    logger.info("Sending pin request to Blender...")
    try:
        start = time.time()
        resp = requests.post(f"{BLENDER_URL}/process", json=payload, timeout=120)
        duration = time.time() - start
        
        logger.info(f"Response ({duration:.2f}s): {resp.status_code}")
        logger.info(resp.text)
        
        if resp.status_code == 200:
            output_path = os.path.join(os.getcwd(), 'media', 'test_cube_with_pin.stl')
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                logger.info(f"SUCCESS: Output file created, size={size} bytes")
                return True
            else:
                logger.error("FAILURE: API returned success but file missing")
                return False
        else:
            logger.error(f"FAILURE: API returned {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    results = []
    
    # Run tests
    results.append(("Hole Subtraction", test_hole()))
    results.append(("Pin Union", test_pin()))
    
    # Summary
    print("\n=== TEST SUMMARY ===")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    sys.exit(0 if all_passed else 1)
