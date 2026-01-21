/**
 * SlicePreview - Three.js based 3D preview for the Grid Slicer
 * 
 * Displays uploaded STL with slice planes that update in real-time
 */

class SlicePreview {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Preview container not found:', containerId);
            return;
        }

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.model = null;
        this.slicePlanes = [];
        this.connectorMarkers = [];  // For visualizing connector positions
        this.bounds = null;

        this.init();
    }

    init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a1a);

        // Camera
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 400;
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
        this.camera.position.set(100, 100, 100);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;

        // Lights
        const ambientLight = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(100, 100, 100);
        this.scene.add(directionalLight);

        const backLight = new THREE.DirectionalLight(0xffffff, 0.5);
        backLight.position.set(-100, -100, -100);
        this.scene.add(backLight);

        // Grid helper
        const gridHelper = new THREE.GridHelper(200, 20, 0x444444, 0x333333);
        this.scene.add(gridHelper);

        // Axes helper
        const axesHelper = new THREE.AxesHelper(50);
        this.scene.add(axesHelper);

        // Handle resize
        window.addEventListener('resize', () => this.onResize());

        // Start animation loop
        this.animate();
    }

    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 400;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    loadSTL(file, showPlanes = true) {
        const reader = new FileReader();

        reader.onload = (event) => {
            const contents = event.target.result;
            const loader = new THREE.STLLoader();

            try {
                const geometry = loader.parse(contents);

                // Remove old model
                if (this.model) {
                    this.scene.remove(this.model);
                    this.model.geometry.dispose();
                    this.model.material.dispose();
                }

                // Create material
                const material = new THREE.MeshStandardMaterial({
                    color: 0x0d6efd,
                    metalness: 0.3,
                    roughness: 0.6,
                    flatShading: false
                });

                // Create mesh
                this.model = new THREE.Mesh(geometry, material);

                // Compute bounding box
                geometry.computeBoundingBox();
                this.bounds = geometry.boundingBox;

                // Center the model
                const center = new THREE.Vector3();
                this.bounds.getCenter(center);
                geometry.translate(-center.x, -center.y, -center.z);

                // Recompute bounds after centering
                geometry.computeBoundingBox();
                this.bounds = geometry.boundingBox;

                this.scene.add(this.model);

                // Fit camera to model
                this.fitCameraToModel();

                // Handle slice planes
                if (showPlanes) {
                    const getGridValue = (id, defaultVal) => {
                        const el = document.getElementById(id);
                        // If element not found or value is empty, return default.
                        // Otherwise, parse as int. If NaN, return default.
                        // This allows 0 to be a valid input.
                        if (!el || el.value === '') return defaultVal;
                        const val = parseInt(el.value);
                        return isNaN(val) ? defaultVal : val;
                    };

                    this.updateSlicePlanes(
                        getGridValue('grid_x', 2),
                        getGridValue('grid_y', 2),
                        getGridValue('grid_z', 1)
                    );
                } else {
                    this.clearSlicePlanes();
                }

            } catch (error) {
                console.error('Error loading STL:', error);
                alert('Error loading STL file. Please ensure it is a valid STL.');
            }
        };

        reader.readAsArrayBuffer(file);
    }

    fitCameraToModel() {
        if (!this.bounds) return;

        const size = new THREE.Vector3();
        this.bounds.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);

        const fov = this.camera.fov * (Math.PI / 180);
        const cameraDistance = maxDim / (2 * Math.tan(fov / 2)) * 1.5;

        this.camera.position.set(cameraDistance, cameraDistance * 0.8, cameraDistance);
        this.camera.lookAt(0, 0, 0);
        this.controls.target.set(0, 0, 0);
        this.controls.update();
    }

    clearSlicePlanes() {
        this.slicePlanes.forEach(plane => {
            this.scene.remove(plane);
            if (plane.geometry) plane.geometry.dispose();
            if (plane.material) plane.material.dispose();
            // Also dispose edges if they exist (child of the plane mesh)
            if (plane.children) {
                plane.children.forEach(child => {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) child.material.dispose();
                });
            }
        });
        this.slicePlanes = [];
    }

    updateSlicePlanes(gridX, gridY, gridZ) {
        // Remove existing slice planes
        this.clearSlicePlanes();

        if (!this.bounds) return;

        const size = new THREE.Vector3();
        this.bounds.getSize(size);
        const min = this.bounds.min;
        const max = this.bounds.max;

        // Create slice planes for each axis
        // X planes (red)
        for (let i = 1; i < gridX; i++) {
            const x = min.x + (size.x * i / gridX);
            const plane = this.createSlicePlane(
                new THREE.Vector3(x, (min.y + max.y) / 2, (min.z + max.z) / 2),
                new THREE.Vector3(1, 0, 0),
                Math.max(size.y, size.z) * 1.2,
                0xff4444
            );
            this.slicePlanes.push(plane);
            this.scene.add(plane);
        }

        // Y planes (green)
        for (let i = 1; i < gridY; i++) {
            const y = min.y + (size.y * i / gridY);
            const plane = this.createSlicePlane(
                new THREE.Vector3((min.x + max.x) / 2, y, (min.z + max.z) / 2),
                new THREE.Vector3(0, 1, 0),
                Math.max(size.x, size.z) * 1.2,
                0x44ff44
            );
            this.slicePlanes.push(plane);
            this.scene.add(plane);
        }

        // Z planes (blue)
        for (let i = 1; i < gridZ; i++) {
            const z = min.z + (size.z * i / gridZ);
            const plane = this.createSlicePlane(
                new THREE.Vector3((min.x + max.x) / 2, (min.y + max.y) / 2, z),
                new THREE.Vector3(0, 0, 1),
                Math.max(size.x, size.y) * 1.2,
                0x4444ff
            );
            this.slicePlanes.push(plane);
            this.scene.add(plane);
        }
    }

    createSlicePlane(position, normal, size, color) {
        // Create a plane geometry
        const geometry = new THREE.PlaneGeometry(size, size);

        // Semi-transparent material
        const material = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide,
            depthWrite: false
        });

        const plane = new THREE.Mesh(geometry, material);
        plane.position.copy(position);

        // Rotate plane to match normal
        if (normal.x === 1) {
            plane.rotation.y = Math.PI / 2;
        } else if (normal.y === 1) {
            plane.rotation.x = -Math.PI / 2;
        }
        // Z normal doesn't need rotation

        // Add edge outline
        const edges = new THREE.EdgesGeometry(geometry);
        const lineMaterial = new THREE.LineBasicMaterial({ color: color, linewidth: 2 });
        const edgeLines = new THREE.LineSegments(edges, lineMaterial);
        plane.add(edgeLines);

        return plane;
    }

    showMessage(text) {
        // Create or update info text
        const existingText = document.getElementById('preview-message');
        if (existingText) {
            existingText.textContent = text;
            existingText.style.display = text ? 'block' : 'none';
        }
    }

    clearConnectorMarkers() {
        this.connectorMarkers.forEach(marker => {
            this.scene.remove(marker);
            if (marker.geometry) marker.geometry.dispose();
            if (marker.material) marker.material.dispose();
        });
        this.connectorMarkers = [];
    }

    showConnectorMarkers(connectors) {
        if (!connectors || connectors.length === 0) return;

        this.clearConnectorMarkers();

        connectors.forEach(conn => {
            const pos = conn.position;
            const type = conn.type;
            const diameter = conn.diameter || 4;
            const depth = conn.depth || 5;

            // Create cylinder geometry for connector marker
            const geometry = new THREE.CylinderGeometry(
                diameter / 2 * 1.2,  // Slightly larger for visibility
                diameter / 2 * 1.2,
                depth * 0.5,  // Shorter for preview
                16
            );

            // Color: green for pins, red for holes
            const color = type === 'pin' ? 0x00ff00 : 0xff4444;
            const material = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.7
            });

            const marker = new THREE.Mesh(geometry, material);

            // Position the marker
            marker.position.set(pos[0], pos[1], pos[2]);

            // Rotate based on normal direction
            const normal = conn.normal || [0, 0, 1];
            if (Math.abs(normal[0]) > 0.9) {
                marker.rotation.z = Math.PI / 2;
            } else if (Math.abs(normal[1]) > 0.9) {
                // Y-axis is default for cylinder, no rotation needed
            } else {
                marker.rotation.x = Math.PI / 2;
            }

            this.scene.add(marker);
            this.connectorMarkers.push(marker);
        });

        console.log(`Added ${connectors.length} connector markers`);
    }
}

// Export for use
window.SlicePreview = SlicePreview;
