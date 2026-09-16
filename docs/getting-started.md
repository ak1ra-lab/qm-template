# Getting Started

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- A Proxmox VE host, normally running as root, or a remote host reachable
  through its API (Proxmox VE >= 8.4) for `create --pve`
- Proxmox VE (`qm`, `pvesm`) for `create` without `--pve`
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command
- `gpg` for signature verification; Ubuntu, Fedora, Rocky, AlmaLinux, openSUSE,
  Alpine and Arch Linux ship signed metadata
- `qemu-img` and one of `genisoimage`, `xorriso` or `mkisofs` for the
  `prepare` command

## Installation

Install the CLI as a uv tool:

```shell
uv tool install qm-template
```

From a checkout:

```shell
uv tool install .
```

## Quick start

```shell
# download and verify a cloud image
qm-template download debian

# create a template on the Proxmox VE host this runs on
qm-template create --vm-id 9000

# ... or on a remote host through its API
qm-template create debian-13 --pve home

# convert an image and build a NoCloud seed ISO for other hypervisors
qm-template prepare debian-13
```

`download` resolves the newest build, verifies it against the upstream
checksum and signature, and stores it below `paths.images_dir`. `create` turns
the image into a template, either locally with `qm` or remotely through the
Proxmox VE API with `--pve`. `prepare` writes a converted disk and a `CIDATA`
seed ISO next to the image. Every command works without a configuration file;
see [Configuration](configuration.md) for the available settings and
[Usage](usage/download.md) for the details of each command.

## Shell completion

Completion is powered by `argcomplete`, which is installed with the CLI. Enable
it once per shell:

```shell
# bash
eval "$(register-python-argcomplete qm-template)"

# zsh
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete qm-template)"
```

Add the relevant lines to `~/.bashrc`/`~/.zshrc`. Command names, options and
per-distro parameter values are completed; every distro parameter flag
(`--release`, `--variant`, `--arch`, `--tag`, `--fs`, `--firmware`, ...)
completes against the distro named on the command line, with values only for
the parameters that distro supports. `create --pve` completes the host names
configured under `[pve.<name>]`.

## Development

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```

`uv run pre-commit run --all-files` is the gate before committing.
