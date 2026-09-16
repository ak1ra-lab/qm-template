# qm-template

A Python CLI that downloads cloud images, creates Proxmox VE VM templates and
prepares local VM artifacts, with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE, Arch Linux, FreeBSD and Amazon Linux 2023.
- **Checksum verification** against each distro's official checksum files,
  saved next to the image (`<image>.sha256`/`.sha512`).
- **GPG signature verification** of signed checksums and images with keys from
  the distro's canonical source and pinned fingerprints.
- **Resumable downloads** via the first available of `axel`, `aria2c`, `wget`
  or `curl`, with progress output (silence with `--quiet`) and retries.
- **A single `qm create ... --template 1` command** instead of a chain of
  `qm set` calls, with automatic next free VM ID selection, a configurable CPU
  type and optional tags, pool, onboot and description.
- **Remote Proxmox VE hosts**: `create --pve <name>` builds the template on a
  remote host through its API (Proxmox VE >= 8.4) and an API token, uploading
  the image to an `import` storage and reusing it on later runs. Every host
  lives in a `[pve.<name>]` section that can override `[create]`, `[vmid]` and
  `[cloudinit]` for that host.
- **Local VM artifacts** with `qm-template prepare`: a hypervisor disk
  conversion via `qemu-img` (VDI, VMDK, QCOW2, raw or VHDX) and a generated
  NoCloud seed ISO with `genisoimage`/`xorriso`/`mkisofs`, both next to the
  source image.
- **Validated configuration**: settings and optional `[distro.<name>]`
  overrides are checked with `pydantic-settings`, `QM_TEMPLATE_*` environment
  variables override the file, and `qm-template config` prints a
  starting-point configuration to stdout.
- **Mirror-friendly**: point any distro at an upstream or mirror through
  `[distro.<name>] base_url`, including its signed checksum file.
- **Shell completion** with `argcomplete`, including the parameter values each
  distro accepts.
- **Debug logging** with `-v`/`-vv` on any command.

## Quick start

```shell
uv tool install qm-template
qm-template download debian
qm-template create --vm-id 9000
```

## Documentation

- [Getting Started](getting-started.md)
- [Configuration](configuration.md)
- [Download images](usage/download.md)
- [Create a template](usage/create.md)
- [Prepare local artifacts](usage/prepare.md)
- [List distros](usage/distros.md)
