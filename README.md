# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows/publish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

**English** | [简体中文](README.zh.md)

A Python CLI that downloads cloud images, creates Proxmox VE VM templates and
prepares local VM artifacts, with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE, Arch Linux, FreeBSD and Amazon Linux 2023,
  with pinned builds, resumable downloads and checksum/signature verification.
- **Proxmox VE templates**: one `qm create ... --template 1` invocation with
  automatic VM ID selection and configurable CPU, firmware and metadata, or
  `create --pve <name>` to build the template on a remote host through its API
  (Proxmox VE >= 8.4).
- **Local VM artifacts**: `prepare` converts an image to VDI, VMDK, QCOW2, raw
  or VHDX and builds a NoCloud seed ISO for any hypervisor.
- **Validated configuration**: TOML settings with optional per-distro and
  per-host overrides, `QM_TEMPLATE_*` environment variables and unknown-key
  rejection.
- **Shell completion** for commands, options, per-distro parameters and remote
  host names.

## Quick start

```shell
uv tool install qm-template

qm-template download debian                  # download and verify an image
qm-template create --vm-id 9000              # template on this Proxmox VE host
qm-template create debian-13 --pve home      # ... or on a remote host
qm-template prepare debian-13 --format vmdk  # disk + seed ISO for any hypervisor
```

## Documentation

Full documentation: <https://ak1ra-lab.github.io/qm-template/>

- [Getting Started](https://ak1ra-lab.github.io/qm-template/getting-started/)
- [Configuration](https://ak1ra-lab.github.io/qm-template/configuration/)
- [Usage](https://ak1ra-lab.github.io/qm-template/usage/download/)
- [简体中文文档](https://ak1ra-lab.github.io/qm-template/zh/)

## Requirements

- Python >= 3.11 and [uv](https://docs.astral.sh/uv/)
- A Proxmox VE host for `create`: `qm`/`pvesm` locally, or a remote host
  reachable through its API (Proxmox VE >= 8.4) with `--pve`
- One of `axel`, `aria2c`, `wget` or `curl` for `download`, and `gpg` for
  signature verification
- `qemu-img` and one of `genisoimage`, `xorriso` or `mkisofs` for `prepare`

## Development

```shell
uv sync --group dev
just lint        # ruff check --fix + ruff format
just typecheck   # ty check src/
just test        # pytest
just docs-build  # mkdocs build
```
