.. _contributing:

Contributing
============

Thanks for contributing to aioafero.

Getting started
---------------

1. Fork and clone the repository.
2. Install Python **3.12+** (3.12, 3.13, and 3.14 are tested in CI).
3. Sync dev dependencies:

   .. code-block:: bash

      uv sync --extra test

4. Run lint and tests before opening a PR — see :doc:`testing`.

Pull request checklist
----------------------

.. code-block:: bash

   uv run tox -e lint
   uv run tox run-parallel -p auto -o --skip-env lint

Report bugs and feature requests on
`GitHub Issues <https://github.com/Expl0dingBanana/aioafero/issues>`_.

Code layout
-----------

* ``src/aioafero/`` — library source
* ``src/aioafero/v1/`` — v1 API bridge, auth, controllers, models
* ``tests/`` — pytest suite (mirrors ``src/`` layout)

Device and protocol logic belongs in **aioafero**, not downstream Home Assistant
integrations. Add new API behavior here first, then wrap it in
`Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_.

Documentation
-------------

User guide and API docs live in ``docs/``. Build locally:

.. code-block:: bash

   uv sync --extra docs
   uv run tox -e docs

Hosted docs are published on `Read the Docs <https://aioafero.readthedocs.io/>`_.
The **Publish** workflow triggers an RTD build after CI passes (same gate as PyPI);
pushes and PRs only run ``tox -e docs`` as a build check.

One-time RTD setup:

1. Import the GitHub repo on `readthedocs.org <https://readthedocs.org/>`_ with project
   slug ``aioafero`` (matches ``.readthedocs.yaml`` and the Publish workflow).
2. Click **This file exists** when prompted for ``.readthedocs.yaml``.
3. Create an API token at `readthedocs.org/account/tokens/
   <https://readthedocs.org/account/tokens/>`_ and add it as ``READTHEDOCS_TOKEN`` in
   the GitHub repo secrets.
4. Disable automatic builds on push so only Publish deploys docs: in GitHub **Settings
   → Webhooks**, edit the Read the Docs hook and uncheck **Push** (leave the
   integration connected so RTD can pull source when the API build runs).
