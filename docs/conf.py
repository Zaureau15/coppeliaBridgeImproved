import os
import sys

sys.path.insert(0, os.path.abspath(".."))  # points to your project root

project: str = "CoppeliaBridge"
author = "Kevin Leahy, modified by Tristan Letourneau"

# ----------------------- General configuration ---------------------- #

extensions: list[str] = [
    "sphinx.ext.autodoc",  # pulls docstrings from your code
    "sphinx.ext.napoleon",  # supports Google/NumPy style docstrings
    "sphinx.ext.viewcode",  # adds "view source" links
    "sphinx_autodoc_typehints",  # renders type hints nicely
]

templates_path: list[str] = ["_templates"]
exclude_patterns: list[str] = []

# ------------------------ HTML output options ----------------------- #

html_theme: str = "alabaster"
html_static_path: list[str] = ["_static"]

autodoc_typehints = "description"  # Put type hints in parameter section
python_use_unqualified_type_names = True  # Hide module names for types
