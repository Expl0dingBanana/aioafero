.. _testing:

Testing and CI
==============

How to run tests locally and how GitHub Actions is wired.

Quick start (local)
-------------------

1. **Clone** the repo and install **Python 3.12, 3.13, and 3.14** (see
   ``requires-python`` and tox envs).

2. **Install dev dependencies with uv:**

   .. code-block:: bash

      uv sync --extra test

3. **Lint:**

   .. code-block:: bash

      uv run tox -e lint

4. **One Python version:**

   .. code-block:: bash

      uv run tox -e py314

   Bare ``uv run pytest`` uses ``pyproject.toml`` addopts and prints **term-missing**
   coverage.

5. **All supported versions + combined coverage (optional):**

   .. code-block:: bash

      uv run tox -e coverage

6. **Parallel matrix (before commit):**

   .. code-block:: bash

      uv run tox run-parallel -p auto -o --skip-env lint

   Runs ``py312``, ``py313``, and ``py314`` concurrently, then ``report`` (depends) to
   combine coverage. Use ``-o`` for live output.

**Subset of tests:** ``uv run tox -e py314 -- tests/v1/test_auth.py -q``

Documentation
-------------

.. code-block:: bash

   uv sync --extra docs
   uv run tox -e docs

Build fails on Sphinx warnings (``-W``).

Tox environments
----------------

.. list-table::
   :header-rows: 1

   * - Env
     - Purpose
   * - ``lint``
     - pre-commit on all files
   * - ``docs``
     - Sphinx HTML build (warnings as errors)
   * - ``default``
     - pytest on current interpreter
   * - ``py312`` / ``py313`` / ``py314``
     - pytest + coverage data in ``.coverage.{envname}``
   * - ``report``
     - ``coverage combine``, terminal report, ``coverage.xml``
   * - ``coverage``
     - Depends on ``report``; convenience meta-env
   * - ``build`` / ``clean`` / ``publish``
     - Packaging (release workflow)

Python versions are defined once in ``[testenv:py3{12,13,14}]``; tox picks the
interpreter from the env name (no per-env ``basepython`` blocks).

Coverage behavior
-----------------

* **Local pytest** — ``addopts = "--cov --cov-report=term-missing"`` in ``pyproject.toml``.
* **Tox py envs** — replace addopts with ``--cov --cov-report=`` so each version
  collects silently; ``report`` prints the combined result once.
* **Why replace, not append?** pytest-cov treats ``--cov-report`` as multi-allowed;
  appending ``--cov-report=`` does not cancel ``term-missing`` from config.

GitHub Actions
--------------

Workflows:

* ``.github/workflows/cicd.yaml`` — lint, docs, test matrix (3.12–3.14), combined
  coverage, Codecov (on push/PR to ``main``).
* ``.github/workflows/reusable-ci.yaml`` — shared jobs; inputs for Python versions and
  ``run-codecov``.
* ``.github/workflows/release.yaml`` — runs CI then ``tox -e build`` and PyPI publish,
  and triggers a Read the Docs build (default branch only; requires
  ``READTHEDOCS_TOKEN``).

CI test step mirrors tox py envs: ``COVERAGE_FILE=.coverage.py312``, pytest with
``-o addopts="--cov --cov-report="``, JUnit XML per version. Coverage artifacts use
``include-hidden-files: true`` because ``.coverage.*`` files are dotfiles excluded by
``upload-artifact@v4`` by default.

Maintenance
-----------

* **Add a Python version** — extend ``[testenv:py3{12,13,14}]`` factor in ``tox.ini``,
  update ``python-versions`` default in ``reusable-ci.yaml``, install the interpreter
  locally, bump classifiers in ``pyproject.toml``.
* **Dependabot** — ``.github/dependabot.yml`` (GitHub Actions, pip, pre-commit).
