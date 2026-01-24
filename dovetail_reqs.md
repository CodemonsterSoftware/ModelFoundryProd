# Feature Specification: Automated Geometric Interlocking (Dovetails)

## 1. Objective
Upgrade the slicing pipeline to support **Dovetail Joinery**. This replaces flat planar cuts with interlocking geometry to create structural friction-fit assemblies.

## 2. Core Constraints (CRITICAL)

### A. The "Global Slide Axis" Rule
To prevent creating "Puzzle Locks" (where parts cannot be assembled), the system must enforce a unified insertion vector for all related cuts.

* **Constraint:** For any sub-assembly, there is only **ONE** valid Slide Vector (Default: `Global (0, 0, 1)`).
* **Validation Logic:**
    * IF `Cut_Normal` is roughly parallel to `Slide_Vector`: (e.g., Horizontal Cut)
        * Standard Dovetail Logic applies.
    * IF `Cut_Normal` is perpendicular to `Slide_Vector`: (e.g., Vertical Cut)
        * **FORCE** the dovetail grooves to align with `Slide_Vector` (Global Z).
        * *Do not* align grooves to the face's local tangent unless explicitly overridden.

### B. Manifold Integrity
* Dovetails are not simple texture displacements; they are boolean operations.
* **Cutter Objects** must be generated as manifold solids with a built-in `Tolerance_Gap` (Default: 0.2mm) to ensure parts fit after 3D printing.

---

## 3. The Dovetail "Cutter" Algorithm

The agent shall implement a `DovetailCutter` class that generates a solid "negative volume" to be subtracted from the mesh.

### Step 1: Coordinate System Construction
Define the Local Space for the cutter profile:
* **Origin:** Center of the cut face.
* **Z-Axis (Depth):** Aligned with the `Slide_Vector` (Global Z).
* **Y-Axis (Normal):** Aligned with the `Cut_Normal`.
* **X-Axis (Tangent):** `Cross_Product(Normal, Slide_Vector)`.

### Step 2: Profile Generation (2D)
Generate a list of 2D vertices (X, Y) representing the waveform.
* *Input Parameters:* `Width`, `Depth`, `Waist_Ratio`, `Fit_Tolerance`.
* *Logic:*
    1.  Start at `x = -bounds`.
    2.  Iterate `x += pitch`.
    3.  Plot trapezoidal or sine-wave points.
    4.  **Dogbone Pass (Important):** If the profile has sharp internal corners (< 90°), bevel them or add circular reliefs to account for 3D printer nozzle radius.

### Step 3: Volumetric Extrusion (3D)
Convert the 2D profile into a 3D manifold solid.
1.  **Extrude Curve:** Extrude the 2D path along the **Z-Axis** (Slide Vector) to a length of `Object_Height * 1.5`.
2.  **Thicken:** Apply a "Solidify" effect (Extrude along Normals) equal to `Tolerance_Gap`.
    * *Note:* This creates the empty space between the two final parts.

### Step 4: Boolean Execution
1.  **Duplicate** the original object (if preserving source).
2.  **Boolean Difference** the *Cutter Object* from the Mesh.
3.  **Separate** the resulting mesh by loose parts (`bpy.ops.mesh.separate`).

---

## 4. Profile Configuration (JSON)

The agent should support swappable profiles via a config dictionary.

```python
PROFILES = {
    "STANDARD_TRAPEZOID": {
        "type": "linear",
        "depth": 4.0,       # mm
        "angle": 55,        # degrees (Keep > 45 for overhang safety)
        "waist": 8.0,       # mm
        "tolerance": 0.2    # mm
    },
    "PUZZLE_LOCK": {
        "type": "curved",
        "bulb_radius": 5.0,
        "neck_width": 6.0,
        "dogbone_relief": True, # Essential for curved/jigsaw fits
        "tolerance": 0.25   # Curved fits need slightly looser tolerance
    }
}