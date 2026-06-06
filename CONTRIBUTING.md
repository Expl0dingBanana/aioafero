# Contributing

-   [Contributing guide](docs/contributing.rst) — layout, when to update docs, preview
-   [MITM capture setup](docs/mitm/index.rst)
-   [Testing & CI](docs/testing.rst)
-   [Docs site](https://aioafero.readthedocs.io/)
-   [Issues](https://github.com/Expl0dingBanana/aioafero/issues)

```bash
uv sync --extra test
uv run tox -e lint
uv run tox -e audit
uv run tox run-parallel -p auto -o --skip-env lint
uv run tox -e docs   # if you touched docs/ or public API
```
