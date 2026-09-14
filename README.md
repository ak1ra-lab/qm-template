# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

Proxmox VE template helper scripts

## Installation

```bash
uv sync --group dev
```

## Usage

```bash
uv run qm-template --version
```

## Development

```bash
just lint
just typecheck
just test
just docs-build
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/qm-template/>, and local docs configuration is stored in `mkdocs.yaml`.
