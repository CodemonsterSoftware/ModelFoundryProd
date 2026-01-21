import json
import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ConvertForm, SliceForm

logger = logging.getLogger(__name__)

# Job storage directory
FORGE_JOBS_DIR = Path(settings.MEDIA_ROOT) / 'forge_jobs'
FORGE_JOBS_DIR.mkdir(exist_ok=True, parents=True)


def get_job_dir(job_id: str) -> Path:
    """Get the directory for a specific job."""
    job_dir = FORGE_JOBS_DIR / job_id
    job_dir.mkdir(exist_ok=True, parents=True)
    return job_dir


# =============================================================================
# Page Views
# =============================================================================

@login_required
def forge_index(request):
    """Main Forge tools dashboard."""
    return render(request, 'forge/index.html', {
        'convert_form': ConvertForm(),
        'slice_form': SliceForm(),
    })


@login_required
def convert_stl(request):
    """STL to STEP conversion page."""
    form = ConvertForm()
    return render(request, 'forge/convert.html', {'form': form})


@login_required
def slice_model(request):
    """Grid slicing page."""
    form = SliceForm()
    return render(request, 'forge/slice.html', {'form': form})


# =============================================================================
# API Endpoints
# =============================================================================

@login_required
@require_POST
def api_convert(request):
    """API: Start STL to STEP conversion job."""
    form = ConvertForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)
    
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        job_dir = get_job_dir(job_id)
        
        # Save uploaded file
        stl_file = request.FILES['stl_file']
        input_path = job_dir / stl_file.name
        with open(input_path, 'wb') as f:
            for chunk in stl_file.chunks():
                f.write(chunk)
        
        # Save job metadata
        job_meta = {
            'id': job_id,
            'type': 'convert',
            'status': 'queued',
            'input_file': str(input_path),
            'repair_mesh': form.cleaned_data.get('repair_mesh', True),
            'tolerance': form.cleaned_data.get('tolerance', 0.1),
        }
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f)
        
        # TODO: Queue actual conversion task (for now, sync placeholder)
        # In production, use Celery or similar
        from .services.converter import convert_stl_to_step
        output_path = job_dir / f"{Path(stl_file.name).stem}.step"
        
        try:
            convert_stl_to_step(
                input_path=str(input_path),
                output_path=str(output_path),
                repair=job_meta['repair_mesh'],
                tolerance=job_meta['tolerance']
            )
            job_meta['status'] = 'completed'
            job_meta['output_file'] = str(output_path)
        except Exception as e:
            job_meta['status'] = 'failed'
            job_meta['error'] = str(e)
            logger.error(f"Conversion failed for job {job_id}: {e}")
        
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f)
        
        return JsonResponse({
            'success': job_meta['status'] == 'completed',
            'job_id': job_id,
            'status': job_meta['status'],
            'message': job_meta.get('error', 'Conversion complete')
        })
        
    except Exception as e:
        logger.error(f"API convert error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_slice(request):
    """API: Start grid slicing job."""
    form = SliceForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)
    
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        job_dir = get_job_dir(job_id)
        
        # Save uploaded file
        stl_file = request.FILES['stl_file']
        input_path = job_dir / stl_file.name
        with open(input_path, 'wb') as f:
            for chunk in stl_file.chunks():
                f.write(chunk)
        
        # Extract form data
        slice_mode = form.cleaned_data.get('slice_mode', 'uniform')
        
        # Prepare grid and planes data
        grid_config = {'x': 1, 'y': 1, 'z': 1}
        planes_config = {}
        
        if slice_mode == 'freeform':
            try:
                # Parse the unified freeform planes JSON
                planes_json = request.POST.get('freeform_planes', '[]')
                planes_config = json.loads(planes_json)
                
                # Validate plane data structure
                if not isinstance(planes_config, list):
                    logger.error("freeform_planes is not a list")
                    return JsonResponse({'success': False, 'error': 'Invalid plane data format'}, status=400)
                
                # Validate each plane has required fields
                for idx, plane in enumerate(planes_config):
                    if not isinstance(plane, dict):
                        return JsonResponse({'success': False, 'error': f'Plane {idx+1} is not a valid object'}, status=400)
                    if 'origin' not in plane or 'rotation' not in plane:
                        return JsonResponse({'success': False, 'error': f'Plane {idx+1} missing origin or rotation'}, status=400)
                    if not all(k in plane['origin'] for k in ['x', 'y', 'z']):
                        return JsonResponse({'success': False, 'error': f'Plane {idx+1} origin missing x, y, or z'}, status=400)
                    if not all(k in plane['rotation'] for k in ['x', 'y', 'z']):
                        return JsonResponse({'success': False, 'error': f'Plane {idx+1} rotation missing x, y, or z'}, status=400)
                
                logger.info(f"Validated {len(planes_config)} freeform planes for slicing")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode plane data: {e}")
                return JsonResponse({'success': False, 'error': 'Invalid plane data JSON'}, status=400)
        elif slice_mode == 'fit':
            # Fit mode: Calculate planes needed to fit printer build volume
            import trimesh
            from .services.slicer import calculate_fit_planes
            
            # Load mesh to get dimensions
            mesh = trimesh.load(str(input_path))
            
            # Extract printer dimensions from form
            printer_dims = {
                'x': form.cleaned_data.get('printer_x', 220.0),
                'y': form.cleaned_data.get('printer_y', 220.0),
                'z': form.cleaned_data.get('printer_z', 250.0),
            }
            
            model_units = form.cleaned_data.get('model_units', 'mm')
            desired_size = form.cleaned_data.get('desired_size')
            
            # Get model dimensions from bounds
            bounds = mesh.bounds
            model_dims = {
                'x': bounds[1][0] - bounds[0][0],
                'y': bounds[1][1] - bounds[0][1],
                'z': bounds[1][2] - bounds[0][2],
            }
            
            # Calculate required planes
            fit_grid = calculate_fit_planes(
                model_dims=model_dims,
                printer_dims=printer_dims,
                model_units=model_units,
                desired_size=desired_size
            )
            
            logger.info(f"Fit mode calculated planes: {fit_grid}")
            
            # Convert planes to sections (same logic as uniform mode)
            grid_config = {
                'x': 1 if fit_grid['x'] == 0 else fit_grid['x'] + 1,
                'y': 1 if fit_grid['y'] == 0 else fit_grid['y'] + 1,
                'z': 1 if fit_grid['z'] == 0 else fit_grid['z'] + 1,
            }
        else:
            # Uniform mode: Input is number of planes (cuts).
            # Slicer expects number of sections (grid divisions).
            # Sections = Planes + 1, BUT 0 cuts should mean 1 section (no slicing on that axis)
            # So: 0 input -> 1 section (no cuts), 1 input -> 2 sections (1 cut), etc.
            grid_config = {
                'x': 1 if form.cleaned_data['grid_x'] == 0 else form.cleaned_data['grid_x'] + 1,
                'y': 1 if form.cleaned_data['grid_y'] == 0 else form.cleaned_data['grid_y'] + 1,
                'z': 1 if form.cleaned_data['grid_z'] == 0 else form.cleaned_data['grid_z'] + 1,
            }

        job_meta = {
            'id': job_id,
            'type': 'slice',
            'status': 'queued',
            'input_file': str(input_path),
            'slice_mode': slice_mode,
            'grid': grid_config,
            'planes': planes_config,
            'joint_type': form.cleaned_data['joint_type'],
            'joint_params': {
                'diameter': form.cleaned_data.get('joint_diameter', 4.0),
                'height': form.cleaned_data.get('joint_height', 5.0),
                'clearance': form.cleaned_data.get('joint_clearance', 0.2),
                'count': form.cleaned_data.get('joint_count', 0),
            },
            'dovetail_params': {
                'angle': form.cleaned_data.get('dovetail_angle', 14.0),
                'width': form.cleaned_data.get('dovetail_width', 15.0),
                'depth': form.cleaned_data.get('dovetail_depth', 10.0),
                'count': form.cleaned_data.get('dovetail_count', 0),
            }
        }
        
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f)
        
        # TODO: Queue actual slicing task
        from .services.slicer import slice_mesh_grid
        
        try:
            slice_result = slice_mesh_grid(
                input_path=str(input_path),
                output_dir=str(job_dir),
                grid=job_meta['grid'],
                planes=job_meta.get('planes'),
                joint_type=job_meta['joint_type'],
                joint_params=job_meta['joint_params'],
                dovetail_params=job_meta['dovetail_params']
            )
            
            # Extract results from new dict format
            output_files = slice_result.get('parts', [])
            warnings = slice_result.get('warnings', [])
            blender_required = slice_result.get('blender_required', False)
            dowel_files = slice_result.get('dowel_files', [])
            
            # Create ZIP of all parts (and dowels if present)
            zip_path = job_dir / f"{Path(stl_file.name).stem}_sliced.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for part_data in output_files:
                    # Handle both dict (new) and string (legacy/fallback) formats
                    if isinstance(part_data, dict):
                        file_path = part_data['filepath']
                    else:
                        file_path = part_data
                    
                    zf.write(file_path, Path(file_path).name)
                
                # Add dowel files to zip
                for dowel_data in dowel_files:
                    zf.write(dowel_data['filepath'], Path(dowel_data['filepath']).name)
            
            # Build part information for response
            parts_info = []
            for idx, part_data in enumerate(output_files):
                if isinstance(part_data, dict):
                    part_path = Path(part_data['filepath'])
                    validation = part_data.get('validation', {'valid': True, 'issues': []})
                    has_connectors = part_data.get('has_connectors', False)
                else:
                    part_path = Path(part_data)
                    validation = {'valid': True, 'issues': []}
                    has_connectors = False
                
                parts_info.append({
                    'index': idx,
                    'filename': part_path.name,
                    'path': str(part_path.relative_to(FORGE_JOBS_DIR)),  # Relative path from media root
                    'validation': validation,
                    'has_connectors': has_connectors
                })
            
            # Build dowel info for response
            dowels_info = []
            for dowel_data in dowel_files:
                dowel_path = Path(dowel_data['filepath'])
                dowels_info.append({
                    'filename': dowel_path.name,
                    'path': str(dowel_path.relative_to(FORGE_JOBS_DIR)),
                    'count_needed': dowel_data.get('count_needed', 0),
                    'diameter': dowel_data.get('diameter', 0),
                    'height': dowel_data.get('height', 0)
                })
            
            job_meta['status'] = 'completed'
            job_meta['output_file'] = str(zip_path)
            job_meta['part_count'] = len(output_files)
            job_meta['parts'] = parts_info
            job_meta['warnings'] = warnings
            job_meta['dowels'] = dowels_info
            job_meta['blender_required'] = blender_required
            
        except Exception as e:
            job_meta['status'] = 'failed'
            job_meta['error'] = str(e)
            logger.error(f"Slicing failed for job {job_id}: {e}")
        
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f)
        
        return JsonResponse({
            'success': job_meta['status'] == 'completed',
            'job_id': job_id,
            'status': job_meta['status'],
            'part_count': job_meta.get('part_count', 0),
            'parts': job_meta.get('parts', []),
            'warnings': job_meta.get('warnings', []),
            'dowels': job_meta.get('dowels', []),
            'blender_required': job_meta.get('blender_required', False),
            'message': job_meta.get('error', 'Slicing complete')
        })
        
    except Exception as e:
        logger.error(f"API slice error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_job_status(request, job_id: str):
    """API: Get job status."""
    job_dir = FORGE_JOBS_DIR / job_id
    job_file = job_dir / 'job.json'
    
    if not job_file.exists():
        return JsonResponse({
            'success': False,
            'error': 'Job not found'
        }, status=404)
    
    with open(job_file) as f:
        job_meta = json.load(f)
    
    return JsonResponse({
        'success': True,
        'job': job_meta
    })


@login_required
def api_download(request, job_id: str):
    """API: Download job output file."""
    job_dir = FORGE_JOBS_DIR / job_id
    job_file = job_dir / 'job.json'
    
    if not job_file.exists():
        return JsonResponse({
            'success': False,
            'error': 'Job not found'
        }, status=404)
    
    with open(job_file) as f:
        job_meta = json.load(f)
    
    if job_meta.get('status') != 'completed':
        return JsonResponse({
            'success': False,
            'error': f"Job status: {job_meta.get('status')}"
        }, status=400)
    
    output_path = Path(job_meta.get('output_file', ''))
    if not output_path.exists():
        return JsonResponse({
            'success': False,
            'error': 'Output file not found'
        }, status=404)
    
    return FileResponse(
        open(output_path, 'rb'),
        as_attachment=True,
        filename=output_path.name
    )


@login_required
def api_download_part(request, job_id: str, part_index: int):
    """API: Download individual part file."""
    job_dir = FORGE_JOBS_DIR / job_id
    job_file = job_dir / 'job.json'
    
    if not job_file.exists():
        return JsonResponse({
            'success': False,
            'error': 'Job not found'
        }, status=404)
    
    with open(job_file) as f:
        job_meta = json.load(f)
    
    if job_meta.get('status') != 'completed':
        return JsonResponse({
            'success': False,
            'error': f"Job status: {job_meta.get('status')}"
        }, status=400)
    
    # Get part information
    parts = job_meta.get('parts', [])
    if part_index < 0 or part_index >= len(parts):
        return JsonResponse({
            'success': False,
            'error': 'Invalid part index'
        }, status=400)
    
    part_info = parts[part_index]
    part_path = FORGE_JOBS_DIR / part_info['path']
    
    if not part_path.exists():
        return JsonResponse({
            'success': False,
            'error': 'Part file not found'
        }, status=404)
    
    return FileResponse(
        open(part_path, 'rb'),
        as_attachment=False,  # Allow viewing in browser
        filename=part_info['filename']
    )
