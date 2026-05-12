import urllib.request
import json
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

class OFDClient:
    TREE_URL = "https://api.github.com/repos/OpenFilamentCollective/open-filament-database/git/trees/main?recursive=1"
    RAW_BASE_URL = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/"
    CACHE_KEY = "ofd_inventory_tree_v3"
    CACHE_TIMEOUT = 60 * 60 * 24 # 24 hours

    @classmethod
    def get_inventory(cls):
        """
        Fetches and structures the OpenFilamentDatabase inventory.
        Returns a dict: { manufacturer: { type: [ {name: str, url: str} ] } }
        """
        cached_data = cache.get(cls.CACHE_KEY)
        if cached_data:
            return cached_data

        try:
            req = urllib.request.Request(cls.TREE_URL, headers={'User-Agent': 'ModelFoundry-App'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            inventory = {}
            for item in data.get('tree', []):
                path = item.get('path', '')
                if path.startswith('data/'):
                    parts = path.split('/')
                    
                    if path.endswith('filament.json') and len(parts) >= 5:
                        manufacturer = parts[1].replace('_', ' ').title()
                        mat_type = parts[2].upper()
                        name = parts[-2].replace('_', ' ').title()
                        
                        if manufacturer not in inventory:
                            inventory[manufacturer] = {}
                        if mat_type not in inventory[manufacturer]:
                            inventory[manufacturer][mat_type] = {}
                        if name not in inventory[manufacturer][mat_type]:
                            inventory[manufacturer][mat_type][name] = {'url': '', 'variants': []}
                            
                        inventory[manufacturer][mat_type][name]['url'] = cls.RAW_BASE_URL + path

                    elif path.endswith('variant.json') and len(parts) >= 6:
                        manufacturer = parts[1].replace('_', ' ').title()
                        mat_type = parts[2].upper()
                        name = parts[-3].replace('_', ' ').title()
                        color_name = parts[-2].replace('_', ' ').title()
                        
                        if manufacturer not in inventory:
                            inventory[manufacturer] = {}
                        if mat_type not in inventory[manufacturer]:
                            inventory[manufacturer][mat_type] = {}
                        if name not in inventory[manufacturer][mat_type]:
                            inventory[manufacturer][mat_type][name] = {'url': '', 'variants': []}
                            
                        inventory[manufacturer][mat_type][name]['variants'].append({
                            'name': color_name,
                            'url': cls.RAW_BASE_URL + path
                        })
            
            # Sort variants
            for mfg in inventory:
                for mat_type in inventory[mfg]:
                    for name in inventory[mfg][mat_type]:
                        inventory[mfg][mat_type][name]['variants'] = sorted(inventory[mfg][mat_type][name]['variants'], key=lambda x: x['name'])
            
            cache.set(cls.CACHE_KEY, inventory, cls.CACHE_TIMEOUT)
            return inventory

        except Exception as e:
            logger.error(f"Failed to fetch OFD tree: {e}")
            return {}

    @classmethod
    def get_filament_data(cls, url):
        """
        Fetches the raw JSON data for a specific filament from GitHub.
        """
        # Security check to only allow OFD github urls
        if not url.startswith(cls.RAW_BASE_URL):
            raise ValueError("Invalid OFD URL")
            
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ModelFoundry-App'})
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to fetch filament data from {url}: {e}")
            return None
