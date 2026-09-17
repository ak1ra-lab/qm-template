# AGENTS.md

`qm-template` is a Python CLI (Python >= 3.11) that downloads distro cloud
images, creates Proxmox VE VM templates and prepares local VM artifacts (disk
plus NoCloud seed ISO). Application code lives under `src/qm_template`; see
`README.md` and `docs/` for user-facing behavior. Local `create` normally runs
as root on a Proxmox VE host; `prepare` and remote `create --pve` typically run
on a workstation.

`download` shells out to `axel`/`aria2c`/`wget`/`curl`; local `create` to
`qm`/`pvesm`; remote `create` talks to the Proxmox VE API through `proxmoxer`;
`prepare` to `qemu-img` and `genisoimage`/`xorriso`/`mkisofs`. Tests MUST mock
these external commands, the network and the API: never exercise them for real
in tests.

## Tooling

`just <recipe>` is a thin wrapper around `uv run ...` (see `justfile`); calling
`uv run ...` directly is equivalent.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`). Never
  `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** over `src/ tests/` (`just lint` = `ruff check --fix`
  then `ruff format`). Never `black`/`isort`/`flake8`.
- Typecheck: **ty**, `src/` only (`just typecheck` = `uv run ty check src/`).
  Never `mypy`.
- Tests: **pytest** (`just test` = `uv run pytest -v tests/`; `just coverage`
  adds coverage). Extra args go before `tests/`, e.g. `just test -k <pattern>`.
- Docs: `just docs-build` and `just docs-serve` (mkdocs-material).
- Build: `just build` = `uv build`; `just all` runs lint, typecheck, test,
  coverage, build and docs-build.
- Python changes MUST pass ruff, ty and pytest, then
  `uv run pre-commit run --all-files`.

## Versioning

Version is dynamic via `hatch-vcs` (Git tags). DO NOT bump version strings
manually; push a tag starting with `v` (e.g. `v0.1.0`) and CI publishes to
PyPI. Record user-visible changes in `CHANGELOG.md` under `[Unreleased]`;
releases move them under a new version heading.

## Conventions

- CLI: `argparse` with `download`, `create`, `prepare`, `distros` and `config`
  subcommands (aliases `get`, `template`); entrypoint `qm-template`.
- Short options follow common conventions and are added only for frequently
  used flags: `-c/--config`, `-V/--version`, `-n/--dry-run`, `-q/--quiet`,
  `-f/--force`, `-v/--verbose`. Everything else stays long-only and is
  discoverable through completion.
- Config: `Settings` models live in `config.py`; unknown keys are rejected with
  per-key errors and migration hints. Environment variables (`QM_TEMPLATE_*`
  with `__` for nesting) beat the file; CLI options beat both.
  `[distro.<name>]` overrides are optional. `[pve.<name>]` sections describe
  remote Proxmox VE API hosts and may carry `create`/`vmid`/`cloudinit`
  sub-tables that override the global sections for that host; per-host layers
  only override explicitly set fields.
- `create` targets the local `qm` host by default and a remote `[pve.<name>]`
  host when `--pve NAME` is given. Both satisfy the `PveTarget` protocol
  (`pve.py`, `api.py`) and are driven by a shared `VmSpec`; keep the API
  target's request builders pure and free of I/O so they stay unit-testable.
- Distro parameters are declared as `Option` schemas on each `Distro` subclass
  (per-distro defaults, accepted values and help). The same schema drives
  `merge()` validation, `[distro.<name>]` config validation, the generated
  `download` flags, `qm-template distros` and completion; `defaults` are
  derived from it. Never duplicate parameter data elsewhere.
  `Option(cli=False)` keeps a parameter out of the CLI (used by `base_url`).
- When adding a distro behavior, prefer a declared `Option` over a hardcoded
  token, mapping or regex branch: hidden axes that change the artifact (for
  example FreeBSD's `fs` or Alpine's `firmware`) must be options, while fixed
  prerequisites of this tool (Cloud-Init, qcow2, upstream revisions) stay
  hardcoded and are not presented as knobs. `Option.pattern` validates
  free-form values early.
- Defaults: config `/etc/qm-template/config.toml` (optional and never written
  automatically; `qm-template config [--full]` prints a starting point), images
  `/var/lib/qm-template`, mirroring the upstream layout
  (`<distro>/<release>/[<tag>/]<filename>`). Dated builds are pinned where the
  upstream provides them.
- `pyproject.toml` is the single source of truth for dependencies and metadata;
  `.copier-answers.yml` is managed by Copier and MUST NOT be edited by hand.
- Tests live under `tests/` and track public behavior, especially the CLI.
- Docs are bilingual (mkdocs-static-i18n, `docs_structure: suffix`): every page
  has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling. Update BOTH
  language files when changing user-facing behavior.
