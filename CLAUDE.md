# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KovNet CLI — a Python command-line client for the KovNet childcare platform (kinderopvang). It authenticates via session cookies against `auth.kovnet.nl` (Rails) and talks to the `app.kovnet.nl` API.

## Commands

```bash
# Install for development
uv sync --extra dev

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_helpers.py::TestExtractCsrfToken::test_meta_tag

# Run the CLI locally
uv run kovnet --help

# Install as a tool
uv tool install .
```

## Architecture

Three source modules in `src/kovnet/`:

- **`client.py`** — Session-cookie authentication (`KovNetAuth`) and API client (`KovNetClient`). Handles the 3-step Rails login flow (GET /signin, POST /check_users, POST /signin), session persistence at `~/.config/kovnet/session.json` (mode 0600), and auto-re-login. `KovNetClient` is a context manager wrapping `httpx.Client` with methods for each API endpoint (children, contracts, invoices, holidays, newsletters). Includes `explore()` for probing arbitrary endpoints.

- **`helpers.py`** — Pure stdlib helpers: `extract_csrf_token()` (Rails CSRF token from HTML) and `scrape_invoices_table()` (DataTables HTML to list of dicts).

- **`cli.py`** — Click-based CLI with 9 commands. Uses Rich for formatted output (tables). Supports `--json` flag for machine-readable output. Credentials come from CLI args, env vars (`KOVNET_USERNAME`/`KOVNET_PASSWORD`), or interactive prompt. Loads `.env` from `~/.config/kovnet/.env` and `./env`.

`__init__.py` exports `KovNetClient`, `KovNetAuth`, `extract_csrf_token` as the public SDK surface. Core dependency is only `httpx`; CLI extras (`rich`, `click`, `python-dotenv`) are optional via `pip install kovnet-cli[cli]`.

Entry point: `kovnet` → `kovnet.cli:main()` (configured in pyproject.toml).

## Key Patterns

- All HTTP is synchronous via `httpx.Client` (not async)
- Auth uses Rails session cookies (not OAuth2)
- Some endpoints return JSON, others return HTML that needs scraping
- CLI output is Dutch language
