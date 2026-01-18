"""
Tests for Forge app - 3D File Tools
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import json
import tempfile
from pathlib import Path


class ForgeViewTests(TestCase):
    """Test Forge page views."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_forge_index_view(self):
        """Test forge index page loads."""
        response = self.client.get(reverse('forge:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'forge/index.html')
    
    def test_forge_convert_view(self):
        """Test convert page loads."""
        response = self.client.get(reverse('forge:convert'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'forge/convert.html')
    
    def test_forge_slice_view(self):
        """Test slice page loads."""
        response = self.client.get(reverse('forge:slice'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'forge/slice.html')
    
    def test_requires_login(self):
        """Test that forge pages require login."""
        self.client.logout()
        response = self.client.get(reverse('forge:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class ForgeAPITests(TestCase):
    """Test Forge API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create a simple STL content (binary STL header + minimal data)
        # This is a minimal valid STL file structure
        self.stl_content = (
            b'solid test\n'
            b'facet normal 0 0 1\n'
            b'  outer loop\n'
            b'    vertex 0 0 0\n'
            b'    vertex 1 0 0\n'
            b'    vertex 0 1 0\n'
            b'  endloop\n'
            b'endfacet\n'
            b'endsolid test\n'
        )
    
    def test_api_slice_requires_post(self):
        """Test that slice API requires POST."""
        response = self.client.get(reverse('forge:api_slice'))
        self.assertEqual(response.status_code, 405)
    
    def test_api_convert_requires_post(self):
        """Test that convert API requires POST."""
        response = self.client.get(reverse('forge:api_convert'))
        self.assertEqual(response.status_code, 405)
    
    def test_api_slice_requires_file(self):
        """Test that slice API requires a file."""
        response = self.client.post(reverse('forge:api_slice'), {
            'grid_x': 2,
            'grid_y': 2,
            'grid_z': 1,
            'joint_type': 'none'
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
    
    def test_api_job_status_not_found(self):
        """Test job status for non-existent job."""
        response = self.client.get(reverse('forge:api_job_status', args=['nonexistent']))
        self.assertEqual(response.status_code, 404)
    
    def test_api_download_not_found(self):
        """Test download for non-existent job."""
        response = self.client.get(reverse('forge:api_download', args=['nonexistent']))
        self.assertEqual(response.status_code, 404)


class SlicerServiceTests(TestCase):
    """Test slicer service functions."""
    
    def test_import_slicer(self):
        """Test that slicer module can be imported."""
        try:
            from forge.services import slicer
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Slicer dependencies not installed: {e}")


class JointsServiceTests(TestCase):
    """Test joints service functions."""
    
    def test_import_joints(self):
        """Test that joints module can be imported."""
        try:
            from forge.services import joints
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Joints dependencies not installed: {e}")


class ConverterServiceTests(TestCase):
    """Test converter service functions."""
    
    def test_import_converter(self):
        """Test that converter module can be imported."""
        from forge.services import converter
        self.assertTrue(True)
    
    def test_pythonocc_detection(self):
        """Test pythonocc availability detection."""
        from forge.services.converter import PYTHONOCC_AVAILABLE
        # Just verify the flag is set correctly (True or False)
        self.assertIsInstance(PYTHONOCC_AVAILABLE, bool)
