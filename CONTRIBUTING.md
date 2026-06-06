# Contributing

Thanks for contributing to aioafero.

-   **Documentation** — https://aioafero.readthedocs.io/
-   **Contributing guide** — [docs/contributing.rst](docs/contributing.rst) (doc layout, when to update docs, preview workflows)
-   **Tests, tox, coverage, CI** — [docs/testing.rst](docs/testing.rst)
-   **Issues** — [GitHub Issues](https://github.com/Expl0dingBanana/aioafero/issues)

Before opening a pull request:

```bash
uv sync --extra test
uv run tox -e lint
uv run tox -e audit
uv run tox run-parallel -p auto -o --skip-env lint
uv run tox -e docs   # Sphinx; see docs/contributing.rst for layout and preview
```

User-guide and API docs live in `docs/`. To preview HTML locally without tox: `uv sync --extra docs` then `uv run sphinx-build -W -b html docs docs/_build/html`.
