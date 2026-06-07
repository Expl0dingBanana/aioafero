.. _contributing:

Contributing
============

1. Fork and clone the repo.
2. Install Python **3.12+** (CI tests 3.12–3.14).
3. ``uv sync --extra test``
4. Before opening a PR, run the checklist below (details in :doc:`testing`).

Pull request checklist
----------------------

.. code-block:: bash

   uv run tox -e lint
   uv run tox run-parallel -p auto -o --skip-env lint
   uv run tox -e docs   # if you changed docs/ or public API

Bugs and features: `GitHub Issues <https://github.com/Expl0dingBanana/aioafero/issues>`_.

Code layout
-----------

* ``src/aioafero/`` — library
* ``src/aioafero/v1/`` — bridge, auth, controllers, models
* ``tests/`` — pytest (mirrors ``src/``)

New API or protocol behavior belongs here, not in downstream integrations. Wrap changes
in `Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_ after
they land in aioafero.

To capture live API traffic from client apps, see :doc:`mitm/index`.

Documentation
-------------

Published at https://aioafero.readthedocs.io/

* ``docs/user/`` — library guides (hand-written)
* ``docs/mitm/`` — MITM capture setup
* ``docs/api/`` — generated from source; do not edit
* ``CHANGELOG.rst`` — user-visible changes at the repo root

New page: add the ``.rst`` file and link it from ``docs/index.rst``. Update docs in the
same PR when the public API changes. Breaking changes need a changelog entry. Mermaid
diagrams need the ``docs`` extra.

.. code-block:: bash

   uv run tox -e docs

Faster local preview (warnings fail the build):

.. code-block:: bash

   uv sync --extra docs
   uv run sphinx-build -W -b html docs docs/_build/html

Output: ``docs/_build/html/``. CI matrix and other tox envs: :doc:`testing`.
