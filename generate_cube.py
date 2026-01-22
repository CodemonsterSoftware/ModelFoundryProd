import trimesh
import os

try:
    mesh = trimesh.creation.box(extents=[10,10,10])
    # output relative to /app/media
    output_path = "/app/media/test_cube_valid.stl"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mesh.export(output_path)
    print(f"Created {output_path}")
except Exception as e:
    print(f"Error: {e}")
