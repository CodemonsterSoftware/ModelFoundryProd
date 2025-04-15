from django.shortcuts import render
import os
import zipfile
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from .models import Project, Part, Group, PurchasedPart, ProjectImage, Designer, Material, Instructions
from .forms import (
    ProjectForm, PartForm, GroupForm, PurchasedPartForm,
    ProjectImageForm, BulkUploadForm, DesignerForm, MaterialForm
)
from django.db.models import Count, Sum, Max
from django.contrib.auth.decorators import login_required
import tempfile
from django.core.files import File
import numpy as np
from stl import mesh
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from decimal import Decimal
from datetime import datetime

# Create your views here.

class ProjectListView(ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'

class ProjectDetailView(DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['parts'] = self.object.parts.all().order_by('group__name', 'name')
        context['purchased_parts'] = self.object.purchased_parts.all()
        context['images'] = self.object.images.all()
        context['groups'] = self.object.groups.all()
        # Include material colors in the context
        materials = Material.objects.filter(is_active=True).order_by('name')
        context['materials'] = materials
        context['material_colors'] = {str(m.id): m.color for m in materials if m.color}
        # Include instructions in the context
        context['instructions'] = self.object.instructions.all().order_by('order')
        # Include PurchasedPart model for status choices
        context['PurchasedPart'] = PurchasedPart
        return context

class ProjectCreateView(CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    success_url = reverse_lazy('projects:project_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        self.object = form.save()
        
        # Handle multiple file uploads
        files = self.request.FILES
        for key in files:
            if key.startswith('image_'):
                ProjectImage.objects.create(
                    project=self.object,
                    image=files[key]
                )
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'redirect_url': reverse('projects:project_detail', args=[self.object.id])
            })
        else:
            messages.success(self.request, 'Project created successfully!')
            return redirect('projects:project_detail', self.object.id)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Please correct the errors below.',
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    
    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        self.object = form.save()
        
        # Handle multiple file uploads
        files = self.request.FILES
        for key in files:
            if key.startswith('image_'):
                ProjectImage.objects.create(
                    project=self.object,
                    image=files[key]
                )
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'redirect_url': self.get_success_url()
            })
        else:
            messages.success(self.request, 'Project updated successfully!')
            return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Please correct the errors below.',
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

class ProjectDeleteView(DeleteView):
    model = Project
    success_url = reverse_lazy('projects:project_list')
    template_name = 'projects/project_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(request, 'Project deleted successfully.')
        return redirect(success_url)

