import logging
import os
import requests
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

class BlenderClient:
    """
    Client for communicating with the headless Blender service running in Docker.
    """
    
    def __init__(self):
        # Service name 'blender' from docker-compose, port 8081
        # If running locally without docker networking resolution (e.g. from host), 
        # this might default to localhost:8081 if port mapped.
        # But inside the docker network, it should be http://blender:8081
        
        # We can make this configurable
        self.base_url = getattr(settings, 'BLENDER_SERVICE_URL', 'http://blender:8081')
        self.timeout = 300  # 5 minutes timeout for long running operations

    def is_available(self) -> bool:
        """Check if Blender service is healthy and reachable."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def process_file(self, input_path: str, output_path: str, operation: str, params: dict = None, **kwargs) -> dict:
        """
        Send a processing task to Blender.
        
        Args:
            input_path: Path to input file. Ideally relative to MEDIA_ROOT.
                       If absolute path is provided, we try to make it relative.
            output_path: Path for output file. RELATIVE to MEDIA_ROOT.
            operation: Name of the operation ('convert_stl_to_step', 'slice', etc.)
            params: Additional parameters for the operation.
            **kwargs: Additional top-level fields for the payload (e.g. script_path).
            
        Returns:
            Dict containing the response from the service.
        """
        params = params or {}
        
        # Normalize paths to be relative to MEDIA_ROOT for the shared volume
        rel_input = self._get_relative_path(input_path)
        rel_output = self._get_relative_path(output_path)
        
        payload = {
            "input_file": rel_input,
            "output_file": rel_output,
            "operation": operation,
            "params": params
        }
        payload.update(kwargs)
        
        try:
            logger.info(f"Sending task to Blender: {operation} on {rel_input}")
            response = requests.post(
                f"{self.base_url}/process", 
                json=payload, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Blender service request failed: {e}")
            if e.response:
                logger.error(f"Response: {e.response.text}")
            raise RuntimeError(f"Blender service failed: {str(e)}")

    def run_script(self, script_path: str, context: dict = None) -> dict:
        """
        Run a Python script inside Blender.
        
        Args:
            script_path: Path to the script file (relative to MEDIA_ROOT).
            context: Dictionary of data to pass to the script.
        """
        rel_script = self._get_relative_path(script_path)
        
        payload = {
            "operation": "script",
            "script_path": rel_script,
            "params": context or {}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/process", 
                json=payload, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Blender script execution failed: {e}")
            raise

    def _get_relative_path(self, path: str) -> str:
        """Convert absolute path to relative path from MEDIA_ROOT if possible."""
        if not path:
            return ""
            
        path_obj = Path(path)
        media_root = Path(settings.MEDIA_ROOT)
        
        if path_obj.is_absolute():
            try:
                rel_path = path_obj.relative_to(media_root)
                return str(rel_path).replace(os.sep, '/')
            except ValueError:
                # If it's not in media root, maybe it's already relative?
                # Or it's a temp file not in shared volume. 
                # For now assume it's roughly correct or user knows what they are doing.
                # If running in docker, paths must be in the shared volume.
                logger.warning(f"Path {path} is absolute but not inside MEDIA_ROOT {media_root}. "
                               "This might fail if not in shared volume.")
                return str(path).replace(os.sep, '/') # Return as is, hope for best or mapped elsewhere
        
        return str(path).replace(os.sep, '/')
