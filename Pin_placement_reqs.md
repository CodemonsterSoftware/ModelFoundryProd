# Technical Specification: Automated STL Slicing & Peg Generation in Blender

## 1. Project Objective
Create a Blender Python script/addon that:
1.  Slices a mesh into multiple parts along defined planes.
2.  Automatically generates alignment pegs (male) and holes (female) on the cut surfaces.
3.  Ensures zero-tolerance alignment errors between parts.
4.  Prevents internal collisions ("Swiss Cheese" effect) and wall-breakouts on complex geometry.

---

## 2. Core Architectural Principles

### A. The "Master Reference" Pattern
**Do not** calculate peg positions relative to the separate mesh pieces after they move.
* **Concept:** The "Peg" is a distinct 3rd actor (a temporary object) spawned at the exact moment of the slice.
* **Workflow:**
    1.  Slice Mesh.
    2.  Spawn `Master_Peg` at the cut centroid.
    3.  `Boolean Union` Master_Peg to Piece A.
    4.  Duplicate `Master_Peg` -> `Cutter_Peg` (add scale tolerance).
    5.  `Boolean Difference` Cutter_Peg from Piece B.

### B. Math-First Validation
**Do not** rely on boolean failures to detect errors.
* Use vector math (`mathutils`) to validate peg placement *before* generating geometry.
* Maintain a "Peg Registry" (list of vectors) to check for collisions between new and existing pegs.

---

## 3. The Logical Pipeline

### Phase 1: The Slice & Cap Analysis
The script must identify the new geometry created by the cut.

1.  **Operation:** Perform `bpy.ops.mesh.bisect` (or Boolean Plane Cut) with `fill=True`.
2.  **Selection:** Immediately capture the newly created faces.
    * *Constraint:* Identify faces where `face.normal` is parallel to the `cut_plane_normal`.
3.  **Island Detection:**
    * The cut surface may contain multiple disconnected parts (e.g., slicing a "U" shape).
    * **Algorithm:** Use `bmesh.ops.region_extend` or a graph traversal (BFS/DFS) on selected faces to group them into distinct "Islands".
    * **Action:** Process each Island as a separate potential peg location.

### Phase 2: Peg Placement Logic
For each identified Island:

1.  **Calculate Centroid:** Average position of all face centers in the island.
2.  **Calculate Orientation:** Align Z-axis to `face.normal`.
3.  **Boundary Check (Wall Thickness):**
    * Cast rays from Centroid outwards (perpendicular to normal) using `obj.ray_cast`.
    * *Rule:* If distance to nearest non-cap edge < `Peg_Radius + 2mm`, abort placement or shrink peg.
4.  **Staggering (Anti-Collision):**
    * Apply a deterministic offset based on the Cut Normal to avoid center-mass pileups in grid slices.
    * *Example:*
        * If Normal == X-Axis: Offset `(0, +Offset, 0)`
        * If Normal == Y-Axis: Offset `(+Offset, 0, 0)`

### Phase 3: Collision Prevention (The "Swiss Cheese" Guard)
Before spawning geometry, run the candidate peg against the **Peg Registry**.

* **Registry Structure:** A list of dicts: `{'start': Vector, 'end': Vector, 'radius': Float}`.
* **Validation Tool:** `mathutils.geometry.intersect_line_line(startA, endA, startB, endB)`.
* **Logic:**
    1.  Calculate shortest distance between Candidate Peg Line and all Registered Peg Lines.
    2.  *Fail Condition:* `distance < (Candidate_Radius + Registered_Radius + Wall_Margin)`.
    3.  *Fallback:* If fail, try shortening the peg. If still fail, skip peg.

### Phase 4: Geometry Generation & Boolean
Once validated:

1.  **Spawn Cylinder:** Radius defined by island size; Length defined by user settings (default ~10-15mm).
2.  **Apply Tolerance:**
    * Male Peg: Exact size.
    * Female Cutter: Scale X/Y by `1.05` (approx +0.15mm to +0.2mm clearance) for 3D printing fit.
3.  **Execute Booleans:**
    * Apply modifiers or destructive booleans to the respective mesh chunks.

---

## 4. Key Blender API Functions (For the Agent)

* **Mesh Data Access:** `bm = bmesh.new(); bm.from_mesh(mesh)`
* **Island Separation:** Custom graph traversal required on `bm.faces`.
* **Intersection Logic:** `mathutils.geometry.intersect_line_line` (CRITICAL for speed).
* **Raycasting:** `obj.ray_cast(origin, direction)` (Use for detecting wall thickness).
* **Matrix Math:** Construct 4x4 matrices for placement:
    ```python
    rot_matrix = normal_vector.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    loc_matrix = Matrix.Translation(centroid)
    final_matrix = loc_matrix @ rot_matrix
    ```

---

## 5. Edge Cases to Handle

1.  **Tiny Islands:** If a slice creates a small artifact (< 20mm² area), ignore it. Do not place a peg.
2.  **Manifold Integrity:** Ensure `bmesh.ops.recalc_face_normals` is run before boolean operations to prevent "inside-out" errors.
3.  **Self-Intersection:** If the object is thin, ensure the peg hole doesn't poke through the opposite side of the mesh. Use the Raycast check for `peg_length` as well as `peg_radius`.