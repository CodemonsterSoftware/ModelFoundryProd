import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

class SizerViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);

        // Scene Basics
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.transformControl = null;

        // Objects
        this.bodyPartMesh = null;
        this.userModel = null;
        this.partConfig = {
            id: null,
            baseSize: 100, // Default size reference (mm)
            currentSize: 150
        };

        this.init();
    }

    init() {
        if (!this.container) return;

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a1a);

        // Camera
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 600;
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
        this.camera.position.set(200, 200, 200);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;

        // Lights
        const ambientLight = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1);
        dirLight.position.set(100, 100, 100);
        this.scene.add(dirLight);

        // Grid
        const gridHelper = new THREE.GridHelper(500, 50, 0x444444, 0x333333);
        this.scene.add(gridHelper);

        // Transform Controls (for User Model)
        this.transformControl = new TransformControls(this.camera, this.renderer.domElement);
        this.transformControl.addEventListener('dragging-changed', (event) => {
            this.controls.enabled = !event.value;
        });
        this.scene.add(this.transformControl);

        // Resize
        window.addEventListener('resize', () => this.onResize());

        // Animation Loop
        this.animate();
    }

    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    // --- Body Part Logic ---

    async setBodyPart(partId, userSize) {
        this.partConfig.id = partId;
        this.partConfig.currentSize = userSize;

        // Remove old
        if (this.bodyPartMesh) {
            this.scene.remove(this.bodyPartMesh);
            this.bodyPartMesh = null;
        }

        try {
            let mesh = null;
            // Priority Logic
            if (partId === 'full') {
                // Try GLB first
                try {
                    const gltf = await this.loadAsset('/static/forge/assets/parts/full.glb', 'glb');
                    mesh = gltf;
                } catch (e) {
                    console.warn("Male GLB failed, trying STL", e);
                    mesh = await this.loadAsset('/static/forge/assets/parts/full.stl', 'stl');
                }
            } else if (partId === 'female') {
                // Try GLB first
                try {
                    const gltf = await this.loadAsset('/static/forge/assets/parts/female.glb', 'glb');
                    mesh = gltf;
                } catch (e) {
                    console.warn("Female GLB failed, trying STL", e);
                    mesh = await this.loadAsset('/static/forge/assets/parts/female.stl', 'stl');
                }
            } else {
                // Try STL first
                try {
                    mesh = await this.loadAsset(`/static/forge/assets/parts/${partId}.stl`, 'stl');
                } catch (e) {
                    console.warn("STL failed, trying GLB", e);
                    const gltf = await this.loadAsset(`/static/forge/assets/parts/${partId}.glb`, 'glb');
                    mesh = gltf;
                }
            }

            this.setupBodyPartMesh(mesh);

        } catch (err) {
            console.warn(`Failed to load asset for ${partId}, falling back to primitive.`, err);
            this.createPrimitiveBodyPart(partId);
        }

        if (this.bodyPartMesh) {
            this.scene.add(this.bodyPartMesh);
            this.updateBodyPartScale();
        }
    }

    setupBodyPartMesh(mesh) {
        this.bodyPartMesh = mesh;

        // Log Morph Targets for inspection
        if (this.bodyPartMesh.morphTargetDictionary) {
            console.log("Morph Targets Found (Root):", this.bodyPartMesh.morphTargetDictionary);
        }
        this.bodyPartMesh.traverse((child) => {
            if (child.isMesh && child.morphTargetDictionary) {
                console.log(`Morph Targets Found on child ${child.name}:`, child.morphTargetDictionary);
            }
        });

        // Normalize & Center asset
        const box = new THREE.Box3().setFromObject(this.bodyPartMesh);
        const center = new THREE.Vector3();
        box.getCenter(center);

        // Center geometry
        this.bodyPartMesh.position.x -= center.x;
        this.bodyPartMesh.position.y -= center.y;
        this.bodyPartMesh.position.z -= center.z;

        // Apply Material (Transparent Ghost)
        const material = new THREE.MeshStandardMaterial({
            color: 0xcccccc,
            transparent: true,
            opacity: 0.5,
            roughness: 0.7,
            metalness: 0
        });

        this.bodyPartMesh.traverse((child) => {
            if (child.isMesh) {
                child.material = material;
            }
        });

        // If it's a single mesh, apply directly
        if (this.bodyPartMesh.isMesh) {
            this.bodyPartMesh.material = material;
        }

        const size = new THREE.Vector3();
        box.getSize(size);
        this.partConfig.baseSize = size.x || 1;
    }

    createPrimitiveBodyPart(partId) {
        let geometry;
        const material = new THREE.MeshStandardMaterial({
            color: 0x888888, transparent: true, opacity: 0.5
        });

        switch (partId) {
            case 'head':
                // Sphere/Ovoid
                geometry = new THREE.SphereGeometry(1, 32, 32);
                // We'll scale it to be oval later
                break;
            case 'arm':
            case 'leg':
                geometry = new THREE.CylinderGeometry(1, 1, 4, 32);
                break;
            case 'chest':
                geometry = new THREE.BoxGeometry(2, 3, 1);
                break;
            case 'full':
            case 'female':
            default: // full/other
                geometry = new THREE.CapsuleGeometry(1, 3, 4, 16);
                break;
        }

        this.bodyPartMesh = new THREE.Mesh(geometry, material);
        // Base size for sphere radius=1 is diameter=2
        // Just storing a reference 'unit' size
        this.partConfig.baseSize = 2;
    }

    loadAsset(url, type) {
        return new Promise((resolve, reject) => {
            if (type === 'stl') {
                const loader = new STLLoader();
                loader.load(url, (geometry) => {
                    const mesh = new THREE.Mesh(geometry);
                    resolve(mesh);
                }, undefined, reject);
            } else {
                const loader = new GLTFLoader();
                loader.load(url, (gltf) => {
                    resolve(gltf.scene);
                }, undefined, reject);
            }
        });
    }

    updateBodyPartScale() {
        if (!this.bodyPartMesh) return;

        const targetSize = this.partConfig.currentSize;
        // Simple uniform scale based on ratio (Target / Base)
        // Note: For real assets, we might need axis-specific logic.
        // For now, assuming user inputs 'Width' and we scale uniformly to match that width.

        // If primitive sphere (r=1, d=2), scale = target / 2
        // If loaded mesh (width=X), scale = target / X

        // Recalculate base size from current bounding box at scale 1? 
        // Better: Reset scale to 1, measure, then apply.
        this.bodyPartMesh.scale.set(1, 1, 1);

        const box = new THREE.Box3().setFromObject(this.bodyPartMesh);
        const size = new THREE.Vector3();
        box.getSize(size);

        // Primary dimension (X axis usually width)
        const currentDim = size.x || 1;
        const scaleFactor = targetSize / currentDim;

        this.bodyPartMesh.scale.set(scaleFactor, scaleFactor, scaleFactor);
    }

    // --- User STL Logic ---

    loadUserSTL(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const loader = new STLLoader();
                const geometry = loader.parse(e.target.result);

                if (this.userModel) {
                    this.scene.remove(this.userModel);
                    this.transformControl.detach();
                }

                const material = new THREE.MeshStandardMaterial({
                    color: 0x0077ff,
                    roughness: 0.5,
                    metalness: 0.5
                });

                this.userModel = new THREE.Mesh(geometry, material);

                // Center geometry
                geometry.computeBoundingBox();
                geometry.center();

                this.scene.add(this.userModel);

                // Attach transform controls
                this.transformControl.attach(this.userModel);

            } catch (err) {
                console.error("STL Load Error", err);
                alert("Failed to load STL.");
            }
        };
        reader.readAsArrayBuffer(file);
    }

    setTransformMode(mode) {
        if (this.transformControl) {
            this.transformControl.setMode(mode);
        }
    }

    resetUserModel() {
        if (this.userModel) {
            this.userModel.position.set(0, 0, 0);
            this.userModel.rotation.set(0, 0, 0);
            this.userModel.scale.set(1, 1, 1);
        }
    }
}

