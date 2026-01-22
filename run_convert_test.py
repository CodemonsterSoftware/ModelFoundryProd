import sys
import os

print("Injecting request_data global...")
# Global var expected by convert.py
# Using builtins to make it available to the exec context if needed, 
# but usually exec shares globals.
global request_data
request_data = {
    "input_file": "test_cube_valid.stl",
    "output_file": "test_cube_valid.step",
    "params": {"repair_mesh": True, "tolerance": 0.1}
}

# Add current dir to path just in case
sys.path.append(os.getcwd())

print("Executing convert.py...")
try:
    with open("convert.py") as f:
        code = compile(f.read(), "convert.py", 'exec')
        exec(code, globals())
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
