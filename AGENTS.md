# AGENTS.md

This is a Python project using an Astral-centered toolchain (`uv`, `ruff`,
`ty`, `pytest`, `mkdocs-material`). Application code lives under
`src/qm_template`.

## Tooling - use these, not the defaults

`just <recipe>` is a convenience wrapper for humans; each recipe is a thin
`uv run ...` (see `justfile`). Agents can call `uv run ...` directly when that is
more flexible - the two are equivalent, not mutually exclusive.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`; extra args forward
  through, e.g. `just sync --frozen`). Never `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** (`just lint` = `uv run ruff check --fix` then
  `uv run ruff format`, over `src/ tests/`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty** (astral-sh/ty), `src/` only
  (`just typecheck` = `uv run ty check src/`). Never `mypy`.
- Tests: **pytest** (`just test` = `uv run pytest -v tests/`). Extra args go
  *before* `tests/`, so `just test -k <pattern>`; or run
  `uv run pytest -v tests/test_file.py` directly.
- Docs: `just docs-build` = `NO_MKDOCS_2_WARNING=1 uv run mkdocs build`
  (and `just docs-serve` to preview).
- Build: `just build` = `uv build`.
- Pre-commit: `uv run pre-commit run --all-files` runs every configured hook
  (check-yaml/check-toml, end-of-file-fixer, trailing-whitespace, ruff, uv-lock,
  ty). Run it explicitly before committing - the hooks are not a passive safety
  net. Manual-stage hooks (e.g. ansible-lint) need `--hook-stage manual`.

Python changes MUST pass ruff, ty, and pytest before commit, then
`uv run pre-commit run --all-files` as the final gate for the remaining hooks.

## Versioning

Version is dynamic via `hatch-vcs` (Git tags). DO NOT manually bump a version
string. To publish a release, push a tag starting with `v` (e.g. `v0.1.0`);
CI builds and publishes to PyPI automatically.

## Project conventions

- CLI uses `argparse` + `argcomplete` for shell completion; entrypoint
  `qm-template`.
- Tests live under `tests/` and track public behavior, especially the CLI.
- `pyproject.toml` is the single source of truth for dependencies and metadata.

## Docs (bilingual)

`docs/` is served by mkdocs with the i18n plugin (`docs_structure: suffix`):
every page has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling
(e.g. `index.md` + `index.zh.md`). When adding or changing user-facing behavior,
update BOTH language files.