// --- UI Binding ---

document.addEventListener('DOMContentLoaded', () => {
    const viewer = new SizerViewer('preview-container');

    const parts = document.querySelectorAll('.body-part-card');
    const dimGroup = document.getElementById('dimensions-group');
    const dimInput = document.getElementById('dimension-input');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('stl_file');
    const transformUI = document.getElementById('transform-controls');
    const badge = document.getElementById('active-part-badge');

    // Part Selection
    parts.forEach(card => {
        card.addEventListener('click', () => {
            parts.forEach(c => c.classList.remove('active'));
            card.classList.add('active');

            const partId = card.dataset.part;
            dimGroup.classList.remove('d-none');

            // Update labels based on part (Simplification)
            // Ideally map partId -> Label Text
            badge.textContent = card.querySelector('div').textContent;

            viewer.setBodyPart(partId, parseFloat(dimInput.value));
        });
    });

    // Dimension Change
    dimInput.addEventListener('input', (e) => {
        viewer.updateBodyPartScale();
        // Since updateBodyPartScale reads from this.partConfig, 
        // we need to update that config first.
        // Actually viewer.setBodyPart updates it. 
        // Let's expose a method to just update size.
        viewer.partConfig.currentSize = parseFloat(e.target.value);
        viewer.updateBodyPartScale();
    });

    // File Upload
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('active'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('active'));
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('active');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    function handleFile(file) {
        // Update UI
        dropzone.innerHTML = `<div class="fw-bold text-success"><i class="bi bi-check-circle"></i> ${file.name}</div>`;
        transformUI.classList.remove('d-none');

        // Load in Viewer
        viewer.loadUserSTL(file);
    }

    // Transform Modes
    document.getElementById('mode-translate').addEventListener('click', (e) => {
        viewer.setTransformMode('translate');
        updateActiveBtn(e.currentTarget);
    });
    document.getElementById('mode-rotate').addEventListener('click', (e) => {
        viewer.setTransformMode('rotate');
        updateActiveBtn(e.currentTarget);
    });
    document.getElementById('mode-scale').addEventListener('click', (e) => {
        viewer.setTransformMode('scale');
        updateActiveBtn(e.currentTarget);
    });
    document.getElementById('reset-model').addEventListener('click', () => {
        viewer.resetUserModel();
    });

    function updateActiveBtn(btn) {
        document.querySelectorAll('#transform-controls .btn-group .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
});
