# AI agent guide — aioafero

Async Python library for the Hubspace / Afero IoT cloud API (**8.0.0**). **Device and protocol logic belongs here**, not in downstream integrations (e.g. [Hubspace-Homeassistant](https://github.com/jdeath/Hubspace-Homeassistant)).

## Commands and quality gate

Run everything through **uv** (`uv sync --extra test` first). Prefer `uv run tox` over calling `pytest`, `ruff`, or `pre-commit` directly.

```bash
uv run tox -e lint          # pre-commit: ruff, bandit, format, codespell, yaml, …
uv run tox -e audit         # pip-audit on runtime deps
uv run tox run-parallel -p auto -o --skip-env lint   # py312–py314 + coverage (default before commit)
uv run tox -e py314 -- tests/v1/test_auth.py -q    # single env / subset
uv run tox -e docs          # when public API or docs/ changed
```

All of the above must pass before a PR: **lint**, **audit**, **tests** (3.12–3.14), **100% coverage** ([Codecov](https://app.codecov.io/gh/Expl0dingBanana/aioafero) fails below 100%), **docs** when applicable. Coverage targets `aioafero` (`--cov=aioafero`); verify with `uv run tox -e report`. Details: [docs/testing.rst](docs/testing.rst), [SECURITY.md](SECURITY.md).

## Linting

Rules live in `pyproject.toml` and `.pre-commit-config.yaml` — fix what `tox -e lint` reports. Match surrounding code. Library is **fully async** (`async def`, no blocking I/O; use `asyncio.timeout`, not `async_timeout`). Public code needs docstrings; tests are exempt. **`TC001`–`TC003` ignored in tests** — do not use `TYPE_CHECKING` imports in tests (breaks `pytest.patch()`).

## Architecture (8.0)

`AferoAuth` (login/OTP/refresh) → `AferoBridgeV1` (session, polling, controllers) → models (cached state) + `EventStream` (REST polls, in-process callbacks). Models are **read-only snapshots**; writes go through controller methods / `set_state`.

**Auth:** Bridge takes `username` + `refresh_token` (optional `token` / `token_expiration`), not a password. **`AferoAuth` and `AferoBridgeV1` require `aiohttp.ClientSession` at construction.** `for_login(session, user, password)` for credentials; runtime uses `AferoAuth(session, user, refresh_token, …)`. `AferoBridgeV1.open(...)` may create a session when omitted (only path without an upfront session). `bridge.close()` does **not** close a session you passed in.

```python
session = aiohttp.ClientSession()
token_data = await v1.AferoAuth.for_login(session, user, password).login()
bridge = v1.AferoBridgeV1(user, token_data.refresh_token, session)
await bridge.initialize()
await bridge.async_block_until_done()
await bridge.close()
await session.close()
```

More: [docs/user/auth.rst](docs/user/auth.rst), [docs/user/overview.rst](docs/user/overview.rst).

## Layout

`src/aioafero/v1/` — `__init__.py` (bridge), `auth.py`, `controllers/`, `models/`, `controllers/event.py` (polling). `tests/` mirrors `src/`. Cloud I/O via controllers — do not bypass `BaseResourcesController.set_state` / `update_afero_api`.

## Adding a device type

Follow an existing controller (e.g. fan, switch). Model in `v1/models/` → controller subclassing `BaseResourcesController` → register on `AferoBridgeV1` and type unions in `v1/__init__.py` → tests under `tests/v1/` using **`mocked_bridge`** / **`mocked_bridge_req`** (pass **`session`** — `aio_sess` async, `Mock()` sync) → `docs/user/` + `CHANGELOG.rst` + version bump in `pyproject.toml`. Split devices: [docs/user/device_splitting.rst](docs/user/device_splitting.rst).

## Further reading

[CHANGELOG.rst](CHANGELOG.rst) (8.0 breaks) · [README.rst](README.rst) · [docs/user/examples.rst](docs/user/examples.rst) · [docs/user/bridge.rst](docs/user/bridge.rst) · [docs/contributing.rst](docs/contributing.rst) · [CONTRIBUTING.md](CONTRIBUTING.md)
