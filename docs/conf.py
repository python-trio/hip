#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import datetime

sys.path.insert(0, os.path.abspath("../.."))

import hip

# Warn about all references to unknown targets
nitpicky = False  # TODO: Switch this to 'True' after interface has solidified.
nitpick_ignore = []
autodoc_inherit_docstrings = False
default_role = "obj"

# XX hack the RTD theme until
#   https://github.com/rtfd/sphinx_rtd_theme/pull/382
# is shipped (should be in the release after 0.2.4)
# ...note that this has since grown to contain a bunch of other CSS hacks too
# though.


def setup(app):
    app.add_css_file("hackrtd.css")


# -- General configuration ------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinxcontrib_trio",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autodoc_member_order = "bysource"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "Hip"
author = hip.__author__
copyright = "%d, %s" % (datetime.date.today().year, author)
version = hip.__version__
release = version

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "default"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

# We have to set this ourselves, not only because it's useful for local
# testing, but also because if we don't then RTD will throw away our
# html_theme_options.
import sphinx_rtd_theme

html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    # default is 2
    # show deeper nesting in the RTD theme's sidebar TOC
    # https://stackoverflow.com/questions/27669376/
    # I'm not 100% sure this actually does anything with our current
    # versions/settings...
    "navigation_depth": 4,
    "logo_only": True,
    "prev_next_buttons_location": "both",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "Hipdoc"


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, "Hip.tex", "Hip Documentation", author, "manual"),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "hip", "Hip Documentation", [author], 1)]


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "Hip",
        "Hip Documentation",
        author,
        "Hip",
        "One line description of project.",
        "Miscellaneous",
    ),
]
