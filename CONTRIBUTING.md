# Contributing

Thanks for contributing to aioafero.

-   **Documentation** — https://aioafero.readthedocs.io/
-   **Development, tox, coverage, and CI** — [docs/testing.rst](docs/testing.rst) (also on Read the Docs under _Contributing_)
-   **Issues** — [GitHub Issues](https://github.com/Expl0dingBanana/aioafero/issues)

Before opening a pull request:

```bash
uv sync --extra test
uv run tox -e lint
uv run tox run-parallel -p auto -o --skip-env lint
uv run tox -e docs
```
