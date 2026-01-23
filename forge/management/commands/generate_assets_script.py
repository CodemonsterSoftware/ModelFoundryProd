
import os
import trimesh
import numpy as np
from pathlib import Path

# Define output directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ASSETS_DIR = BASE_DIR / 'forge' / 'static' / 'forge' / 'assets' / 'parts'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def create_head():
    # Simple icosphere for head
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=100)
    # Scale to be more head-shaped (oval)
    mesh.apply_scale([0.85, 1.0, 1.0]) 
    return mesh

def create_chest():
    # Box/Hull for chest
    mesh = trimesh.creation.box(extents=[300, 400, 200])
    # Round corners? Trimesh box is sharp. 
    # Let's use a capsule or cylinder modified?
    # Simple box is fine for placeholder
    return mesh

def create_limb():
    # Capsule for arm/leg
    # Trimesh capsule: height, radius
    mesh = trimesh.creation.capsule(height=400, radius=50)
    return mesh

def create_full():
    # Combine simple shapes
    head = create_head()
    head.apply_translation([0, 350, 0])
    
    chest = create_chest()
    chest.apply_translation([0, 0, 0])
    
    # Just a simple stack
    mesh = trimesh.util.concatenate([head, chest])
    return mesh

def main():
    parts = {
        'head': create_head,
        'chest': create_chest,
        'arm': create_limb,
        'leg': create_limb,
        'full': create_full
    }
    
    print(f"Generating assets in {ASSETS_DIR}...")
    
    for name, func in parts.items():
        filename = f"{name}.stl"
        path = ASSETS_DIR / filename
        
        print(f"Generating {filename}...")
        try:
            mesh = func()
            mesh.export(str(path))
            print(f"Saved {path}")
        except Exception as e:
            print(f"Error creating {name}: {e}")

if __name__ == "__main__":
    main()