def upload_files(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            zip_file = request.FILES['zip_file']
            
            with zipfile.ZipFile(zip_file) as z:
                for filename in z.namelist():
                    if filename.lower().endswith('.stl'):
                        # Extract the file
                        file_data = z.read(filename)
                        part_name = os.path.splitext(os.path.basename(filename))[0]
                        
                        # Create the part
                        part = Part.objects.create(
                            project=project,
                            name=part_name,
                            quantity=1,  # Default value
                            material='',  # Empty by default
                            color='',  # Empty by default
                            stl_file=file_data
                        )
            
            messages.success(request, 'Files uploaded successfully')
            return redirect('projects:project_detail', pk=project.id)
    else:
        form = BulkUploadForm()
    
    return render(request, 'projects/upload_files.html', {
        'form': form,
        'project': project
    })

def add_part(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = PartForm(request.POST, request.FILES, project=project)
        if form.is_valid():
            part = form.save(commit=False)
            part.project = project
            part.save()
            return redirect('projects:project_detail', pk=project.id)
    else:
        form = PartForm(project=project)
    
    return render(request, 'projects/part_form.html', {
        'form': form,
        'project': project
    })

def add_group(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            if not name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Group name is required'
                }, status=400)
                
            # Check if group with same name already exists
            if Group.objects.filter(project=project, name=name).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'A group with this name already exists'
                }, status=400)
                
            # Create the group
            group = Group.objects.create(
                project=project,
                name=name
            )
            
            return JsonResponse({
                'status': 'success',
                'group_id': group.id
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

def add_purchased_part(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = PurchasedPartForm(request.POST)
        if form.is_valid():
            part = form.save(commit=False)
            part.project = project
            part.save()
            return redirect('projects:project_detail', pk=project.id)
    else:
        form = PurchasedPartForm()
    
    return render(request, 'projects/purchased_part_form.html', {
        'form': form,
        'project': project
    })

def upload_project_images(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        try:
            # Get all files from the request
            files = request.FILES
            success_count = 0
            
            # Process each uploaded file
            for key in files:
                if key.startswith('image_'):
                    # Create a new ProjectImage for each file
                    image = ProjectImage(
                        project=project,
                        image=files[key]
                    )
                    image.save()
                    success_count += 1
            
            if success_count > 0:
                messages.success(request, f'Successfully uploaded {success_count} image(s)')
            else:
                messages.warning(request, 'No images were uploaded')
                
            return redirect('projects:project_detail', pk=project.id)
            
        except Exception as e:
            messages.error(request, f'Error uploading images: {str(e)}')
            return redirect('projects:project_detail', pk=project.id)
    
    return render(request, 'projects/upload_images.html', {
        'project': project
    })

def update_part_completion(request, part_id):
    if request.method == 'POST':
        part = get_object_or_404(Part, id=part_id)
        completed = request.POST.get('completed', 0)
        try:
            completed = int(completed)
            if 0 <= completed <= part.quantity:
                part.completed = completed
                part.save()
                return JsonResponse({'status': 'success'})
        except ValueError:
            pass
    return JsonResponse({'status': 'error'}, status=400)

def update_part_group(request, part_id):
    if request.method == 'POST':
        part = get_object_or_404(Part, id=part_id)
        group_id = request.POST.get('group_id')
        
        if group_id:
            group = get_object_or_404(Group, id=group_id)
            part.group = group
        else:
            part.group = None
            
        part.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

def part_details(request, part_id):
    part = get_object_or_404(Part, id=part_id)
    # Convert volume from mm³ to in³ (1 in³ = 16387.064 mm³)
    volume_in3 = part.volume / 16387.064 if part.volume else None
    data = {
        'name': part.name,
        'quantity': part.quantity,
        'material_id': part.material.id if part.material else None,
        'color': part.color,
        'group_id': part.group.id if part.group else None,
        'completed': part.completed,
        'volume': volume_in3,
        'material_cost': float(part.material_cost) if part.material_cost else None,
    }
    
    # Only include stl_url if the file exists
    if part.stl_file:
        data['stl_url'] = request.build_absolute_uri(part.stl_file.url)
    
    return JsonResponse(data)

def update_part(request, part_id):
    if request.method == 'POST':
        try:
            part = Part.objects.get(id=part_id)
            material_id = request.POST.get('material_id')
            
            # Update part fields
            part.name = request.POST.get('name', part.name)
            part.quantity = int(request.POST.get('quantity', part.quantity))
            part.color = request.POST.get('color', part.color)
            
            # Handle material assignment
            if material_id:
                try:
                    material = Material.objects.get(id=material_id)
                    part.material = material
                except Material.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Material not found'}, status=400)
            else:
                part.material = None
            
            # Handle group assignment
            group_id = request.POST.get('group')
            if group_id:
                try:
                    group = Group.objects.get(id=group_id)
                    part.group = group
                except Group.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Group not found'}, status=400)
            else:
                part.group = None
                
            part.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@login_required
def update_purchased_part_status(request, part_id):
    if request.method == 'POST':
        try:
            part = PurchasedPart.objects.get(id=part_id)
            new_status = request.POST.get('status')
            
            # Validate status
            if new_status not in dict(PurchasedPart.STATUS_CHOICES):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid status'
                }, status=400)
                
            part.status = new_status
            part.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Status updated successfully'
            })
        except PurchasedPart.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Part not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

