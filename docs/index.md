# qm-template

A Python CLI that downloads cloud images and creates Proxmox VE VM templates
with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE and Arch Linux.
- **Checksum verification** against each distro's official checksum files,
  saved next to the image (`<image>.sha256`/`.sha512`).
- **Resumable downloads** via `axel`, `aria2c`, `wget` or `curl`, whichever is
  available.
- **A single `qm create ... --template 1` command** instead of a chain of
  `qm set` calls.
- **TOML configuration** read with `tomllib` from the standard library.

## Quick start

```shell
uv tool install qm-template
qm-template download debian
qm-template distros
```

See [Getting Started](getting-started.md) for configuration, usage and
development instructions.
