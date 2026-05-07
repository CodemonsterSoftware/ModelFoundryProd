"""
STL Converter Module Entrypoint
================================
Converts an uploaded STL file to STEP format via the Blender service.

Usage (invoked automatically by PythonBackend):
    python main.py /path/to/forge_jobs/<uuid>/job.json
"""

import sys
import json
import logging
from pathlib import Path

# Bootstrap: add project root so forge.services.blender_client (used
# internally by converter.py) remains importable.
# Path layout: converter/ -> modules/ -> forge/ -> <project root>
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("converter")


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

        # All params arrive as strings — cast explicitly
        repair_mesh = params.get("repair_mesh", "true").lower() not in ("false", "0", "")
        tolerance = float(params.get("tolerance", "0.1"))

        output_path = job_dir / f"{input_path.stem}.step"

        from converter import convert_stl_to_step

        convert_stl_to_step(
            input_path=str(input_path),
            output_path=str(output_path),
            repair=repair_mesh,
            tolerance=tolerance,
        )

        job["status"] = "completed"
        job["output_file"] = str(output_path)

    except Exception as e:
        logger.exception(f"Converter failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)

    with open(job_json_path, "w") as f:
        json.dump(job, f)


if __name__ == "__main__":
    main()