def add_multiple_parts(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        try:
            # Get the parts data from the request
            parts_data = json.loads(request.POST.get('parts', '[]'))
            created_parts = []
            
            # Process each part
            for part_data in parts_data:
                # Create the part
                part = Part.objects.create(
                    project=project,
                    name=part_data['name'],
                    quantity=part_data['quantity'],
                    material_id=part_data['material'],
                    color=part_data['color']
                )
                created_parts.append(part)
                
                # Set the group if specified
                if part_data.get('group'):
                    group = get_object_or_404(Group, id=part_data['group'])
                    part.group = group
                    part.save()
            
            # Handle file uploads
            files = request.FILES.getlist('files')
            for i, file in enumerate(files):
                if i < len(created_parts):
                    part = created_parts[i]
                    # Save the file to the part
                    part.stl_file.save(file.name, file, save=True)
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    # For GET requests, render the template
    groups = project.groups.all()
    materials = Material.objects.filter(is_active=True).order_by('name')
    return render(request, 'projects/add_parts.html', {
        'project': project,
        'groups': groups,
        'materials': materials
    })

def index(request):
    recent_projects = Project.objects.all().order_by('-created_at')[:6]
    return render(request, 'projects/index.html', {
        'recent_projects': recent_projects
    })

def copy_mirror_part(request, part_id):
    try:
        # First get the part without user check
        original_part = get_object_or_404(Part, id=part_id)
        project_id = original_part.project.id
        
        # Create a new part with "(mirrored)" appended to the name
        new_part = Part.objects.create(
            project=original_part.project,
            name=f"{original_part.name} (Left)",
            color=original_part.color,
            material=original_part.material,
            quantity=original_part.quantity,
            group=original_part.group,
            completed=0,
            stl_file=original_part.stl_file
        )
        original_part.name = f"{original_part.name} (Right)"
        original_part.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully created mirrored part: {new_part.name}'
            })
        else:
            messages.success(request, f'Successfully created mirrored part: {new_part.name}')
            return redirect('projects:project_detail', pk=project_id)

    except Exception as e:
        print(e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': f'Error creating mirrored part: {str(e)}'
            }, status=500)
        else:
            messages.error(request, f'Error creating mirrored part: {str(e)}')
            # Try to get the project_id from the URL or session if available
            try:
                project_id = request.GET.get('project_id') or request.session.get('last_project_id')
                if project_id:
                    return redirect('projects:project_detail', pk=project_id)
            except:
                pass
            return redirect('projects:index')

@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            
            # Handle multiple file uploads
            files = request.FILES
            for key in files:
                if key.startswith('image_'):
                    ProjectImage.objects.create(
                        project=project,
                        image=files[key]
                    )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'redirect_url': reverse('projects:project_detail', args=[project.id])})
            else:
                messages.success(request, 'Project created successfully!')
                return redirect('projects:project_detail', project.id)
    else:
        form = ProjectForm()
    return render(request, 'projects/project_form.html', {'form': form})

@login_required
def designer_index(request):
    """Display a list of all designers and their projects."""
    # Get all users who have designed projects
    designers = Designer.objects.all()
    designer_data = []
    
    for designer in designers:
        # Get projects where this user is the designer
        projects = Project.objects.filter(designer=designer)
        total_projects = projects.count()
        total_parts = Part.objects.filter(project__in=projects).count()
        
        designer_data.append({
            'designer': designer,
            'total_projects': total_projects,
            'total_parts': total_parts,
            'projects': projects
        })
    
    # Handle form submission
    if request.method == 'POST':
        form = DesignerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Designer added successfully!')
            return redirect('projects:designer_index')
    else:
        form = DesignerForm()
    
    return render(request, 'projects/designer_index.html', {
        'designer_data': designer_data,
        'form': form
    })

@login_required
def designer_detail(request, designer_id):
    """Display detailed information about a designer and their projects."""
    designer = get_object_or_404(Designer, id=designer_id)
    projects = Project.objects.filter(designer=designer).order_by('-created_at')
    
    return render(request, 'projects/designer_detail.html', {
        'designer': designer,
        'projects': projects
    })

