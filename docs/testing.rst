.. _testing:

Testing and CI
==============

Quick start (local)
-------------------

1. Install **Python 3.12+** and sync dev dependencies:

   .. code-block:: bash

      uv sync --extra test

2. **Lint** (ruff, bandit, format, …):

   .. code-block:: bash

      uv run tox -e lint

3. **Dependency audit:**

   .. code-block:: bash

      uv run tox -e audit

4. **One Python version:**

   .. code-block:: bash

      uv run tox -e default

   Uses your current Python (3.12+). Bare ``uv run pytest`` uses ``pyproject.toml``
   addopts and prints coverage.

5. **Full matrix** (before commit):

   .. code-block:: bash

      uv run tox run-parallel -p auto -o --skip-env lint

   Runs ``py312``, ``py313``, and ``py314`` concurrently, then combines coverage.

**Subset of tests:** ``uv run tox -e default -- tests/v1/test_auth.py -q``

Documentation
-------------

.. code-block:: bash

   uv run tox -e docs

Run when you change ``docs/`` or public API docstrings. Layout, new pages, and a faster
preview loop: :doc:`contributing`.

Tox environments
----------------

.. list-table::
   :header-rows: 1

   * - Env
     - Purpose
   * - ``lint``
     - pre-commit on all files (includes **bandit** on ``src/``)
   * - ``audit``
     - **pip-audit** on installed runtime dependencies
   * - ``docs``
     - Sphinx HTML build (warnings as errors)
   * - ``default``
     - pytest on current interpreter
   * - ``py312`` / ``py313`` / ``py314``
     - pytest + per-env coverage data
   * - ``report`` / ``coverage``
     - combine coverage and print report
   * - ``build`` / ``clean`` / ``publish``
     - Packaging (release workflow)

Python versions are defined once in ``[testenv:py3{12,13,14}]``; tox picks the
interpreter from the env name (no per-env ``basepython`` blocks).

Coverage
--------

Bare ``pytest`` prints per-file coverage. Tox py envs collect silently and ``report``
combines the matrix — see ``pyproject.toml`` and ``tox.ini``.

GitHub Actions
--------------

* ``.github/workflows/cicd.yaml`` — lint, audit, docs, test matrix (3.12–3.14), combined
  coverage, Codecov (on push/PR/weekly schedule to ``main``).
* ``.github/workflows/codeql-analysis.yml`` — CodeQL static analysis (push/PR/weekly).
* ``.github/workflows/reusable-ci.yaml`` — shared jobs; inputs for Python versions and
  ``run-codecov``.
* ``.github/workflows/release.yaml`` — runs CI then ``tox -e build`` and PyPI publish
  (default branch only). Read the Docs builds separately via its GitHub webhook.

CI test step mirrors tox py envs: ``COVERAGE_FILE=.coverage.py312``, pytest with
``-o addopts="--cov=aioafero --cov-report="``, JUnit XML per version. Coverage artifacts use
``include-hidden-files: true`` because ``.coverage.*`` files are dotfiles excluded by
``upload-artifact@v4`` by default.

Maintenance
-----------

* **Add a Python version** — extend ``[testenv:py3{12,13,14}]`` factor in ``tox.ini``,
  update ``python-versions`` default in ``reusable-ci.yaml``, install the interpreter
  locally, bump classifiers in ``pyproject.toml``.
* **Dependabot** — ``.github/dependabot.yml`` (GitHub Actions, pip, pre-commit); enable
  **Dependabot alerts** and **security updates** in repo settings (see ``SECURITY.md``).

Security scanning
-----------------

Bandit (``tox -e lint``), pip-audit (``tox -e audit``), CodeQL, and Dependabot — see
``SECURITY.md``.
