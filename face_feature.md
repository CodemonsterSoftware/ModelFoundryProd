# Feature Specification: "Lay Face on Bed" with Auto-Center

## Context
We are building a 3D printing slicer frontend using Three.js. The scene assumes a standard 3D printing coordinate system:
- **Unit:** Millimeters
- **Up Axis:** +Z
- **Build Plate:** The X-Y plane at Z=0

## Objective
Implement a function `alignFaceToBed(mesh, face)` that performs the following transformation on a selected object:
1.  **Rotation:** Rotates the object so the normal vector of the selected `face` points downwards (-Z).
2.  **Z-Alignment:** Translates the object vertically so the selected face is flush with the build plate ($Z=0$).
3.  **Centering:** Translates the object horizontally so its Bounding Box is centered at $(0,0)$ on the X-Y plane.

## Technical Implementation Details

### Dependencies
- `three` (r120+)

### Algorithm Steps
1.  **Clone Normal:** Clone the `face.normal`.
2.  **World Direction:** Apply the mesh's current `quaternion` to this normal to get its orientation in World Space.
3.  **Rotation Calculation:** Calculate the quaternion required to rotate the `worldNormal` to the target vector `(0, 0, -1)`.
4.  **Apply Rotation:** Pre-multiply the mesh's quaternion with this new rotation.
5.  **Update Matrix:** Call `mesh.updateMatrixWorld()` immediately to ensure subsequent calculations use the new orientation.
6.  **Z-Snap (Face alignment):**
    - Retrieve a vertex from the selected face (e.g., `face.a`).
    - Transform this vertex to World Space.
    - Calculate `offsetZ = -worldVertex.z`.
    - Apply `mesh.position.z += offsetZ`.
7.  **X-Y Centering:**
    - Re-update `mesh.updateMatrixWorld()`.
    - Compute the Axis-Aligned Bounding Box (AABB) using `new THREE.Box3().setFromObject(mesh)`.
    - Calculate the center of the box: `center = box.getCenter()`.
    - Calculate offsets: `offsetX = -center.x`, `offsetY = -center.y`.
    - Apply `mesh.position.x += offsetX` and `mesh.position.y += offsetY`.

### Reference Implementation

```javascript
import * as THREE from 'three';

/**
 * Aligns a mesh so the selected face is flush with Z=0 and centers the object on X/Y.
 * * @param {THREE.Mesh} mesh - The target mesh to move.
 * @param {THREE.Face3} face - The face selected by the raycaster.
 */
export function alignFaceToBed(mesh, face) {
    if (!mesh || !face) {
        console.warn("alignFaceToBed: Mesh or Face not provided.");
        return;
    }

    // --- Step 1: Rotation ---
    
    // Get face normal in world space
    const normalMatrix = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld);
    const worldNormal = face.normal.clone().applyMatrix3(normalMatrix).normalize();
    
    // Target direction is -Z (down)
    const down = new THREE.Vector3(0, 0, -1);
    
    // Calculate rotation to align normal with down vector
    const targetQuaternion = new THREE.Quaternion();
    targetQuaternion.setFromUnitVectors(worldNormal, down);
    
    // Apply rotation to the mesh (premultiply to apply in world space equivalent)
    mesh.quaternion.premultiply(targetQuaternion);
    mesh.updateMatrixWorld();

    // --- Step 2: Z-Snapping (Move face to Z=0) ---

    // We need the world position of a vertex on that face to know where 'bottom' is
    // Access the position attribute
    const positionAttribute = mesh.geometry.getAttribute('position');
    const vertex = new THREE.Vector3();
    vertex.fromBufferAttribute(positionAttribute, face.a);
    
    // Transform vertex to world space
    vertex.applyMatrix4(mesh.matrixWorld);

    // The distance to move is simply the negative of the vertex's current Z
    mesh.position.z -= vertex.z;
    mesh.updateMatrixWorld();

    // --- Step 3: Auto-Centering (Move center to X=0, Y=0) ---

    // Compute new bounding box after rotation and Z-snap
    const bbox = new THREE.Box3().setFromObject(mesh);
    const center = new THREE.Vector3();
    bbox.getCenter(center);

    // Move mesh so that the center aligns with 0,0 on X and Y
    mesh.position.x -= center.x;
    mesh.position.y -= center.y;
    
    mesh.updateMatrixWorld();
}