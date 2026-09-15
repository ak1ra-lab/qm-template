# qm-template

A Python CLI that downloads cloud images, creates Proxmox VE VM templates and
prepares VirtualBox artifacts, with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE and Arch Linux.
- **Checksum verification** against each distro's official checksum files,
  saved next to the image (`<image>.sha256`/`.sha512`).
- **Resumable downloads** via the first available of `axel`, `aria2c`, `wget`
  or `curl`, with progress output (silence with `--quiet`) and retries.
- **A single `qm create ... --template 1` command** instead of a chain of
  `qm set` calls, with automatic next free VM ID selection and a configurable
  CPU type.
- **Local VM artifacts** with `qm-template prepare`: a hypervisor disk
  conversion via `qemu-img` (VDI, VMDK, QCOW2, raw or VHDX) and a generated
  NoCloud seed ISO, both next to the source image.
- **Validated configuration**: settings and optional `[distro.<name>]`
  overrides are checked with `pydantic-settings`, `QM_TEMPLATE_*` environment
  variables override the file, and `qm-template config` prints a
  starting-point configuration to stdout.
- **Mirror-friendly**: point any distro at an upstream or mirror through
  `[distro.<name>] base_url`, including its checksum file.
- **Shell completion** with `argcomplete`, including the parameter values each
  distro accepts.

## Quick start

```shell
uv tool install qm-template
qm-template download debian
qm-template distros
```

See [Getting Started](getting-started.md) for configuration, usage and
development instructions.
