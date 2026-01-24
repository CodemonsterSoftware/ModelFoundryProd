# Feature Specification: Alignment Pins (Tenon & Socket)

## Overview
This feature implements a "Tenon & Socket" alignment system for large multi-part 3D prints.
- **Frontend (Three.js):** Handles user inputs, calculates valid grid positions, and renders a "ghost" preview.
- **Backend (Blender Sidecar):** Receives layout data, performs destructive boolean CSG operations, and generates the printable male connector.

---

## Part A: Frontend Logic (Three.js)

The frontend is responsible for the **User Experience** and **Data Preparation**. It must visually represent where the pins will go before any geometry is modified.

### 1. User Inputs
The user provides three key values:
1.  **Pin Size ($W$):** The edge length of the square base (e.g., `12mm`).
2.  **Spacing ($S$):** The distance between pin centers (e.g., `30mm`).
3.  **Edge Margin ($M$):** The minimum safe distance from a pin's edge to the mesh boundary (e.g., `4mm`).

### 2. Derived Constants (System Defined)
These values are calculated automatically to ensure printability and fit.
* **Pin Height ($H$):** $W \times 0.5$.
    * *Rationale:* Ensures a 45° wall angle, allowing the socket to be printed on an overhang without supports.
* **Fit Tolerance ($T$):** $0.2mm$ (Default).
    * *Rationale:* The gap required between the male pin and female socket to account for printer inaccuracies.

### 3. Grid Generation Algorithm
When a user selects a face, execute the following:

1.  **Define Basis:** Calculate a local coordinate system (Tangent/Bitangent) on the selected face using its Normal and Centroid.
2.  **Generate Grid:** Create a grid of points on this plane spaced by $S$.
3.  **Validity Filter:**
    For each point, fire a Raycast along $-Normal$. A point is **Valid** only if:
    * **Intersection:** The ray hits the target mesh.
    * **Inside Bounds:** The point is strictly inside the face loop (odd-even rule).
    * **Safety Check:** The distance to the nearest mesh edge is $> (W/2 + M)$.
4.  **Preview:** Instantiate "Ghost" pyramids (transparent red) at all valid locations.

### 4. JSON Payload Structure
When the user confirms the action, send this payload to the Blender sidecar:

```json
{
  "operation": "generate_alignment_pins",
  "target_mesh_id": "part_A_split_01",
  "design_inputs": {
    "edge_length": 12.0,   // User Input
    "spacing": 30.0,       // User Input
    "margin": 4.0          // User Input
  },
  "derived_parameters": {
    "pin_height": 6.0,     // Auto-calculated (12.0 * 0.5)
    "fit_tolerance": 0.2   // System Constant
  },
  "pin_locations": [
    // List of valid points calculated by Three.js
    { "x": 10.5, "y": 40.0, "z": 0.0, "normal": [0, 0, 1] },
    { "x": 40.5, "y": 40.0, "z": 0.0, "normal": [0, 0, 1] }
  ]
}
Part B: Backend Logic (Blender / Python)The backend performs the geometry operations. It creates the sockets (holes) in the main part and generates the separate male tenon file.Algorithm StepsGenerate "Master Cutter": Create a square pyramid geometry.Dimensions: Base Width $= W + T$, Height $= H + (T/2)$.Note: This object is larger than the pin to create the tolerance gap.Boolean Subtraction:Place a cutter instance at every valid pin_location, aligned to the normal.Join all cutters into a single mesh (optimization).Apply a Boolean Difference modifier to the target mesh.Generate "Printable Tenon":Create a Double-Sided pyramid (Diamond shape).Dimensions: Base Width $= W$, Height $= H$ (on both sides).Note: This object uses exact dimensions (Zero Tolerance).Export this object immediately as Tenon_[Size]mm.stl.Reference Implementation (Python/bpy)Pythonimport bpy
import bmesh
from mathutils import Vector

def generate_alignment_pins(data):
    target_obj = bpy.data.objects[data['target_mesh_id']]
    locs = data['pin_locations']
    
    # Extract Parameters
    W = data['design_inputs']['edge_length']
    H = data['derived_parameters']['pin_height']
    T = data['derived_parameters']['fit_tolerance']
    
    # --- Step 1: Create Master Cutter (Female Socket) ---
    # Cutter includes tolerance
    cutter_w = W + T
    cutter_h = H + (T / 2)
    
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, 
        cap_ends=True, 
        cap_tris=False, 
        segments=4, 
        diameter1=cutter_w * 1.414, # Square side to diameter conversion
        diameter2=0, 
        depth=cutter_h
    )
    # Ensure cutter origin is at the base
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, -cutter_h/2))
    
    cutter_mesh = bpy.data.meshes.new("MasterCutter")
    bm.to_mesh(cutter_mesh)
    bm.free()
    
    # --- Step 2: Position & Boolean ---
    cutters = []
    for loc in locs:
        c = bpy.data.objects.new("Cutter_Temp", cutter_mesh)
        bpy.context.collection.objects.link(c)
        c.location = Vector((loc['x'], loc['y'], loc['z']))
        
        # Align Z-axis to Face Normal
        norm = Vector(loc['normal'])
        rot = Vector((0, 0, 1)).rotation_difference(norm)
        c.rotation_euler = rot.to_euler()
        cutters.append(c)
        
    # Join cutters for performance
    if cutters:
        bpy.ops.object.select_all(action='DESELECT')
        for c in cutters: c.select_set(True)
        bpy.context.view_layer.objects.active = cutters[0]
        bpy.ops.object.join()
        merged_cutter = bpy.context.view_layer.objects.active
        
        # Apply Boolean Difference
        mod = target_obj.modifiers.new(name="SocketCut", type='BOOLEAN')
        mod.object = merged_cutter
        mod.operation = 'DIFFERENCE'
        mod.solver = 'FAST'
        bpy.context.view_layer.objects.active = target_obj
        bpy.ops.object.modifier_apply(modifier="SocketCut")
        
        # Cleanup
        bpy.data.objects.remove(merged_cutter)
    
    # --- Step 3: Create Printable Tenon (Male Part) ---
    # Note: Passed W and H are exact (No tolerance)
    output_dir = bpy.path.abspath("//")
    tenon_file_path = create_printable_tenon(W, H, output_dir)
    
    return {
        "status": "success", 
        "modified_mesh": target_obj.name, 
        "tenon_file": tenon_file_path
    }

def create_printable_tenon(width, height, output_path):
    """
    Generates a double-sided pyramid with EXACT dimensions.
    """
    name = f"Tenon_{width}mm"
    
    # Return existing file if already generated
    filepath = f"{output_path}/{name}.stl"
    if name in bpy.data.objects:
        return filepath

    w = width / 2
    # Vertices: Top Tip, Bottom Tip, 4 Base Corners
    verts = [
        (0,0,height), (0,0,-height), 
        (-w,-w,0), (w,-w,0), (w,w,0), (-w,w,0)
    ]
    # Faces: 8 triangles connecting tips to base
    faces = [
        (0,2,3), (0,3,4), (0,4,5), (0,5,2), 
        (1,3,2), (1,4,3), (1,5,4), (1,2,5)
    ]
    
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    
    # Export only this object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True)
    
    return filepath