import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "coppeliaBridge"
author = "trist"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

templates_path = ["_templates"]
exclude_patterns = ["build"]

html_theme = "alabaster"
html_static_path = []

autodoc_typehints = "description"
python_use_unqualified_type_names = True