@login_required
def designer_update(request, designer_id):
    designer = get_object_or_404(Designer, id=designer_id)
    
    if request.method == 'POST':
        form = DesignerForm(request.POST, request.FILES, instance=designer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Designer updated successfully!')
            return redirect('projects:designer_detail', designer_id=designer.id)
    else:
        form = DesignerForm(instance=designer)
    
    return render(request, 'projects/designer_form.html', {
        'form': form,
        'designer': designer
    })

@login_required
def material_list(request):
    """View for listing all materials."""
    materials = Material.objects.filter(is_active=True).order_by('name')
    return render(request, 'projects/material_list.html', {
        'materials': materials,
    })

@login_required
def material_create(request):
    """Create a new material."""
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            messages.success(request, f'Material "{material.name}" created successfully.')
            return redirect('projects:material_list')
    else:
        form = MaterialForm()
    
    return render(request, 'projects/material_form.html', {
        'form': form,
        'title': 'Add Material',
    })

@login_required
def material_edit(request, material_id):
    """Edit an existing material."""
    material = get_object_or_404(Material, id=material_id)
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            material = form.save()
            messages.success(request, f'Material "{material.name}" updated successfully.')
            return redirect('projects:material_list')
    else:
        form = MaterialForm(instance=material)
    
    return render(request, 'projects/material_form.html', {
        'form': form,
        'title': f'Edit {material.name}',
        'material': material,
    })

@login_required
def download_stl(request, part_id):
    """Download the STL file for a part."""
    part = get_object_or_404(Part, id=part_id)
    
    if not part.stl_file:
        return JsonResponse({
            'status': 'error',
            'message': 'No STL file available for this part'
        }, status=404)
    
    response = HttpResponse(part.stl_file, content_type='application/sla')
    response['Content-Disposition'] = f'attachment; filename="{part.name}.stl"'
    return response

@login_required
def update_part_progress(request, part_id):
    if request.method == 'POST':
        try:
            part = Part.objects.get(id=part_id)
            completed = int(request.POST.get('completed', 0))
            
            # Validate completed value
            if completed < 0:
                completed = 0
            if completed > part.quantity:
                completed = part.quantity
                
            part.completed = completed
            part.save()
            
            # Calculate total completed parts for the project
            total_completed = Part.objects.filter(project=part.project).aggregate(
                total=Sum('completed')
            )['total'] or 0
            
            return JsonResponse({
                'status': 'success',
                'total_completed': total_completed
            })
        except Part.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Part not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

@login_required
def upload_instructions(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        images = request.FILES.getlist('images')
        description_format = request.POST.get('description_format', 'filename')
        
        if not images:
            return JsonResponse({
                'status': 'error',
                'message': 'No images were uploaded'
            })
        
        try:
            # Get the current highest order number
            current_highest_order = Instructions.objects.filter(project=project).aggregate(Max('order'))['order__max'] or 0
            
            # Sort images by filename
            images = sorted(images, key=lambda x: x.name)
            
            for index, image in enumerate(images, current_highest_order + 1):
                description = ''
                if description_format == 'filename':
                    description = os.path.splitext(image.name)[0]
                elif description_format == 'step':
                    description = f'Step {index}'
                
                Instructions.objects.create(
                    project=project,
                    image=image,
                    description=description,
                    order=index
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully uploaded {len(images)} instructions'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    # Get existing instructions ordered by their order field
    existing_instructions = Instructions.objects.filter(project=project).order_by('order')
    
    return render(request, 'projects/upload_instructions.html', {
        'project': project,
        'existing_instructions': existing_instructions
    })

@login_required
def delete_instruction(request, project_id):
    if request.method == 'POST':
        instruction_id = request.POST.get('instruction_id')
        try:
            instruction = Instructions.objects.get(id=instruction_id, project_id=project_id)
            instruction.delete()
            return JsonResponse({'status': 'success'})
        except Instructions.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Instruction not found'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })

@login_required
def purchased_part_details(request, part_id):
    try:
        part = PurchasedPart.objects.get(id=part_id)
        return JsonResponse({
            'name': part.name,
            'price': float(part.price),
            'quantity': part.quantity,
            'link': part.link,
            'status': part.status
        })
    except PurchasedPart.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Purchased part not found'
        }, status=404)

@login_required
def update_purchased_part(request, part_id):
    try:
        part = PurchasedPart.objects.get(id=part_id)
        
        # Update fields
        part.name = request.POST.get('name', part.name)
        part.price = float(request.POST.get('price', part.price))
        part.quantity = int(request.POST.get('quantity', part.quantity))
        part.link = request.POST.get('link', part.link)
        part.status = request.POST.get('status', part.status)
        
        # Validate data
        if not part.name:
            return JsonResponse({
                'status': 'error',
                'message': 'Name is required'
            })
        if part.price < 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Price must be a positive number'
            })
        if part.quantity < 1:
            return JsonResponse({
                'status': 'error',
                'message': 'Quantity must be at least 1'
            })
        
        part.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Purchased part updated successfully'
        })
    except PurchasedPart.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Purchased part not found'
        }, status=404)
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid number format: {str(e)}'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def delete_purchased_part(request, part_id):
    if request.method == 'POST':
        try:
            part = get_object_or_404(PurchasedPart, id=part_id)
            part.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def export_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Create a temporary directory to store files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create subdirectories for different file types
        stl_dir = os.path.join(temp_dir, 'stl_files')
        thumbnail_dir = os.path.join(temp_dir, 'thumbnails')
        instructions_dir = os.path.join(temp_dir, 'instructions')
        project_images_dir = os.path.join(temp_dir, 'project_images')
        
        # Create all directories
        for directory in [stl_dir, thumbnail_dir, instructions_dir, project_images_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Prepare project data for manifest
        project_data = {
            'metadata': {
                'name': project.name,
                'description': project.description,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'designer': project.designer.name if project.designer else None,
                'designer_id': project.designer.id if project.designer else None
            },
            'materials': [],
            'groups': [],
            'parts': [],
            'purchased_parts': [],
            'instructions': [],
            'project_images': []
        }
        
        # Export materials
        materials_used = set()
        for part in project.parts.all():
            if part.material:
                materials_used.add(part.material)
        
        for material in materials_used:
            material_data = {
                'id': material.id,
                'name': material.name,
                'type': material.type,
                'description': material.description,
                'density': float(material.density) if material.density else None,
                'color': material.color,
                'is_active': material.is_active,
                'brand': material.brand,
                'link': material.link,
                'cost': float(material.cost) if material.cost else None,
                'weight': float(material.weight) if material.weight else None
            }
            project_data['materials'].append(material_data)
        
        # Export groups
        for group in project.groups.all():
            group_data = {
                'id': group.id,
                'name': group.name
            }
            project_data['groups'].append(group_data)
        
        # Export parts
        for part in project.parts.all():
            part_data = {
                'id': part.id,
                'name': part.name,
                'quantity': part.quantity,
                'material_id': part.material.id if part.material else None,
                'material_name': part.material_name,
                'color': part.color,
                'completed': part.completed,
                'group_id': part.group.id if part.group else None,
                'volume': float(part.volume) if part.volume else None,
                'material_cost': float(part.material_cost) if part.material_cost else None
            }
            
            # Handle STL file
            if part.stl_file:
                stl_path = os.path.join(stl_dir, f"{part.name}.stl")
                with default_storage.open(part.stl_file.name, 'rb') as source_file:
                    with open(stl_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                part_data['stl_file'] = f"stl_files/{part.name}.stl"
            
            # Handle thumbnail
            if part.thumbnail:
                thumbnail_path = os.path.join(thumbnail_dir, f"{part.name}.jpg")
                with default_storage.open(part.thumbnail.name, 'rb') as source_file:
                    with open(thumbnail_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                part_data['thumbnail'] = f"thumbnails/{part.name}.jpg"
            
            project_data['parts'].append(part_data)
        
        # Export purchased parts
        for part in project.purchased_parts.all():
            part_data = {
                'id': part.id,
                'name': part.name,
                'price': float(part.price),
                'quantity': part.quantity,
                'link': part.link,
                'status': part.status
            }
            project_data['purchased_parts'].append(part_data)
        
        # Export instructions
        for instruction in project.instructions.all().order_by('order'):
            instruction_data = {
                'id': instruction.id,
                'description': instruction.description,
                'order': instruction.order
            }
            
            # Handle instruction image
            if instruction.image:
                image_path = os.path.join(instructions_dir, f"step_{instruction.order}.jpg")
                with default_storage.open(instruction.image.name, 'rb') as source_file:
                    with open(image_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                instruction_data['image'] = f"instructions/step_{instruction.order}.jpg"
            
            project_data['instructions'].append(instruction_data)
        
        # Export project images
        for image in project.images.all():
            image_data = {
                'id': image.id,
                'uploaded_at': image.uploaded_at.isoformat()
            }
            
            # Handle project image
            if image.image:
                image_path = os.path.join(project_images_dir, f"project_image_{image.id}.jpg")
                with default_storage.open(image.image.name, 'rb') as source_file:
                    with open(image_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                image_data['image'] = f"project_images/project_image_{image.id}.jpg"
            
            project_data['project_images'].append(image_data)
        
        # Create manifest file
        manifest_path = os.path.join(temp_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(project_data, f, indent=2)
        
        # Create zip file
        zip_path = os.path.join(temp_dir, f"{project.name}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file != f"{project.name}.zip":  # Don't include the zip file itself
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
        
        # Serve the zip file
        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{project.name}.zip"'
            return response

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('projects:index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def delete_part(request, part_id):
    if request.method == 'POST':
        try:
            part = get_object_or_404(Part, id=part_id)
            part.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def import_project(request):
    if request.method == 'POST':
        try:
            # Get the uploaded zip file
            zip_file = request.FILES.get('zip_file')
            if not zip_file:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No file was uploaded'
                }, status=400)

            # Create a temporary directory to extract files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract the zip file
                with zipfile.ZipFile(zip_file) as z:
                    z.extractall(temp_dir)

                # Read the manifest file
                manifest_path = os.path.join(temp_dir, 'manifest.json')
                if not os.path.exists(manifest_path):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No manifest.json file found in the zip'
                    }, status=400)

                with open(manifest_path) as f:
                    project_data = json.load(f)

                # Create the project
                project = Project.objects.create(
                    name=project_data['metadata']['name'],
                    description=project_data['metadata']['description'],
                    user=request.user,
                    designer_id=project_data['metadata']['designer_id']
                )

                # Create or get materials
                materials = {}
                for material_data in project_data['materials']:
                    # Try to get existing material by name
                    existing_material = Material.objects.filter(name=material_data['name']).first()
                    if existing_material:
                        materials[material_data['id']] = existing_material
                    else:
                        # Create new material
                        material = Material.objects.create(
                            name=material_data['name'],
                            type=material_data['type'],
                            description=material_data['description'],
                            density=material_data['density'],
                            color=material_data['color'],
                            is_active=material_data['is_active'],
                            brand=material_data['brand'],
                            link=material_data['link'],
                            cost=material_data['cost'],
                            weight=material_data['weight']
                        )
                        materials[material_data['id']] = material

                # Create groups
                groups = {}
                for group_data in project_data['groups']:
                    group = Group.objects.create(
                        name=group_data['name'],
                        project=project
                    )
                    groups[group_data['id']] = group

                # Create parts
                for part_data in project_data['parts']:
                    part = Part.objects.create(
                        project=project,
                        name=part_data['name'],
                        quantity=part_data['quantity'],
                        material=materials.get(part_data['material_id']),
                        color=part_data['color'],
                        completed=part_data['completed'],
                        group=groups.get(part_data['group_id']),
                        volume=part_data['volume']
                    )

                    # Handle STL file
                    if part_data.get('stl_file'):
                        stl_path = os.path.join(temp_dir, part_data['stl_file'])
                        if os.path.exists(stl_path):
                            with open(stl_path, 'rb') as f:
                                part.stl_file.save(os.path.basename(stl_path), File(f), save=True)

                    # Handle thumbnail
                    if part_data.get('thumbnail'):
                        thumbnail_path = os.path.join(temp_dir, part_data['thumbnail'])
                        if os.path.exists(thumbnail_path):
                            with open(thumbnail_path, 'rb') as f:
                                part.thumbnail.save(os.path.basename(thumbnail_path), File(f), save=True)

                # Create purchased parts
                for part_data in project_data['purchased_parts']:
                    PurchasedPart.objects.create(
                        project=project,
                        name=part_data['name'],
                        price=part_data['price'],
                        quantity=part_data['quantity'],
                        link=part_data['link'],
                        status=part_data['status']
                    )

                # Create instructions
                for instruction_data in project_data['instructions']:
                    instruction = Instructions.objects.create(
                        project=project,
                        description=instruction_data['description'],
                        order=instruction_data['order']
                    )

                    # Handle instruction image
                    if instruction_data.get('image'):
                        image_path = os.path.join(temp_dir, instruction_data['image'])
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as f:
                                instruction.image.save(os.path.basename(image_path), File(f), save=True)

                # Create project images
                for image_data in project_data['project_images']:
                    image = ProjectImage.objects.create(
                        project=project,
                        uploaded_at=datetime.fromisoformat(image_data['uploaded_at'])
                    )

                    # Handle project image
                    if image_data.get('image'):
                        image_path = os.path.join(temp_dir, image_data['image'])
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as f:
                                image.image.save(os.path.basename(image_path), File(f), save=True)

                messages.success(request, 'Project imported successfully!')
                return redirect('projects:project_detail', pk=project.id)

        except Exception as e:
            messages.error(request, f'Error importing project: {str(e)}')
            return redirect('projects:index')

    return render(request, 'projects/import_project.html')
