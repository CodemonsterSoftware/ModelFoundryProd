import importlib.util
import json
import logging
import subprocess
import sys
from typing import Dict, Any, Optional
from pathlib import Path
from django.conf import settings
from .base import ExecutionEngine

logger = logging.getLogger(__name__)

class PythonBackend(ExecutionEngine):
    """
    Executes a module's main python entrypoint directly in-process.
    """
    
    def __init__(self, module_id: str, manifest: Dict[str, Any]):
        self.module_id = module_id
        self.manifest = manifest
        self.modules_dir = Path(settings.BASE_DIR) / 'forge' / 'modules'
        self.module_path = self.modules_dir / self.module_id
        
        # Determine the entrypoint
        self.main_script_name = self.manifest.get('main', 'main.py')
        self.script_path = self.module_path / self.main_script_name
        
    def run_task(self, job_meta: Dict[str, Any], input_path: Optional[str], output_dir: str) -> Dict[str, Any]:
        """
        Executes the python module as an isolated subprocess using its dedicated `.venv`.
        It passes the job.json path so the tool can manipulate it and we return the final state.
        """
        if not self.script_path.exists():
            error_msg = f"PythonBackend failed: Entrypoint '{self.main_script_name}' not found for module '{self.module_id}'"
            logger.error(error_msg)
            return {'status': 'failed', 'error': error_msg}
            
        try:
            import platform
            if platform.system() == 'Windows':
                venv_python = self.module_path / '.venv' / 'Scripts' / 'python.exe'
            else:
                venv_python = self.module_path / '.venv' / 'bin' / 'python'
            
            # Graceful fallback to global python if the module was installed before .venv paradigm
            # or intentionally skips dependencies entirely.
            if not venv_python.exists():
                logger.warning(f"No isolated .venv found for '{self.module_id}'. Falling back to global python.")
                venv_python = sys.executable
                
            job_json_path = Path(output_dir) / 'job.json'
            
            # Expected Interface: python main.py <path_to_job_json>
            cmd = [str(venv_python), str(self.script_path), str(job_json_path)]
            
            logger.info(f"Executing subprocess: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.module_path))
            
            if result.returncode != 0:
                error_msg = f"Module {self.module_id} failed with exit code {result.returncode}:\n{result.stderr}\n\nSTDOUT:\n{result.stdout}"
                logger.error(error_msg)
                return {'status': 'failed', 'error': result.stderr.strip() or "Unknown error (check logs)"}
                
            # Re-read job.json to get the updates applied by the script itself
            with open(job_json_path, 'r') as f:
                final_meta = json.load(f)
                
            # The parent `api_module_run` view expects us to return the *updates* Dictionary.
            # But since the subprocess mutated the entire json natively, we just return the whole object,
            # and `api_module_run` handles the merge blindly!
            return final_meta
            
        except Exception as e:
            logger.exception(f"PythonBackend execution exception for {self.module_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
