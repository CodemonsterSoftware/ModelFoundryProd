import subprocess
import logging
import uuid
import tempfile
import urllib.request
import json
import zipfile
import shutil
import os
from pathlib import Path
from django.conf import settings
from .module_registry import registry

logger = logging.getLogger(__name__)

class ModuleManager:
    """
    Handles installation and removal of modules from remote sources.
    """
    
    @classmethod
    def install_from_github_manifest(cls, manifest_url: str) -> bool:
        """
        Installs a module by downloading a zip archive dictated by the manifest url.
        """
        try:
            # Auto-convert github blob URLs to raw URLs for better UX
            if "github.com" in manifest_url and "/blob/" in manifest_url:
                manifest_url = manifest_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                logger.info(f"Auto-converted GitHub blob URL to raw URL: {manifest_url}")

            # 1. Fetch remote manifest
            req = urllib.request.Request(manifest_url)
            with urllib.request.urlopen(req) as response:
                manifest_data = json.loads(response.read().decode('utf-8-sig'))
                
            module_id = manifest_data.get('id')
            if not module_id:
                raise ValueError("Manifest missing 'id'")
                
            download_url = manifest_data.get('download') or manifest_data.get('download_url')
            if not download_url:
                # Fallback purely for demonstration or local dev testing
                raise ValueError("Manifest missing 'download' url for zip payload.")
            
            # Destination paths
            modules_dir = Path(settings.BASE_DIR) / 'forge' / 'modules'
            dest_dir = modules_dir / module_id
            
            # 2. Download zip to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
                logger.info(f"Downloading module package from {download_url}...")
                with urllib.request.urlopen(urllib.request.Request(download_url)) as dl_resp:
                    shutil.copyfileobj(dl_resp, tmp_zip)
                tmp_zip_path = tmp_zip.name
            
            try:
                # 3. Purge existing installation if present
                if dest_dir.exists():
                    logger.info(f"Overwriting existing module {module_id}...")
                    # ignore_errors=True prevents Windows/Docker file-locking crashes (Errno 39)
                    shutil.rmtree(dest_dir, ignore_errors=True)
                    
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # 4. Extract zip
                # Note: GitHub typically dumps into a wrapper folder (e.g., repo-name-main/)
                # We need to flatten this to `module_id/` directly.
                with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                    # Find common root prefix
                    file_list = zip_ref.namelist()
                    if not file_list:
                         raise ValueError("Downloaded module zip is empty.")
                         
                    # Determine string prefix
                    common_prefix = os.path.commonpath([f for f in file_list if not f.endswith('/')])
                    
                    if common_prefix and file_list[0].startswith(common_prefix + '/'):
                         prefix_len = len(common_prefix) + 1
                    else:
                         prefix_len = 0
                    
                    # Extract and structure correctly
                    for file_info in zip_ref.infolist():
                        if file_info.is_dir():
                            continue
                            
                        # Remove base directory wrapper
                        target_sub_path = file_info.filename[prefix_len:] if prefix_len else file_info.filename
                        if not target_sub_path:
                            continue
                        
                        target_full_path = dest_dir / target_sub_path
                        target_full_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        with zip_ref.open(file_info) as source, open(target_full_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                            
                logger.info(f"Module physically extracted to {dest_dir}.")
                
                # 5. Dependency Installation Loop (Isolated .venv)
                venv_dir = dest_dir / '.venv'
                venv_bin = venv_dir / 'bin'
                venv_python = venv_bin / 'python'
                venv_pip = venv_bin / 'pip'
                
                logger.info(f"Creating isolated virtual environment at {venv_dir}...")
                # Use --clear to ensure a clean venv, especially if shutil.rmtree missed files due to Windows locking
                subprocess.run(["python", "-m", "venv", "--clear", str(venv_dir)], check=True)
                
                # Read from the effectively fresh local manifest structure
                local_manifest = dest_dir / 'manifest.json'
                if local_manifest.exists():
                    with open(local_manifest, 'r') as f:
                        local_data = json.load(f)
                        deps = local_data.get('dependencies', {}).get('pip', [])
                        if deps:
                           logger.info(f"Installing manifest dependencies into .venv: {deps}")
                           cmd = [str(venv_pip), "install", "--no-cache-dir"] + deps
                           subprocess.run(cmd, check=True)
                
                # Fallback to pure requirements.txt
                req_file = dest_dir / 'requirements.txt'
                if req_file.exists():
                    logger.info(f"Installing requirements files into .venv via {req_file}...")
                    subprocess.run([str(venv_pip), "install", "--no-cache-dir", "-r", str(req_file)], check=True)
                    
                # 6. Reload registry across system
                registry.reload_modules()
                return True
                
            finally:
                if os.path.exists(tmp_zip_path):
                    os.remove(tmp_zip_path)
            
        except Exception as e:
            logger.error(f"Failed to install module from {manifest_url}: {e}")
            raise Exception(f"{e}")

    @classmethod
    def uninstall_module(cls, module_id: str) -> bool:
        """
        Uninstalls a module by deleting its directory and reloading the registry.
        """
        try:
            if not module_id:
                raise ValueError("Module ID is required for uninstallation.")

            modules_dir = Path(settings.BASE_DIR) / 'forge' / 'modules'
            dest_dir = modules_dir / module_id

            if not dest_dir.exists() or not dest_dir.is_dir():
                logger.warning(f"Attempted to uninstall module '{module_id}' but it does not exist at {dest_dir}.")
                return False

            logger.info(f"Uninstalling module '{module_id}' by removing directory {dest_dir}...")
            shutil.rmtree(dest_dir)
            
            logger.info(f"Module '{module_id}' successfully removed. Reloading registry...")
            registry.reload_modules()
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall module '{module_id}': {e}")
            return False
