#!/usr/bin/env python3
"""
CuraEngine API Server
This script provides a REST API for interacting with CuraEngine.
"""
import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directories
DATA_DIR = Path('/app/data')
PROFILES_DIR = DATA_DIR / 'profiles'
OUTPUT_DIR = DATA_DIR / 'output'
TEMP_DIR = DATA_DIR / 'temp'

# Ensure directories exist
for directory in [DATA_DIR, PROFILES_DIR, OUTPUT_DIR, TEMP_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# CuraEngine path
CURA_ENGINE = '/opt/CuraEngine/build/CuraEngine'

# Default Cura configuration files
DEFAULT_DEFINITION_FILE = '/app/resources/fdmprinter.def.json'
DEFAULT_EXTRUDER_FILE = '/app/resources/fdmextruder.def.json'

# Default profiles
DEFAULT_PROFILES = {
    'default': {
        'layer_height': 0.2,
        'infill_sparse_density': 20,
        'speed_print': 50,
        'material_print_temperature': 200,
        'material_bed_temperature': 60,
        'retraction_enable': True,
        'retraction_amount': 5,
        'retraction_speed': 45,
        'adhesion_type': 'skirt',
    },
    'draft': {
        'layer_height': 0.3,
        'infill_sparse_density': 15,
        'speed_print': 60,
        'material_print_temperature': 210,
        'material_bed_temperature': 60,
        'retraction_enable': True,
        'retraction_amount': 5,
        'retraction_speed': 45,
        'adhesion_type': 'skirt',
    },
    'fine': {
        'layer_height': 0.1,
        'infill_sparse_density': 20,
        'speed_print': 40,
        'material_print_temperature': 200,
        'material_bed_temperature': 60,
        'retraction_enable': True,
        'retraction_amount': 5,
        'retraction_speed': 45,
        'adhesion_type': 'skirt',
    },
}

# Initialize default profiles if they don't exist
for profile_name, profile_settings in DEFAULT_PROFILES.items():
    profile_path = PROFILES_DIR / f"{profile_name}.json"
    if not profile_path.exists():
        with open(profile_path, 'w') as f:
            json.dump(profile_settings, f, indent=2)

@app.route('/version', methods=['GET'])
def get_version():
    """Get the version of CuraEngine."""
    try:
        result = subprocess.run(
            [CURA_ENGINE, 'version'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return jsonify({
                'status': 'success',
                'version': version
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Error getting version: {result.stderr}"
            }), 500
    except Exception as e:
        logger.error(f"Error getting version: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting version: {str(e)}"
        }), 500

@app.route('/profiles', methods=['GET'])
def get_profiles():
    """Get available slicing profiles."""
    try:
        profiles = []
        for profile_file in PROFILES_DIR.glob('*.json'):
            profiles.append(profile_file.stem)
        return jsonify(profiles)
    except Exception as e:
        logger.error(f"Error getting profiles: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting profiles: {str(e)}"
        }), 500

@app.route('/profiles/<profile_name>', methods=['GET'])
def get_profile(profile_name):
    """Get a specific slicing profile."""
    profile_path = PROFILES_DIR / f"{profile_name}.json"
    try:
        if profile_path.exists():
            with open(profile_path) as f:
                profile = json.load(f)
            return jsonify(profile)
        else:
            return jsonify({
                'status': 'error',
                'message': f"Profile '{profile_name}' not found"
            }), 404
    except Exception as e:
        logger.error(f"Error getting profile '{profile_name}': {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting profile: {str(e)}"
        }), 500

@app.route('/profiles', methods=['POST'])
def create_profile():
    """Create or update a slicing profile."""
    try:
        data = request.json
        if not data or 'name' not in data or 'settings' not in data:
            return jsonify({
                'status': 'error',
                'message': "Missing required fields: 'name' and 'settings'"
            }), 400
        
        profile_name = data['name']
        profile_settings = data['settings']
        
        profile_path = PROFILES_DIR / f"{profile_name}.json"
        with open(profile_path, 'w') as f:
            json.dump(profile_settings, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': f"Profile '{profile_name}' created/updated successfully"
        })
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error creating profile: {str(e)}"
        }), 500

@app.route('/slice', methods=['POST'])
def slice_model():
    """Slice a 3D model file."""
    try:
        # Check if model file was uploaded
        if 'model' not in request.files:
            return jsonify({
                'status': 'error',
                'message': "No model file provided"
            }), 400
        
        model_file = request.files['model']
        
        # Get profile name and parameters
        profile_name = request.form.get('profile', 'default')
        parameters_str = request.form.get('parameters', '{}')
        
        # Parse parameters
        try:
            parameters = json.loads(parameters_str)
        except json.JSONDecodeError:
            parameters = {}
        
        # Check if profile exists
        profile_path = PROFILES_DIR / f"{profile_name}.json"
        if not profile_path.exists():
            return jsonify({
                'status': 'error',
                'message': f"Profile '{profile_name}' not found"
            }), 404
        
        # Load profile settings
        with open(profile_path) as f:
            profile_settings = json.load(f)
        
        # Override with custom parameters
        profile_settings.update(parameters)
        
        # Create temporary files
        with tempfile.TemporaryDirectory(dir=TEMP_DIR) as temp_dir:
            temp_dir_path = Path(temp_dir)
            model_path = temp_dir_path / model_file.filename
            config_path = temp_dir_path / 'config.json'
            gcode_path = temp_dir_path / 'output.gcode'
            
            # Save uploaded model file
            model_file.save(model_path)
            
            # Create config file
            with open(config_path, 'w') as f:
                json.dump(profile_settings, f, indent=2)
            
            # Run CuraEngine slice command
            cmd = [
                CURA_ENGINE, 'slice',
                '-v',  # Verbose output
                '-j', str(DEFAULT_DEFINITION_FILE),  # Printer definition
                '-e0', str(DEFAULT_EXTRUDER_FILE),  # Extruder definition
                '-s', f"layer_height={profile_settings.get('layer_height', 0.2)}",  # Example setting
                '-o', str(gcode_path),  # Output file
                str(model_path)  # Input file
            ]
            
            # Add all settings from profile
            for key, value in profile_settings.items():
                if key != 'layer_height':  # Already added above
                    cmd.extend(['-s', f"{key}={value}"])
            
            logger.info(f"Running CuraEngine command: {' '.join(str(arg) for arg in cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"CuraEngine error: {result.stderr}")
                return jsonify({
                    'status': 'error',
                    'message': f"CuraEngine error: {result.stderr}"
                }), 500
            
            # Return the G-code file
            return send_file(
                gcode_path,
                as_attachment=True,
                download_name=f"{model_file.filename.rsplit('.', 1)[0]}.gcode",
                mimetype='text/plain'
            )
    
    except Exception as e:
        logger.error(f"Error slicing model: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error slicing model: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 