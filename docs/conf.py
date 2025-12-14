# docs/conf.py
"""
Sphinx configuration for Contacts API documentation.

This file configures Sphinx to generate API documentation using:
- autodoc: Extract documentation from Python docstrings
- napoleon: Support for Google and NumPy style docstrings
- autosummary: Generate summary tables automatically
- viewcode: Link to highlighted source code
"""

import os
import sys

# Add the project root to the path for autodoc
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------

project = "Contacts API"
copyright = "2024, Developer"
author = "Developer"
release = "2.1.0"
version = "2.1"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# Autosummary configuration
autosummary_generate = True
autosummary_imported_members = True

# Autodoc configuration
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

autodoc_typehints = "description"
autodoc_class_signature = "separated"

# Napoleon settings (for Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

# Intersphinx mapping to other documentation
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

html_theme = "alabaster"
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    "description": "REST API for managing contacts with FastAPI",
    "github_user": "developer",
    "github_repo": "contacts-api",
    "fixed_sidebar": True,
    "show_powered_by": False,
}

# -- Options for autodoc -----------------------------------------------------

# Mock imports for modules that might not be available
autodoc_mock_imports = [
    "cloudinary",
    "redis",
    "slowapi",
    "fastapi_mail",
]

