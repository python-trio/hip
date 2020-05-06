# -*- coding: utf-8 -*-
from datetime import date
import os
import sys

import alabaster

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, root_path)

import hip


# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "alabaster",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
]

# Test code blocks only when explicitly specified
doctest_test_doctest_blocks = ""

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "Hip"
release = version = hip.__version__
author = hip.__author__
copyright = "{year}, {author}".format(year=date.today().year, author=author)

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "alabaster"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "description": "Hip is a new Python HTTP client for everybody",
    "github_user": "python-trio",
    "github_repo": "hip",
    "github_button": False,
    "github_banner": True,
    "travis_button": True,
    "show_powered_by": False,
    "font_family": "'Roboto', Georgia, sans",
    "head_font_family": "'Roboto', Georgia, serif",
    "code_font_family": "'Roboto Mono', 'Consolas', monospace",
}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = [alabaster.get_path()]

# Custom sidebar templates, maps document names to template names.
html_sidebars = {
    "**": [
        "about.html",
        "navigation.html",
        "relations.html",
        "searchbox.html",
        "donate.html",
    ]
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.8", None),
}
