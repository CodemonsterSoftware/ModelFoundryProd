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
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from django.core.files import File
from django.db import transaction
from projects.models import Project, Group, Part



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
# Core Framework Views
# =============================================================================
from .module_registry import registry
from .module_manager import ModuleManager

@login_required
def forge_index(request):
    """Main Forge tools dashboard."""
    modules = registry.get_all_modules()
    active_modules = [m for m in modules if m.get('enabled', True)]
    
    return render(request, 'forge/index.html', {
        'modules': active_modules
    })

@login_required
def module_view(request, module_id: str):
    """Renders the UI for a specific module."""
    try:
        module = registry.get_module(module_id)
        if not module.get('enabled', True):
            return render(request, 'forge/error.html', {'error': 'Module disabled'})

        template = module.get('template', 'forge/module_generic.html')
        context = {'module': module}

        return render(request, template, context)
    except KeyError:
        return render(request, 'forge/error.html', {'error': 'Module not found'}, status=404)

@login_required
@require_POST
def api_module_run(request, module_id: str):
    """Generic endpoint to submit a job to a module engine."""
    # (Implementation to route payload to backends)
    return JsonResponse({'success': False, 'error': 'Not implemented yet'})

@login_required
@require_POST
def install_module(request):
    """Endpoint to trigger installing a module from a github manifest URL."""
    manifest_url = request.POST.get('manifest_url')
    if not manifest_url:
        return JsonResponse({'success': False, 'error': 'Missing url'}, status=400)
    
    try:
        success = ModuleManager.install_from_github_manifest(manifest_url)
        return JsonResponse({'success': success})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def uninstall_module(request, module_id: str):
    """Endpoint to uninstall a module."""
    if not module_id:
        return JsonResponse({'success': False, 'error': 'Missing module_id'}, status=400)
    
    success = ModuleManager.uninstall_module(module_id)
    if success:
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Failed to uninstall module'}, status=500)



# =============================================================================
# API Endpoints
# =============================================================================



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



@login_required
def api_projects(request):
    """API: List projects for the current user."""
    projects = Project.objects.filter(user=request.user).order_by('-updated_at')
    data = []
    for p in projects:
        groups = [{'id': g.id, 'name': g.name} for g in p.groups.all().order_by('name')]
        data.append({
            'id': p.id, 
            'name': p.name,
            'groups': groups
        })
    return JsonResponse({'success': True, 'projects': data})


@login_required
@require_POST
def api_module_run(request, module_id: str):
    """API: Dynamically executes a module's backend run hook."""
    from .module_registry import registry
    try:
        module = registry.get_module(module_id)
        if not module.get('enabled', True):
            return JsonResponse({'success': False, 'error': 'Module disabled'}, status=400)
            
        # Generate generic job ID
        job_id = str(uuid.uuid4())
        job_dir = get_job_dir(job_id)
        
        # Save any universally uploaded input files to the job dir
        input_path = None
        if 'input_file' in request.FILES:
             f = request.FILES['input_file']
             input_path = job_dir / f.name
             with open(input_path, 'wb') as dst:
                 for chunk in f.chunks():
                     dst.write(chunk)
                     
        # Setup job struct
        job_meta = {
             'id': job_id,
             'module': module_id,
             'status': 'queued',
             'input_file': str(input_path) if input_path else None,
             'params': request.POST.dict() # Dump ALL post parameters gracefully mapped to string values
        }
        
        # Write initial state
        with open(job_dir / 'job.json', 'w') as f:
             json.dump(job_meta, f)
             
        # Factory initialization of dynamic backend based on manifest string
        backend_type = module.get('backend', 'python').lower()
        if backend_type == 'python':
            from .backends.python import PythonBackend
            engine = PythonBackend(module_id=module_id, manifest=module)
        elif backend_type == 'blender':
            from .backends.blender import BlenderBackend
            engine = BlenderBackend()
        elif backend_type == 'openscad':
            from .backends.openscad import OpenSCADBackend
            engine = OpenSCADBackend()
        else:
            raise ValueError(f"Unknown backend requested: {backend_type}")
            
        # Blocking Execution Hook
        # In a deep production setup this would be handed to Celery, but we run sync here currently
        updates = engine.run_task(
            job_meta=job_meta,
            input_path=str(input_path) if input_path else None,
            output_dir=str(job_dir)
        )
        
        # Merge dictionary updates safely returned from the plugin back onto the job struct
        job_meta.update(updates)
        if 'status' not in updates: # Safety fallback
            job_meta['status'] = 'completed'
            
        with open(job_dir / 'job.json', 'w') as f:
             json.dump(job_meta, f)
             
        return JsonResponse({
             'success': job_meta['status'] == 'completed',
             'job_id': job_id,
             'status': job_meta['status'],
             'message': job_meta.get('error', 'Execution completed'),
             # Pass generic hook returns forward verbatim
             'payload': updates
        })
        
    except KeyError:
        return JsonResponse({'success': False, 'error': 'Module not found'}, status=404)
    except Exception as e:
        logger.exception(f"Dynamic module execution failed for {module_id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def api_save_job_parts(request):
    """API: Save sliced parts from a job to a project."""
    try:
        data = json.loads(request.body)
        job_id = data.get('job_id')
        project_id = data.get('project_id')
        group_name = data.get('group_name')
        
        if not all([job_id, project_id, group_name]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
            
        # Verify project ownership
        project = get_object_or_404(Project, id=project_id, user=request.user)
        
        # Get Job Data
        job_dir = FORGE_JOBS_DIR / job_id
        job_file = job_dir / 'job.json'
        
        if not job_file.exists():
            return JsonResponse({'success': False, 'error': 'Job not found'}, status=404)
            
        with open(job_file) as f:
            job_meta = json.load(f)
            
        if job_meta.get('status') != 'completed':
            return JsonResponse({'success': False, 'error': 'Job not completed'}, status=400)
            
        # Create or Get Group
        # We generally want to create a new group for the slice result
        group, created = Group.objects.get_or_create(
            project=project,
            name=group_name
        )
        
        saved_count = 0
        
        # Use transaction to ensure atomicity
        with transaction.atomic():
            for part_info in job_meta.get('parts', []):
                if not isinstance(part_info, dict):
                    continue
                    
                filename = part_info.get('filename')
                rel_path = part_info.get('path')
                
                if not filename or not rel_path:
                    continue
                    
                source_path = FORGE_JOBS_DIR / rel_path
                if not source_path.exists():
                    logger.warning(f"Source file missing: {source_path}")
                    continue
                
                # Create Part
                part = Part(
                    project=project,
                    group=group,
                    name=Path(filename).stem,  # Remove extension
                    quantity=1,
                    completed=0
                )
                
                # Save file (this will copy it to the media storage defined in Part model)
                with open(source_path, 'rb') as f:
                    part.stl_file.save(filename, File(f), save=True)
                
                saved_count += 1
                
        return JsonResponse({
            'success': True, 
            'message': f'Saved {saved_count} parts to project "{project.name}" in group "{group.name}"'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Save parts error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
