"""Sphinx configuration for aioafero."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from datetime import UTC, datetime

__location__ = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(__location__, "../src"))

# -- Run sphinx-apidoc -------------------------------------------------------
# Regenerate API stubs on each build (RTD does not run apidoc separately).

try:
    from sphinx.ext import apidoc
except ImportError:
    from sphinx import apidoc

output_dir = os.path.join(__location__, "api")
module_dir = os.path.join(__location__, "../src/aioafero")
with contextlib.suppress(FileNotFoundError):
    shutil.rmtree(output_dir)

try:
    import sphinx

    cmd_line = f"sphinx-apidoc --implicit-namespaces -f -o {output_dir} {module_dir}"
    args = cmd_line.split(" ")
    if tuple(sphinx.__version__.split(".")) >= ("1", "7"):
        args = args[1:]
    apidoc.main(args)
except Exception as exc:  # pragma: no cover - doc build only
    print(f"Running `sphinx-apidoc` failed!\n{exc}")

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"

project = "aioafero"
copyright = f"2024-{datetime.now(tz=UTC).year}, Chris Dohmen"
author = "Chris Dohmen"

try:
    from aioafero import __version__ as version
except ImportError:
    version = ""

if not version or version.lower() == "unknown":
    version = os.getenv("READTHEDOCS_VERSION", "unknown")

release = version

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", ".venv"]

suppress_warnings = [
    "ref.python",  # type aliases and re-exports create ambiguous cross-refs in apidoc
]

pygments_style = "sphinx"
todo_emit_warnings = True

# -- Autodoc -----------------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "show-inheritance": True,
}
autodoc_typehints = "both"
autodoc_typehints_description_target = "all"
autodoc_typehints_format = "short"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_special_with_doc = True

# Hide internal lifecycle helpers on controller pages (user guide autodoc).
_CONTROLLER_SKIP_METHODS = frozenset(
    {
        "emit_to_subscribers",
        "generate_update_dev",
        "get_filtered_devices",
        "initialize",
        "initialize_elem",
        "initialize_number",
        "initialize_select",
        "initialize_sensor",
        "split_sensor_data",
        "update",
        "update_afero_api",
        "update_elem",
        "update_number",
        "update_select",
        "update_sensor",
    }
)


def _autodoc_skip_member(app, what, name, obj, skip, options):
    if what != "method" or name not in _CONTROLLER_SKIP_METHODS:
        return skip
    module = getattr(obj, "__module__", "") or ""
    if module.startswith("aioafero.v1.controllers."):
        return True
    return skip


def setup(app):
    """Register Sphinx extension hooks."""
    app.connect("autodoc-skip-member", _autodoc_skip_member)


# -- HTML --------------------------------------------------------------------

html_theme = "furo"
html_title = "aioafero documentation"
html_baseurl = os.getenv("READTHEDOCS_CANONICAL_URL", "")
html_static_path = ["_static"]
html_copybutton_exclude = ".linenos, .gp"

html_theme_options = {
    "source_repository": "https://github.com/Expl0dingBanana/aioafero",
    "source_branch": "main",
    "source_directory": "docs/",
    "navigation_with_keys": True,
    "top_of_page_buttons": ["view", "edit"],
}

# -- Intersphinx -------------------------------------------------------------

python_version = ".".join(map(str, sys.version_info[0:2]))
intersphinx_mapping = {
    "python": (f"https://docs.python.org/{python_version}", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable/", None),
}

print(f"loading configurations for {project} {version} ...", file=sys.stderr)
