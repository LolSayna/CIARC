"""Sphinx configuration."""

import os.path
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "CIARC"
author = "Riftonauts"
copyright = "2024, Riftonauts"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
