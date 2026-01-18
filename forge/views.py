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
        job_meta = {
            'id': job_id,
            'type': 'slice',
            'status': 'queued',
            'input_file': str(input_path),
            'grid': {
                'x': form.cleaned_data['grid_x'],
                'y': form.cleaned_data['grid_y'],
                'z': form.cleaned_data['grid_z'],
            },
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
            output_files = slice_mesh_grid(
                input_path=str(input_path),
                output_dir=str(job_dir),
                grid=job_meta['grid'],
                joint_type=job_meta['joint_type'],
                joint_params=job_meta['joint_params'],
                dovetail_params=job_meta['dovetail_params']
            )
            
            # Create ZIP of all parts
            zip_path = job_dir / f"{Path(stl_file.name).stem}_sliced.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for output_file in output_files:
                    zf.write(output_file, Path(output_file).name)
            
            job_meta['status'] = 'completed'
            job_meta['output_file'] = str(zip_path)
            job_meta['part_count'] = len(output_files)
            
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
