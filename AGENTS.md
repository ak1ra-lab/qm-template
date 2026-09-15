# AGENTS.md

`qm-template` is a Python CLI that downloads distro cloud images, creates
Proxmox VE VM templates and prepares local VM artifacts (disk plus NoCloud
seed ISO). The `create` command targets a Proxmox VE host and is normally run
as root; `prepare` typically runs on a workstation. Application code lives
under `src/qm_template`.

`download` shells out to `axel`/`aria2c`/`wget`/`curl`; `create` shells out to
Proxmox VE (`qm`, `pvesm`); `prepare` shells out to `qemu-img`/`genisoimage`.
None of these must be exercised in tests - tests mock or only cover pure
logic.

## Tooling

`just <recipe>` is a thin wrapper around `uv run ...` (see `justfile`); calling
`uv run ...` directly is equivalent.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`). Never
  `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** (`just lint` = `uv run ruff check --fix` then
  `uv run ruff format`, over `src/ tests/`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty**, `src/` only (`just typecheck` = `uv run ty check src/`).
  Never `mypy`.
- Tests: **pytest** (`just test` = `uv run pytest -v tests/`). Extra args go
  *before* `tests/`, e.g. `just test -k <pattern>`.
- Docs: `just docs-build` and `just docs-serve` (mkdocs-material).
- Build: `just build` = `uv build`.
- Pre-commit: `uv run pre-commit run --all-files` is the final gate before
  committing.

Python changes MUST pass ruff, ty, and pytest, then pre-commit.

## Versioning

Version is dynamic via `hatch-vcs` (Git tags). DO NOT bump version strings
manually; push a tag starting with `v` (e.g. `v0.1.0`) and CI publishes to
PyPI.

## Conventions

- CLI: `argparse` with `download`, `create`, `prepare` and `distros` subcommands;
  entrypoint `qm-template`. Runtime dependencies stay empty (standard library
  only).
- Defaults: config `/etc/qm-template/config.toml`, images
  `/var/lib/qm-template`, mirroring the upstream layout
  (`<distro>/<release>/[<tag>/]<filename>`). Dated builds are pinned where the
  upstream provides them.
- Tests live under `tests/` and track public behavior, especially the CLI.
- `pyproject.toml` is the single source of truth for dependencies and metadata.

## Docs (bilingual)

`docs/` is served by mkdocs-static-i18n (`docs_structure: suffix`): every page
has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling. Update BOTH
language files when changing user-facing behavior.
