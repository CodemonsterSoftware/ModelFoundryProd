import subprocess
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base import ExecutionEngine

logger = logging.getLogger(__name__)

class OpenSCADBackend(ExecutionEngine):
    """
    Execution backend that runs the local OpenSCAD CLI.
    """
    
    def run_task(self, job_meta: Dict[str, Any], input_path: Optional[str], output_dir: str) -> Dict[str, Any]:
        """
        Executes an OpenSCAD script with parameters.
        Must define a main SCAD file in the module.
        """
        module_path = job_meta.get("module_path")
        if not module_path:
            raise ValueError("OpenSCAD backend requires a module_path")
            
        main_scad = Path(module_path) / "main.scad"
        if not main_scad.exists():
            raise FileNotFoundError(f"OpenSCAD module missing main.scad at {main_scad}")
            
        output_file = Path(output_dir) / "output.stl"
        
        # Build command: openscad -o output.stl main.scad
        cmd = ["openscad", "-o", str(output_file)]
        
        # Add parameters
        params = job_meta.get("params", {})
        for key, value in params.items():
            if isinstance(value, str):
                cmd.extend(["-D", f'{key}="{value}"'])
            else:
                cmd.extend(["-D", f'{key}={value}'])
                
        cmd.append(str(main_scad))
        
        try:
            logger.info(f"Running OpenSCAD: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            return {
                "status": "completed",
                "output_file": str(output_file),
                "parts": [{"filename": "output.stl", "path": str(output_file.relative_to(Path(output_dir).parent))}]
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"OpenSCAD failed: {e.stderr}")
            return {
                "status": "failed",
                "error": e.stderr
            }
