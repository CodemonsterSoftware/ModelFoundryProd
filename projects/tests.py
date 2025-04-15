from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Project, Part, Group, PurchasedPart, Material, Designer, Instructions, ProjectImage
import json
import os
import tempfile
import zipfile
from decimal import Decimal
from django.core.files import File
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

class ViewTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create test designer
        self.designer = Designer.objects.create(
            name='Test Designer',
            mmf_url='https://mmf.com/test',
            patreon_url='https://patreon.com/test',
            cults3d_url='https://cults3d.com/test',
            website_url='https://test.com'
        )

        # Create test material
        self.material = Material.objects.create(
            name='Test Material',
            type='PLA',
            description='Test Description',
            density=Decimal('1.25'),
            color='#FF0000',
            is_active=True,
            weight=Decimal('1000.00'),
            cost=Decimal('25.00')
        )

        # Create test project
        self.project = Project.objects.create(
            name='Test Project',
            description='Test Description',
            user=self.user,
            designer=self.designer
        )

        # Create test group
        self.group = Group.objects.create(
            name='Test Group',
            project=self.project
        )

        # Create test part
        self.part = Part.objects.create(
            name='Test Part',
            quantity=1,
            material=self.material,
            project=self.project,
            group=self.group,
            volume=1000.0
        )

        # Create test purchased part
        self.purchased_part = PurchasedPart.objects.create(
            name='Test Purchased Part',
            price=Decimal('10.00'),
            quantity=1,
            project=self.project,
            status='pending'
        )

    def test_index_view(self):
        response = self.client.get(reverse('projects:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/index.html')
        self.assertIn('recent_projects', response.context)

    def test_project_list_view(self):
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_list.html')
        self.assertIn('projects', response.context)

    def test_project_detail_view(self):
        response = self.client.get(reverse('projects:project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_detail.html')
        self.assertIn('project', response.context)
        self.assertIn('parts', response.context)
        self.assertIn('purchased_parts', response.context)
        self.assertIn('groups', response.context)
        self.assertIn('materials', response.context)
        self.assertIn('material_colors', response.context)
        self.assertIn('instructions', response.context)

    def test_project_create_view(self):
        response = self.client.get(reverse('projects:project_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_form.html')
        self.assertIn('form', response.context)

        # Test POST request
        response = self.client.post(reverse('projects:project_create'), {
            'name': 'New Project',
            'description': 'New Description',
            'designer': self.designer.id
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name='New Project').exists())

    def test_project_update_view(self):
        response = self.client.get(reverse('projects:project_update', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_form.html')
        self.assertIn('form', response.context)

        # Test POST request
        response = self.client.post(reverse('projects:project_update', args=[self.project.id]), {
            'name': 'Updated Project',
            'description': 'Updated Description',
            'designer': self.designer.id
        })
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, 'Updated Project')

    def test_project_delete_view(self):
        response = self.client.get(reverse('projects:project_delete', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_confirm_delete.html')

        # Test POST request
        response = self.client.post(reverse('projects:project_delete', args=[self.project.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_add_part_view(self):
        # Create a temporary part form template
        template_content = """
        {% extends 'projects/base.html' %}
        {% block content %}
        <form method="post">
            {% csrf_token %}
            {{ form.as_p }}
            <button type="submit">Save</button>
        </form>
        {% endblock %}
        """
        with open('projects/templates/projects/part_form.html', 'w') as f:
            f.write(template_content)

        response = self.client.get(reverse('projects:add_part', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/part_form.html')
        self.assertIn('form', response.context)

        # Clean up the temporary template
        os.remove('projects/templates/projects/part_form.html')

    def test_update_part_completion_view(self):
        response = self.client.post(reverse('projects:update_part_completion', args=[self.part.id]), {
            'completed': 1
        })
        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.completed, 1)

    def test_update_part_group_view(self):
        new_group = Group.objects.create(
            name='New Group',
            project=self.project
        )
        response = self.client.post(reverse('projects:update_part_group', args=[self.part.id]), {
            'group_id': new_group.id
        })
        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.group, new_group)

    def test_add_group_view(self):
        response = self.client.post(reverse('projects:add_group', args=[self.project.id]), {
            'name': 'New Group'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Group.objects.filter(name='New Group').exists())

    def test_add_purchased_part_view(self):
        response = self.client.get(reverse('projects:add_purchased_part', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/purchased_part_form.html')
        self.assertIn('form', response.context)

        # Test POST request
        response = self.client.post(reverse('projects:add_purchased_part', args=[self.project.id]), {
            'name': 'New Purchased Part',
            'price': '15.00',
            'quantity': 2,
            'status': 'pending'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PurchasedPart.objects.filter(name='New Purchased Part').exists())

    def test_export_project_view(self):
        response = self.client.get(reverse('projects:export_project', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

    def test_import_project_view(self):
        # Create a temporary directory for the test zip file
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'test.zip')
            
            # Create the zip file
            with zipfile.ZipFile(zip_path, 'w') as zf:
                # Create manifest.json
                manifest = {
                    'metadata': {
                        'name': 'Imported Project',
                        'description': 'Imported Description',
                        'designer_id': self.designer.id
                    },
                    'materials': [{
                        'id': 1,
                        'name': 'Test Material',
                        'type': 'PLA',
                        'description': 'Test Description',
                        'density': 1.25,
                        'color': '#FF0000',
                        'is_active': True,
                        'weight': 1000.00,
                        'cost': 25.00
                    }],
                    'groups': [{
                        'id': 1,
                        'name': 'Test Group'
                    }],
                    'parts': [{
                        'name': 'Test Part',
                        'quantity': 1,
                        'material_id': 1,
                        'color': '#FF0000',
                        'completed': 0,
                        'group_id': 1,
                        'volume': 1000.0
                    }],
                    'purchased_parts': [{
                        'name': 'Test Purchased Part',
                        'price': 10.00,
                        'quantity': 1,
                        'link': '',
                        'status': 'pending'
                    }],
                    'instructions': [],
                    'project_images': []
                }
                zf.writestr('manifest.json', json.dumps(manifest))

            # Test POST request with zip file
            with open(zip_path, 'rb') as f:
                response = self.client.post(reverse('projects:import_project'), {
                    'zip_file': SimpleUploadedFile('test.zip', f.read())
                })
            self.assertEqual(response.status_code, 302)
            self.assertTrue(Project.objects.filter(name='Imported Project').exists())

    def test_register_view(self):
        response = self.client.get(reverse('projects:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIn('form', response.context)

        # Test POST request
        response = self.client.post(reverse('projects:register'), {
            'username': 'newuser',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_upload_project_images_view(self):
        # Create a test image file
        image = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'',
            content_type='image/jpeg'
        )

        # Test POST request
        response = self.client.post(reverse('projects:upload_project_images', args=[self.project.id]), {
            'image_0': image
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectImage.objects.filter(project=self.project).exists())

    def test_upload_instructions_view(self):
        # Create a test image file
        image = SimpleUploadedFile(
            name='test_instruction.jpg',
            content=b'',
            content_type='image/jpeg'
        )

        # Test POST request with both image and description
        response = self.client.post(reverse('projects:upload_instructions', args=[self.project.id]), {
            'description_format': 'step',
            'images': [image]  # Send as a list of images
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Instructions.objects.filter(project=self.project).exists())

    def test_delete_instruction_view(self):
        # Create a test instruction
        instruction = Instructions.objects.create(
            project=self.project,
            description='Test Instruction',
            order=1
        )

        # Test POST request
        response = self.client.post(reverse('projects:delete_instruction', args=[self.project.id]), {
            'instruction_id': instruction.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Instructions.objects.filter(id=instruction.id).exists())

    def test_part_details_view(self):
        response = self.client.get(reverse('projects:part_details', args=[self.part.id]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['name'], self.part.name)
        self.assertEqual(data['quantity'], self.part.quantity)
        self.assertEqual(data['material_id'], self.part.material.id)

    def test_update_part_view(self):
        response = self.client.post(reverse('projects:update_part', args=[self.part.id]), {
            'name': 'Updated Part',
            'quantity': 3,
            'material_id': self.material.id,
            'color': '#00FF00',
            'group': self.group.id
        })
        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.name, 'Updated Part')
        self.assertEqual(self.part.quantity, 3)

    def test_delete_part_view(self):
        response = self.client.post(reverse('projects:delete_part', args=[self.part.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Part.objects.filter(id=self.part.id).exists())

    def test_update_part_progress_view(self):
        # First update the part's quantity to allow for higher completion value
        self.part.quantity = 3
        self.part.save()
        
        response = self.client.post(reverse('projects:update_part_progress', args=[self.part.id]), {
            'completed': 2
        })
        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.completed, 2)

    def test_update_purchased_part_status_view(self):
        response = self.client.post(reverse('projects:update_purchased_part_status', args=[self.purchased_part.id]), {
            'status': 'ordered'
        })
        self.assertEqual(response.status_code, 200)
        self.purchased_part.refresh_from_db()
        self.assertEqual(self.purchased_part.status, 'ordered')

    def test_purchased_part_details_view(self):
        response = self.client.get(reverse('projects:purchased_part_details', args=[self.purchased_part.id]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['name'], self.purchased_part.name)
        self.assertEqual(float(data['price']), float(self.purchased_part.price))
        self.assertEqual(data['quantity'], self.purchased_part.quantity)

    def test_update_purchased_part_view(self):
        response = self.client.post(reverse('projects:update_purchased_part', args=[self.purchased_part.id]), {
            'name': 'Updated Purchased Part',
            'price': '20.00',
            'quantity': 3,
            'link': 'https://example.com',
            'status': 'ordered'
        })
        self.assertEqual(response.status_code, 200)
        self.purchased_part.refresh_from_db()
        self.assertEqual(self.purchased_part.name, 'Updated Purchased Part')
        self.assertEqual(self.purchased_part.price, Decimal('20.00'))
        self.assertEqual(self.purchased_part.quantity, 3)

    def test_delete_purchased_part_view(self):
        response = self.client.post(reverse('projects:delete_purchased_part', args=[self.purchased_part.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchasedPart.objects.filter(id=self.purchased_part.id).exists())

    def test_download_stl_view(self):
        # Create a test STL file
        stl_content = b'Test STL content'
        self.part.stl_file.save('test.stl', ContentFile(stl_content))
        
        response = self.client.get(reverse('projects:download_stl', args=[self.part.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/sla')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

class ModelTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create test designer
        self.designer = Designer.objects.create(
            name='Test Designer',
            mmf_url='https://mmf.com/test',
            patreon_url='https://patreon.com/test',
            cults3d_url='https://cults3d.com/test',
            website_url='https://test.com'
        )

        # Create test material
        self.material = Material.objects.create(
            name='Test Material',
            type='PLA',
            description='Test Description',
            density=Decimal('1.25'),
            color='#FF0000',
            is_active=True,
            weight=Decimal('1000.00'),
            cost=Decimal('25.00')
        )

        # Create test project
        self.project = Project.objects.create(
            name='Test Project',
            description='Test Description',
            user=self.user,
            designer=self.designer
        )

        # Create test group
        self.group = Group.objects.create(
            name='Test Group',
            project=self.project
        )

        # Create test part
        self.part = Part.objects.create(
            name='Test Part',
            quantity=2,
            material=self.material,
            project=self.project,
            group=self.group,
            volume=1000.0,
            completed=1
        )

        # Create test purchased part
        self.purchased_part = PurchasedPart.objects.create(
            name='Test Purchased Part',
            price=Decimal('10.00'),
            quantity=2,
            project=self.project,
            status='pending'
        )

    def test_project_total_parts(self):
        # Test total_parts property
        self.assertEqual(self.project.total_parts, 2)  # One part with quantity 2

    def test_project_material_counts(self):
        # Test material_counts property
        counts = self.project.material_counts
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts[self.material], 2)  # One part with quantity 2

    def test_project_total_cost(self):
        # Test total_cost property
        # Material cost: 1000mm³ * 1.25g/cm³ * $25/kg = $0.03125
        # Purchased part cost: $10 * 2 = $20
        # Total: $20.0625 (since we're using total quantity, not completed)
        expected_cost = 20.0625
        self.assertAlmostEqual(self.project.total_cost, expected_cost, places=4)

    def test_material_cost_per_kg(self):
        # Test cost_per_kg property
        # $25 for 1000g = $25/kg
        self.assertEqual(self.material.cost_per_kg, Decimal('25.00'))

    def test_material_total_used(self):
        # Test total_used property
        # Volume: 1000mm³ = 1cm³
        # Density: 1.25g/cm³
        # Quantity: 2
        # Completed: 1
        # Expected: 1cm³ * 1.25g/cm³ * 2 = 2.5g (since we're using total quantity, not completed)
        self.assertEqual(self.material.total_used, Decimal('2.500'))

    def test_part_material_cost(self):
        # Test material_cost property
        # Volume: 1000mm³ = 1cm³
        # Density: 1.25g/cm³
        # Cost: $25/kg
        # Expected: 1cm³ * 1.25g/cm³ * $25/kg = $0.03125
        self.assertAlmostEqual(self.part.material_cost, 0.03125, places=5)

    def test_part_calculate_volume(self):
        # Test calculate_volume method
        # Create a test STL file
        stl_content = b'Test STL content'
        self.part.stl_file.save('test.stl', ContentFile(stl_content))
        
        # The method returns 0 for invalid STL files
        self.assertEqual(self.part.calculate_volume(), 0)

    def test_instructions_str(self):
        # Test Instructions __str__ method
        instruction = Instructions.objects.create(
            project=self.project,
            description='Test Instruction',
            order=1
        )
        self.assertEqual(str(instruction), f"Step 1 - {self.project.name}")

    def test_designer_str(self):
        # Test Designer __str__ method
        self.assertEqual(str(self.designer), 'Test Designer')

    def test_group_str(self):
        # Test Group __str__ method
        self.assertEqual(str(self.group), 'Test Group')

    def test_part_str(self):
        # Test Part __str__ method
        self.assertEqual(str(self.part), 'Test Part')

    def test_purchased_part_str(self):
        # Test PurchasedPart __str__ method
        self.assertEqual(str(self.purchased_part), 'Test Purchased Part')

    def test_project_image_str(self):
        # Test ProjectImage __str__ method
        image = ProjectImage.objects.create(
            project=self.project,
            image=SimpleUploadedFile('test.jpg', b'')
        )
        self.assertEqual(str(image), f"Image for {self.project.name}")

    def test_material_str(self):
        # Test Material __str__ method
        self.assertEqual(str(self.material), f"{self.material.name} ({self.material.get_type_display()})")

    def test_project_str(self):
        # Test Project __str__ method
        self.assertEqual(str(self.project), 'Test Project')

    def test_material_ordering(self):
        # Test Material Meta ordering
        material2 = Material.objects.create(
            name='Another Material',
            type='ABS',
            description='Another Description',
            density=Decimal('1.05'),
            color='#00FF00',
            is_active=True,
            weight=Decimal('1000.00'),
            cost=Decimal('30.00')
        )
        materials = list(Material.objects.all())
        # Check that materials are ordered by name
        self.assertEqual(materials[0].name, 'Another Material')  # 'A' comes before 'T'
        self.assertEqual(materials[1].name, 'Test Material')

    def test_instructions_ordering(self):
        # Test Instructions Meta ordering
        instruction1 = Instructions.objects.create(
            project=self.project,
            description='First Instruction',
            order=2
        )
        instruction2 = Instructions.objects.create(
            project=self.project,
            description='Second Instruction',
            order=1
        )
        instructions = list(Instructions.objects.all())
        self.assertEqual(instructions[0], instruction2)  # Order 1 comes before Order 2

    def test_designer_ordering(self):
        # Test Designer Meta ordering
        designer2 = Designer.objects.create(
            name='Another Designer',
            mmf_url='https://mmf.com/another',
            patreon_url='https://patreon.com/another',
            cults3d_url='https://cults3d.com/another',
            website_url='https://another.com'
        )
        designers = list(Designer.objects.all())
        # Check that designers are ordered by name
        self.assertEqual(designers[0].name, 'Another Designer')  # 'A' comes before 'T'
        self.assertEqual(designers[1].name, 'Test Designer')
