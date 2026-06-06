# Security

## Reporting a vulnerability

Please report security issues privately via [GitHub Security Advisories](https://github.com/Expl0dingBanana/aioafero/security/advisories/new) rather than opening a public issue.

## Automated checks

This repository runs:

| Check                       | When                     | Tool                                             |
| --------------------------- | ------------------------ | ------------------------------------------------ |
| Lint + Python security lint | Every PR / push          | pre-commit (ruff, **bandit**, …)                 |
| Dependency vulnerabilities  | Every PR / push + weekly | **pip-audit** (`tox -e audit`)                   |
| Deep static analysis        | Every PR / push + weekly | **CodeQL**                                       |
| Dependency update PRs       | Weekly                   | **Dependabot** (pip, GitHub Actions, pre-commit) |

Enable **Dependabot alerts** and **Dependabot security updates** under the repository **Settings → Code security and analysis** so GitHub opens PRs for known CVEs in dependencies.

## Local commands

```bash
uv sync --extra test
uv run tox -e lint    # includes bandit via pre-commit
uv run tox -e audit   # pip-audit on installed runtime deps
```
