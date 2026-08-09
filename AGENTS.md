# AI agent guide — aioafero

Async Python library for the Afero IoT cloud API. **Device and protocol logic belongs here**, not in downstream integrations (e.g. [Hubspace-Homeassistant](https://github.com/jdeath/Hubspace-Homeassistant)). Package version is in `pyproject.toml` / [CHANGELOG.rst](CHANGELOG.rst).

**Scope / PRs:** Stay on the asked task — no drive-by refactors, invented cloud payloads, or “fixing” HA behavior here. Prefer small, reviewable PRs. If work spans unrelated concerns (behavior vs docs/tooling, or multiple features), split them. Aim for a diff a human can review in one pass—not multi-thousand-line dumps.

## Commands and quality gate

Run everything through **uv** (`uv sync --extra test` first). Prefer `uv run tox` over calling `pytest`, `ruff`, or `pre-commit` directly.

```bash
uv run tox -e lint          # pre-commit: ruff, bandit, format, codespell, yaml, …
uv run tox -e audit         # pip-audit on runtime deps
uv run tox run-parallel -p auto -o --skip-env lint   # py312–py314 + coverage (default before commit)
uv run tox -e py314 -- tests/v1/test_auth.py -q    # single env / subset
uv run tox -e docs          # when public API or docs/ changed
```

All of the above must pass before a PR: **lint**, **audit**, **tests** (3.12–3.14), **100% coverage** ([Codecov](https://app.codecov.io/gh/Expl0dingBanana/aioafero) fails below 100%), **docs** when applicable. Coverage targets `aioafero` via `[tool.coverage.run] source_pkgs` (pytest uses bare `--cov`). After changing `src/`, run the relevant tox env and **read the missing-lines report** (or `uv run tox -e report`) before calling it done. Details: [docs/testing.rst](docs/testing.rst), [SECURITY.md](SECURITY.md).

## Pre-push review (reduce Copilot ping-pong)

Before pushing, run the quality gate above, then review the branch diff:

```bash
git diff main...HEAD -- src/ tests/
```

In Cursor, ask: _Review this diff like Copilot would — secrets/redaction, None paths, API JSON validation, typing vs runtime, auth/session rules._

GitHub Copilot PR review reads [.github/copilot-instructions.md](.github/copilot-instructions.md) (≤4k chars). Re-request after push:

```bash
gh pr edit <number> --add-reviewer Copilot
```

The GraphQL “Projects (classic)” warning from `gh pr edit` is harmless.

## Linting

Rules live in `pyproject.toml` and `.pre-commit-config.yaml` — fix what `tox -e lint` reports. Match surrounding code. Library is **fully async** (`async def`, no blocking I/O; use `asyncio.timeout`, not `async_timeout`). Public code needs docstrings; tests are exempt. **`TC001`–`TC003` ignored in tests** — do not use `TYPE_CHECKING` imports in tests (breaks `pytest.patch()`).

## Architecture

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

**Secrets / dumps:** never commit credentials, live tokens, or dumps with PII. Prefer anonymized device dumps under `tests/v1/device_dumps/`.

## Testing

How tests are expected to be written:

1. **Decide what you are proving.** If the assert is an _end result_ (model
   `available`, split entities, cache contents, events after a poll/workflow),
   use the **real bridge flow**. If the assert is a single function’s contract
   (helper return value, pure transform, one edge skip), call that function
   directly.

2. **For end results, seed reality then poke HTTP.** Load a dump from
   `tests/v1/device_dumps/`, run `generate_events_from_data` +
   `async_block_until_done` (or the same path existing tests use), patch
   `request` / `_fetch_device_states` / similar for the failure or response you
   need, then assert on **real** controller items. Do **not** invent fake
   controllers, fake `get_device` returns, or hand-wired `_known_devs` graphs
   for those tests.

3. **Mirror first.** Before writing a new workflow test, find a sibling that
   already does it (e.g. trim splits in `tests/v1/controllers/test_light.py`)
   and copy that pattern—same fixtures, same dump helpers
   (`create_hs_raw_from_dump` / `create_devices_from_data`).

4. **Reuse fixtures.** Prefer `mocked_bridge` / `mocked_bridge_req` and
   `aio_sess`. Do not add large custom mocks when an existing fixture + dump
   covers it.

5. **Parameterize where possible.** Prefer `@pytest.mark.parametrize` (or
   equivalent) over near-duplicate test functions when cases share setup and
   only inputs/expected outcomes differ—keeps the suite shorter and easier to
   extend.

6. **Module coverage via the mirrored test file.** Prefer covering a `src/`
   module from its matching `tests/` file (e.g. `controllers/event.py` →
   `tests/v1/controllers/test_event.py`). When you change a module, that test
   file alone should hit **100%** on it — check with a scoped cov run such as
   `uv run pytest tests/v1/controllers/test_event.py --cov=aioafero.v1.controllers.event --cov-report=term-missing`.
   Behavior belongs in asserts, not just line execution.

7. **Unit-test escape hatch.** Mocks and direct calls are fine _inside_ a
   focused unit test. They are **not** OK as a substitute when the thing you
   care about is still end-state on live models after a bridge workflow—even
   if you also call a private helper afterward. If the assert touches a live
   controller item (`available`, splits, cache, events), prefer dumps even
   inside an otherwise “unit” test. Seed via dumps/discovery first; then call
   the helper only if that is the unit under test.

## Adding a device type

Follow an existing controller (e.g. fan, switch). Model in `v1/models/` → controller subclassing `BaseResourcesController` → register on `AferoBridgeV1` and type unions in `v1/__init__.py` → tests under `tests/v1/` (see Testing above) → `docs/user/` + `CHANGELOG.rst` + version bump in `pyproject.toml`. Split devices: [docs/user/device_splitting.rst](docs/user/device_splitting.rst).

## Further reading

[CHANGELOG.rst](CHANGELOG.rst) · [README.rst](README.rst) · [docs/user/examples.rst](docs/user/examples.rst) · [docs/user/bridge.rst](docs/user/bridge.rst) · [docs/contributing.rst](docs/contributing.rst) · [CONTRIBUTING.md](CONTRIBUTING.md)
