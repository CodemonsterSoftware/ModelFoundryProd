import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from django.conf import settings

logger = logging.getLogger(__name__)

class ModuleRegistry:
    """
    Central registry for discovering and loading ModelFoundry Forge modules.
    """
    
    def __init__(self):
        self.modules: Dict[str, Dict[str, Any]] = {}
        # Assuming the modules directory is inside the forge app
        self.modules_dir = Path(settings.BASE_DIR) / 'forge' / 'modules'
        self.modules_dir.mkdir(exist_ok=True, parents=True)
        self.reload_modules()
        
    def reload_modules(self):
        """Scans the modules directory and loads manifest.json files."""
        self.modules.clear()
        
        if not self.modules_dir.exists():
            return
            
        for module_path in self.modules_dir.iterdir():
            if not module_path.is_dir():
                continue
                
            manifest_file = module_path / 'manifest.json'
            if not manifest_file.exists():
                logger.warning(f"Module found without manifest.json: {module_path.name}")
                continue
                
            try:
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    
                module_id = manifest.get('id', module_path.name)
                manifest['path'] = str(module_path)
                
                # Default values if missing
                manifest.setdefault('name', module_id.replace('_', ' ').title())
                manifest.setdefault('backend', 'python')
                manifest.setdefault('description', '')
                manifest.setdefault('icon', 'fa-puzzle-piece')
                
                self.modules[module_id] = manifest
                logger.info(f"Loaded Forge Module: {module_id}")
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse manifest.json in {module_path.name}")
            except Exception as e:
                logger.error(f"Error loading module {module_path.name}: {e}")
                
    def get_module(self, module_id: str) -> Dict[str, Any]:
        """Returns the module manifest, or raises KeyError if not found."""
        return self.modules[module_id]
        
    def get_all_modules(self) -> List[Dict[str, Any]]:
        """Returns a list of all loaded module manifests."""
        return list(self.modules.values())

# Global singleton
registry = ModuleRegistry()
