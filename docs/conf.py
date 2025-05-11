import os
import sys
import django

# Point to the project's root directory
sys.path.insert(0, os.path.abspath('..')) 

# Set up Django environment
os.environ['DJANGO_SETTINGS_MODULE'] = 'ModelFoundry.settings'  # Replace 'ModelFoundry.settings' with your actual project settings
django.setup()

# -- Project information -----------------------------------------------------
project = 'ModelFoundry'  # Replace with your project's name
copyright = '2024, Your Name'  # Replace with your name/organization and current year
author = 'Your Name' # Replace with your name/organization

# The full version, including alpha/beta/rc tags
release = '0.1'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',      # Include documentation from docstrings
    'sphinx.ext.napoleon',     # Support for Google and NumPy style docstrings
    'sphinx.ext.intersphinx',  # Link to other projects' documentation
    'sphinx.ext.viewcode',     # Add links to source code
    'sphinx_rtd_theme',        # Read the Docs theme
]

# Intersphinx mapping (example for Python and Django)
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'django': ('https://docs.djangoproject.com/en/stable/', 'https://docs.djangoproject.com/en/stable/_objects/'),
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# If you have a logo, uncomment and set the path
# html_logo = "_static/logo.png"

# -- Options for autodoc -----------------------------------------------------
autodoc_member_order = 'bysource'
# Ensure that the __init__ method is documented
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# Napoleon settings (if you use Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True 