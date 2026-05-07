"""
Etcher Module Entrypoint
========================
Handles two actions via a single job endpoint, distinguished by
params['action']: 'etch' or 'read'.

Usage (invoked automatically by PythonBackend):
    python main.py /path/to/forge_jobs/<uuid>/job.json
"""

import sys
import json
import logging
import tempfile
import os
from pathlib import Path



logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("etcher")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <job.json_path>")

    job_json_path = Path(sys.argv[1])
    job_dir = job_json_path.parent

    with open(job_json_path, "r") as f:
        job = json.load(f)

    params: dict = job.get("params", {})
    input_file: str = job.get("input_file")
    action = params.get("action", "etch")  # 'etch' or 'read'
    strategy = params.get("strategy", "vertex_permutation")

    try:
        from etcher import RuneEtcher

        etcher = RuneEtcher(strategy=strategy)

        if action == "etch":
            message = params.get("message", "")
            if not message:
                raise ValueError("'message' param is required for etch action")
            if not input_file or not Path(input_file).exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")

            input_path = Path(input_file)
            output_filename = f"{input_path.stem}_etched.stl"
            output_path = job_dir / output_filename

            etcher.etch(str(input_path), str(output_path), message)

            job["status"] = "completed"
            job["output_file"] = str(output_path)
            job["action"] = "etch"
            job["message_length"] = len(message)
            # Parts list so the standard download endpoint works
            forge_jobs_dir = job_dir.parent
            job["parts"] = [
                {
                    "filename": output_filename,
                    "path": str(output_path.relative_to(forge_jobs_dir)),
                }
            ]

        elif action == "read":
            if not input_file or not Path(input_file).exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")

            decoded_message = etcher.read(str(input_file))

            job["status"] = "completed"
            job["action"] = "read"
            job["decoded_message"] = decoded_message

        else:
            raise ValueError(f"Unknown action: '{action}'. Must be 'etch' or 'read'.")

    except Exception as e:
        logger.exception(f"Etcher failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)

    with open(job_json_path, "w") as f:
        json.dump(job, f)


if __name__ == "__main__":
    main()
