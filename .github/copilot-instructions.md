# Copilot code review — aioafero

When reviewing pull requests for this repository, prioritize the checks below over style nits.

## Security and secrets

-   All sensitive values (passwords, refresh/bearer tokens, OAuth codes, PKCE verifiers, account IDs) must be registered with `securelogging.add_secret()` before DEBUG logging and removed when no longer needed.
-   Never call `add_secret(None)` or `add_secret("")` — validate strings first.
-   When replacing token data, remove old secrets only if they are not reused in the new `TokenData`.
-   PKCE verifiers: redact in logs without leaving entries in the global secret registry unless the full login flow will clean them up.
-   Passwords must be cleared from memory after credential POST (`_clear_password()`).

## Correctness and defensive coding

-   Validate API JSON before use; chained `.get()` on possibly-`None` nested dicts must not raise `AttributeError`. Treat missing/empty IDs as errors (e.g. `AferoError("No account ID found")`).
-   `TokenData.token` and `access_token` are optional (`str | None`); runtime code must not return `None` as a bearer token or produce `Authorization: Bearer None`.
-   Missing bearer or expired token must trigger refresh in `AferoAuth.token()`.
-   `AferoAuth` and `AferoBridgeV1` require `aiohttp.ClientSession` at construction — no lazy session creation except `AferoBridgeV1.open()` creating one internally (`_close_session=True`).

## Architecture (8.0 API break)

-   Credential login: `AferoAuth.for_login(session, user, password)` only — not via `AferoAuth.__init__`.
-   Runtime: `AferoAuth(session, user, refresh_token, token=..., token_expiration=...)`.
-   Bridge: `username` + `refresh_token` (no password). `bridge.close()` does not close a caller-supplied session.

## Tests and CI expectations

-   **100% coverage** on `aioafero` package (`--cov=aioafero`); new branches need tests.
-   Fully async library — no blocking I/O in library code.
-   Run locally: `uv run tox -e lint`, `uv run tox -e audit`, `uv run tox run-parallel -p auto -o --skip-env lint`.

## Typing

-   Public `NamedTuple` / return types must match runtime values (no `None` in fields typed as `str`).
-   Match existing conventions in surrounding modules.
