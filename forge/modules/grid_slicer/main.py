"""
Grid Slicer Module Entrypoint
=============================
Reads job.json written by the Forge framework, runs the slice pipeline,
and writes results back to job.json before exit.

Usage (invoked automatically by PythonBackend):
    python main.py /path/to/forge_jobs/<uuid>/job.json
"""

import sys
import json
import zipfile
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: add the Forge project root to sys.path so that the shared
# forge.services.blender_client (used internally by slicer.py) remains
# importable. slicer.py itself lives here alongside main.py.
# Path layout: grid_slicer/ -> modules/ -> forge/ -> <project root>
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("grid_slicer")


def _build_grid_config(params: dict, slice_mode: str) -> dict:
    """Convert incoming string params into the grid dict expected by the slicer."""
    if slice_mode == "fit":
        # fit mode calculates planes via trimesh; delegated here
        return None  # handled separately in main()
    elif slice_mode == "uniform":
        def _sections(val: str, default: int = 1) -> int:
            cuts = int(val) if val else default
            return 1 if cuts == 0 else cuts + 1
        return {
            "x": _sections(params.get("grid_x", "2")),
            "y": _sections(params.get("grid_y", "2")),
            "z": _sections(params.get("grid_z", "1")),
        }
    else:  # freeform — grid not used
        return {"x": 1, "y": 1, "z": 1}


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <job.json_path>")

    job_json_path = Path(sys.argv[1])
    job_dir = job_json_path.parent

    with open(job_json_path, "r") as f:
        job = json.load(f)

    params: dict = job.get("params", {})
    input_file: str = job.get("input_file")

    try:
        if not input_file or not Path(input_file).exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        input_path = Path(input_file)
        slice_mode = params.get("slice_mode", "uniform")

        # ---------------------------------------------------------------
        # Resolve grid / planes config
        # ---------------------------------------------------------------
        planes_config = []
        grid_config = {"x": 1, "y": 1, "z": 1}

        if slice_mode == "freeform":
            planes_json = params.get("freeform_planes", "[]")
            planes_config = json.loads(planes_json)
            if not isinstance(planes_config, list):
                raise ValueError("freeform_planes must be a JSON array")

        elif slice_mode == "fit":
            import trimesh
            from slicer import calculate_fit_planes
            mesh = trimesh.load(str(input_path))
            bounds = mesh.bounds
            model_dims = {
                "x": bounds[1][0] - bounds[0][0],
                "y": bounds[1][1] - bounds[0][1],
                "z": bounds[1][2] - bounds[0][2],
            }
            printer_dims = {
                "x": float(params.get("printer_x", "220")),
                "y": float(params.get("printer_y", "220")),
                "z": float(params.get("printer_z", "250")),
            }
            fit_grid = calculate_fit_planes(
                model_dims=model_dims,
                printer_dims=printer_dims,
                model_units=params.get("model_units", "mm"),
                desired_size=float(params["desired_size"]) if params.get("desired_size") else None,
            )
            grid_config = {
                "x": 1 if fit_grid["x"] == 0 else fit_grid["x"] + 1,
                "y": 1 if fit_grid["y"] == 0 else fit_grid["y"] + 1,
                "z": 1 if fit_grid["z"] == 0 else fit_grid["z"] + 1,
            }

        else:  # uniform
            def _sections(val, default=0):
                cuts = int(val) if val else default
                return 1 if cuts == 0 else cuts + 1
            grid_config = {
                "x": _sections(params.get("grid_x", "2")),
                "y": _sections(params.get("grid_y", "2")),
                "z": _sections(params.get("grid_z", "1")),
            }

        # ---------------------------------------------------------------
        # Joint / connector params
        # ---------------------------------------------------------------
        joint_type = params.get("joint_type", "none")
        joint_params = {}
        dovetail_params = {}

        if joint_type == "tenon":
            joint_params = {
                "size": float(params.get("tenon_size", "12.0")),
                "spacing": float(params.get("tenon_spacing", "30.0")),
                "margin": float(params.get("tenon_margin", "4.0")),
                "tolerance": float(params.get("tenon_tolerance", "0.2")),
            }
        else:
            joint_params = {
                "diameter": float(params.get("joint_diameter", "4.0")),
                "height": float(params.get("joint_height", "5.0")),
                "clearance": float(params.get("joint_clearance", "0.2")),
                "count": int(params.get("joint_count", "0")),
                "shape": params.get("joint_shape", "circle"),
            }

        dovetail_profile = params.get("dovetail_profile", "trapezoid")
        dovetail_params = {
            "profile": "STANDARD_TRAPEZOID" if dovetail_profile == "trapezoid" else "PUZZLE_LOCK",
            "angle": float(params.get("dovetail_angle", "55.0")),
            "width": float(params.get("dovetail_width", "8.0")),
            "depth": float(params.get("dovetail_depth", "4.0")),
            "count": int(params.get("dovetail_count", "0")),
        }

        # ---------------------------------------------------------------
        # Run the slicer
        # ---------------------------------------------------------------
        from slicer import slice_mesh_grid, calculate_connector_suggestions

        slice_result = slice_mesh_grid(
            input_path=str(input_path),
            output_dir=str(job_dir),
            grid=grid_config,
            planes=planes_config if planes_config else None,
            joint_type=joint_type,
            joint_params=joint_params,
            dovetail_params=dovetail_params,
        )

        output_files = slice_result.get("parts", [])
        warnings = slice_result.get("warnings", [])
        blender_required = slice_result.get("blender_required", False)
        dowel_files = slice_result.get("dowel_files", [])

        connector_suggestions = calculate_connector_suggestions(output_files)

        # ---------------------------------------------------------------
        # Build ZIP of all parts
        # ---------------------------------------------------------------
        zip_path = job_dir / f"{input_path.stem}_sliced.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for part_data in output_files:
                fp = part_data["filepath"] if isinstance(part_data, dict) else part_data
                zf.write(fp, Path(fp).name)
            for dowel_data in dowel_files:
                zf.write(dowel_data["filepath"], Path(dowel_data["filepath"]).name)

        # ---------------------------------------------------------------
        # Build parts / dowels lists for the response
        # ---------------------------------------------------------------
        # job_dir.parent is FORGE_JOBS_DIR — paths are relative to that
        forge_jobs_dir = job_dir.parent

        parts_info = []
        for idx, part_data in enumerate(output_files):
            if isinstance(part_data, dict):
                part_path = Path(part_data["filepath"])
                validation = part_data.get("validation", {"valid": True, "issues": []})
                has_connectors = part_data.get("has_connectors", False)
                connector_positions = part_data.get("connector_positions", [])
            else:
                part_path = Path(part_data)
                validation = {"valid": True, "issues": []}
                has_connectors = False
                connector_positions = []

            parts_info.append(
                {
                    "index": idx,
                    "filename": part_path.name,
                    "path": str(part_path.relative_to(forge_jobs_dir)),
                    "validation": validation,
                    "has_connectors": has_connectors,
                    "connectors": connector_positions,
                }
            )

        dowels_info = []
        for dowel_data in dowel_files:
            dowel_path = Path(dowel_data["filepath"])
            dowels_info.append(
                {
                    "filename": dowel_path.name,
                    "path": str(dowel_path.relative_to(forge_jobs_dir)),
                    "count_needed": dowel_data.get("count_needed", 0),
                    "diameter": dowel_data.get("diameter", 0),
                    "height": dowel_data.get("height", 0),
                }
            )

        # ---------------------------------------------------------------
        # Write success state back to job.json
        # ---------------------------------------------------------------
        job["status"] = "completed"
        job["output_file"] = str(zip_path)
        job["part_count"] = len(output_files)
        job["parts"] = parts_info
        job["warnings"] = warnings
        job["dowels"] = dowels_info
        job["blender_required"] = blender_required
        job["connector_suggestions"] = connector_suggestions

    except Exception as e:
        logger.exception(f"Grid Slicer failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)

    with open(job_json_path, "w") as f:
        json.dump(job, f)


if __name__ == "__main__":
    main()
