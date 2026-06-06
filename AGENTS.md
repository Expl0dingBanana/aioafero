# AI agent guide — aioafero

Async Python library for the Hubspace / Afero IoT cloud API (currently **8.0.0**). Use this document when making changes here.

Downstream integrations (e.g. [Hubspace-Homeassistant](https://github.com/jdeath/Hubspace-Homeassistant)) install this from PyPI and wrap it for their platform. **Device and protocol logic belongs here**, not in those integrations.

## Commands

Run all development commands through **uv**. First-time setup (or after dependency changes):

```bash
uv sync --extra test
```

This installs tox, pytest, and other test tools. **Lint uses pre-commit via tox** — you do not need a separate `pre-commit install` for the standard workflow; `uv run tox -e lint` runs all hooks from `.pre-commit-config.yaml`.

```bash
uv run tox -e lint
uv run tox run-parallel -p auto -o --skip-env lint      # py312–py314 + combined coverage report
uv run tox -e py314                                     # single Python version
uv run tox -e py314 -- tests/v1/test_auth.py -q         # subset
uv run tox -e docs                                      # Sphinx (required when docs/API change)
uv run tox -av                                          # list tox environments
```

Run the **full test matrix in parallel** by default (`run-parallel -p auto -o`). Use a single env (`-e lint`, `-e py314`, …) only when targeting one environment; use sequential `uv run tox` without `run-parallel` only when explicitly asked.

Do not invoke `pytest`, `ruff`, or `pre-commit` directly unless you are debugging a single step. Prefer `uv run tox`.

See [docs/testing.rst](docs/testing.rst) for the full testing and CI guide.

## Linting

Lint rules live in `pyproject.toml` and `.pre-commit-config.yaml` — do not duplicate them here. Run `uv run tox -e lint` while iterating and fix what it reports.

When writing new code, match patterns in the file or module you are editing. In particular:

-   **Async** — ruff `ASYNC` rules apply; the library is fully async (see below).
-   **Docstrings** — new public modules, classes, and functions need docstrings (`D` rules); tests are exempt (`per-file-ignores` for `tests/**`).
-   **Pre-commit is not ruff-only** — also runs codespell, prettier, trailing-whitespace, and yaml checks.

Non-obvious exceptions:

-   **`TC001`–`TC003` are ignored** — do not move imports into `TYPE_CHECKING` blocks in tests; it breaks `pytest.patch()`.

## Dependencies

Runtime and dev dependencies are declared in **`pyproject.toml`**:

-   **Runtime** — `[project] dependencies` (`aiohttp`, `beautifulsoup4`, `securelogging`).
-   **Test** — `[project.optional-dependencies] test` (pytest, tox, aioresponses, …).
-   **Docs** — `[project.optional-dependencies] docs` (Sphinx, furo, mermaid).

Version is set in `[project] version` (currently `8.0.0`). Bump it and add a **`CHANGELOG.rst`** entry for user-visible changes.

## Architecture

```
Your code / integration
    → AferoAuth (login, OTP, token refresh)
    → AferoBridgeV1 (session, polling, controllers)
        → Controllers (lights, fans, thermostats, …)
        → Models (cached state snapshots)
        → EventStream (discovery + state polls → in-process events)
    → Afero / Hubspace cloud (REST)
```

Key concepts:

| Term                 | Meaning                                                                                      |
| -------------------- | -------------------------------------------------------------------------------------------- |
| **Bridge**           | `AferoBridgeV1` — main entry point; owns HTTP session, polling, controllers                  |
| **Auth**             | `AferoAuth` — credential login and OTP; returns `TokenData`; decoupled from bridge since 8.0 |
| **Controller**       | Typed collection (`LightController`, `FanController`, …) on `bridge.lights`, etc.            |
| **Resource / model** | Cached state (`Light`, `Fan`, …); updated by polls and command responses                     |
| **EventStream**      | Background discovery/state polling; emits `EventType` to subscribers                         |

### 8.0 auth pattern

Since **8.0.0**, `AferoBridgeV1` takes **`username` + `refresh_token`** (optional bearer `token`), not a password. Login flow:

```python
auth = v1.AferoAuth.for_login(session, username, password)
token_data = await auth.login()  # or submit_otp() on OTPRequired
bridge = v1.AferoBridgeV1(username, token_data.refresh_token, session=session)
```

See [docs/user/auth.rst](docs/user/auth.rst) for full auth documentation.

### Typical session flow

1. Authenticate with `AferoAuth` (or reuse a saved refresh token).
2. Create `AferoBridgeV1` and `await bridge.initialize()`.
3. `await bridge.async_block_until_done()` — wait for first discovery poll.
4. Read via controllers; write via `set_state` / action methods.
5. `await bridge.close()` (or `async with bridge`).

Models are **read-only snapshots** — changing attributes locally does not write to the cloud.

### Source layout

| Path                                   | Role                                                |
| -------------------------------------- | --------------------------------------------------- |
| `src/aioafero/v1/__init__.py`          | `AferoBridgeV1`, public exports                     |
| `src/aioafero/v1/auth.py`              | Authentication                                      |
| `src/aioafero/v1/controllers/`         | Per-device-type controllers                         |
| `src/aioafero/v1/models/`              | Resource models and mixins                          |
| `src/aioafero/v1/controllers/base.py`  | `BaseResourcesController` — shared controller logic |
| `src/aioafero/v1/controllers/event.py` | Polling and event dispatch                          |
| `src/aioafero/device.py`               | Raw `AferoDevice` / state types                     |
| `tests/`                               | Mirrors `src/` layout                               |

## Async

The library **must remain fully async-compatible**:

-   Use `async def` for I/O and bridge/controller methods.
-   Do not use blocking I/O in async code paths.
-   Prefer `asyncio.timeout` over `async_timeout` (banned by ruff).
-   Always close bridges and sessions (`await bridge.close()`, `await session.close()`).

## Adding a device type or controller

Implement here first, then wrap in Home Assistant (or other hosts). Follow existing controllers as templates.

1. **Model** — add `src/aioafero/v1/models/<type>.py`; register in `models/__init__.py`.
2. **Controller** — subclass `BaseResourcesController`; set `ITEM_TYPE_ID`, `ITEM_TYPES`, `ITEM_CLS`, `ITEM_MAPPING`, and sensor/number/select dicts as needed.
3. **Bridge** — register controller on `AferoBridgeV1`; add to `AferoModelResource` / `AferoController` unions and `__all__` in `v1/__init__.py`.
4. **Split devices** — if one physical device maps to multiple resources, use `DEVICE_SPLIT_CALLBACKS` (see [docs/user/device_splitting.rst](docs/user/device_splitting.rst)).
5. **Tests** — add `tests/v1/models/test_<type>.py` and `tests/v1/controllers/test_<type>.py`; use `mocked_bridge` fixture and helpers in `tests/v1/utils.py`.
6. **Docs** — update `docs/user/` and `CHANGELOG.rst` for public API changes; run `uv run tox -e docs`.
7. **Release** — bump `[project] version` in `pyproject.toml`.

Controller writes go through `BaseResourcesController.set_state` / `update_afero_api` — do not bypass the controller layer for cloud calls.

## Testing

-   Tests mirror `src/` under `tests/`.
-   Use **`mocked_bridge`** or **`mocked_bridge_req`** from `tests/conftest.py` for controller tests.
-   Simulate discovery/updates with `bridge.generate_devices_from_data()` and `bridge.generate_events_from_data()`.
-   Always **`await bridge.close()`** in fixture teardown to avoid lingering asyncio tasks.
-   HTTP mocking uses `aioresponses` / `mock_aioresponse`; see `tests/conftest.py` for the aiohttp 3.14 shim.
-   **Coverage must stay at 100%** — the [Codecov](https://app.codecov.io/gh/Expl0dingBanana/aioafero) PR check fails when project coverage drops below 100% (see [example PR report](https://app.codecov.io/gh/Expl0dingBanana/aioafero/pull/63?dropdown=coverage&src=pr&el=continue)). After the parallel tox run, check the combined `coverage report -m` from the `report` env, or run `uv run tox -e coverage`. Add tests for any new or changed lines before committing.

## Documentation

| File                    | Role                                                          |
| ----------------------- | ------------------------------------------------------------- |
| `README.rst`            | Project overview, quick start, links                          |
| `CHANGELOG.rst`         | User-visible changes per release                              |
| `docs/user/`            | Hand-written user guide (auth, bridge, controllers, examples) |
| `docs/api/`             | **Generated** by sphinx-apidoc — do not edit by hand          |
| `docs/contributing.rst` | Doc layout and when to update                                 |

Update docs in the same PR when public API or user-facing behavior changes. Link new user-guide pages from `docs/index.rst`.

For fast doc iteration: `uv sync --extra docs` then `uv run sphinx-build -W -b html docs docs/_build/html`.

## Further reading

Agents do not automatically read every doc file — consult these when relevant:

-   **`README.rst`** — overview and quick start
-   **`CHANGELOG.rst`** — breaking changes (especially 8.0 auth refactor)
-   **`CONTRIBUTING.md`** — PR checklist pointer
-   **`docs/user/overview.rst`** — architecture and session flow
-   **`docs/user/auth.rst`** — authentication and OTP
-   **`docs/user/examples.rst`** — subscribe callbacks and usage patterns
-   **`docs/contributing.rst`** — documentation layout and preview
-   **`docs/testing.rst`** — tox envs, coverage, CI

## Quality gate

All of the following **must pass** before committing or opening a PR:

1. **Lint** — `uv run tox -e lint` (pre-commit: ruff, **bandit**, format, codespell, yaml, …).
2. **Audit** — `uv run tox -e audit` (pip-audit on runtime dependencies).
3. **Tests** — `uv run tox run-parallel -p auto -o --skip-env lint` (pytest on Python 3.12, 3.13, and 3.14).
4. **Coverage** — combined project coverage must remain **100%**. The [Codecov](https://app.codecov.io/gh/Expl0dingBanana/aioafero) PR check fails when coverage is below 100%; add tests for all new/changed code paths.
5. **Docs** — `uv run tox -e docs` when changing public API or anything under `docs/`.

```bash
uv sync --extra test
uv run tox -e lint
uv run tox -e audit
uv run tox run-parallel -p auto -o --skip-env lint
# uv run tox -e docs   # when docs or public API changed
```

Do not commit with failing lint, failing tests, or uncovered lines.
