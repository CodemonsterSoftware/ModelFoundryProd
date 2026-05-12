"""
Tests for Forge app — module framework and service logic.

Note: Service tests import directly from the module tree now that
slicer.py / rune_etcher.py / converter.py live inside their respective
module directories rather than forge/services/.
"""
import sys
from pathlib import Path
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
import json
from django.conf import settings

# Add project root so paths resolve correctly in tests
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class ForgeViewTests(TestCase):
    """Test Forge framework views."""

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

    def test_requires_login(self):
        """Test that forge pages require login."""
        self.client.logout()
        response = self.client.get(reverse('forge:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_module_view_not_found(self):
        """Test that an unknown module_id returns 404."""
        response = self.client.get(
            reverse('forge:module_view', kwargs={'module_id': 'nonexistent_xyz'})
        )
        self.assertEqual(response.status_code, 404)

    def test_api_job_status_not_found(self):
        """Test job status for non-existent job returns 404."""
        response = self.client.get(
            reverse('forge:api_job_status', args=['nonexistent-job-id'])
        )
        self.assertEqual(response.status_code, 404)

    def test_api_download_not_found(self):
        """Test download endpoint for non-existent job returns 404."""
        response = self.client.get(
            reverse('forge:api_download', args=['nonexistent-job-id'])
        )
        self.assertEqual(response.status_code, 404)

    def test_api_module_run_requires_post(self):
        """Test that the generic module run endpoint only accepts POST."""
        response = self.client.get(
            reverse('forge:api_module_run', kwargs={'module_id': 'grid_slicer'})
        )
        self.assertEqual(response.status_code, 405)


class SlicerModuleServiceTests(TestCase):
    """Test grid_slicer module's bundled slicer service."""

    MODULE_DIR = Path(__file__).parent / 'modules' / 'grid_slicer'

    def setUp(self):
        if str(self.MODULE_DIR) not in sys.path:
            sys.path.insert(0, str(self.MODULE_DIR))

    def test_import_slicer(self):
        """Slicer service should be importable from the module directory."""
        try:
            import slicer  # noqa: F401
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Slicer dependencies not installed: {e}")

    def test_import_joints(self):
        """Joints helper should be importable from the grid_slicer module directory."""
        try:
            import joints  # noqa: F401
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Joints dependencies not installed: {e}")


class EtcherModuleServiceTests(TestCase):
    """Test rune_etcher module's bundled service."""

    MODULE_DIR = Path(__file__).parent / 'modules' / 'rune_etcher'

    def setUp(self):
        if str(self.MODULE_DIR) not in sys.path:
            sys.path.insert(0, str(self.MODULE_DIR))

    def test_import_rune_etcher(self):
        """RuneEtcher service should be importable from the module directory."""
        try:
            from rune_etcher import RuneEtcher  # noqa: F401
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Rune etcher dependencies not installed: {e}")


class ConverterModuleServiceTests(TestCase):
    """Test converter module's bundled service."""

    MODULE_DIR = Path(__file__).parent / 'modules' / 'converter'

    def setUp(self):
        if str(self.MODULE_DIR) not in sys.path:
            sys.path.insert(0, str(self.MODULE_DIR))

    def test_import_converter(self):
        """Converter service should be importable from the module directory."""
        try:
            from converter import convert_stl_to_step  # noqa: F401
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Converter dependencies not installed: {e}")

    def test_pythonocc_detection(self):
        """PYTHONOCC_AVAILABLE flag should be a bool (True if installed, False if not)."""
        try:
            from converter import PYTHONOCC_AVAILABLE
            self.assertIsInstance(PYTHONOCC_AVAILABLE, bool)
        except ImportError as e:
            self.skipTest(f"Converter dependencies not installed: {e}")


class ForgeModuleE2ETests(TestCase):
    """End-to-End tests for module execution pipelines."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_grid_slicer_e2e_pipeline(self):
        """
        Test the full pipeline of uploading an STL and processing it through grid_slicer.
        This hits the Django views, creates the job struct, executes the subprocess,
        and parses the return payload.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from forge.module_registry import registry
        
        # Check if grid_slicer is available
        try:
            module = registry.get_module('grid_slicer')
        except KeyError:
            self.skipTest("grid_slicer module not registered")
            
        # Check if module has a venv or can be run
        module_dir = Path(settings.BASE_DIR) / 'forge' / 'modules' / 'grid_slicer'
        if not (module_dir / 'main.py').exists():
            self.skipTest("grid_slicer main.py not found")

        # Create a simple valid ASCII STL
        stl_content = b"solid cube\n  facet normal 0 0 -1\n    outer loop\n      vertex 0 0 0\n      vertex 1 1 0\n      vertex 1 0 0\n    endloop\n  endfacet\nendsolid\n"
        test_file = SimpleUploadedFile(
            "test_cube.stl",
            stl_content,
            content_type="model/stl"
        )
        
        url = reverse('forge:api_module_run', kwargs={'module_id': 'grid_slicer'})
        
        response = self.client.post(url, {
            'input_file': test_file,
            'grid_x': '1',
            'grid_y': '1',
            'grid_z': '1',
            'slice_mode': 'uniform'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # If the backend failed due to missing dependencies in its venv, we gracefully accept that 
        # as the pipeline framework itself worked.
        if not data.get('success'):
            if 'No module named' in data.get('message', '') or 'Blender not found' in data.get('message', ''):
                self.skipTest(f"Module backend dependencies missing: {data.get('message')}")
            else:
                self.fail(f"Pipeline executed but failed: {data.get('message')}")
                
        self.assertEqual(data.get('status'), 'completed')
        self.assertIn('job_id', data)
        self.assertIn('payload', data)
