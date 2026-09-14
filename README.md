# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

A Python CLI that downloads cloud images and creates Proxmox VE VM templates
with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE and Arch Linux
- **Checksum verification**: SHA-256/SHA-512 fetched from each distro's official
  checksum files and saved next to the image (`<image>.sha256`/`.sha512`)
- **Resumable downloads**: uses `aria2c`, `wget` or `curl`, whichever is
  available
- **Complete `qm create` command**: the whole template is assembled into a
  single `qm create ... --template 1` invocation instead of a chain of
  `qm set` calls
- **TOML configuration**: read with `tomllib` from the standard library
- **Standard library only**: Python >= 3.11; external commands are limited to
  the downloader and the Proxmox VE `qm`/`pvesm` tools

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) to install and develop
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `aria2c`, `wget` or `curl` for the `download` command

## Installation

Install the CLI as a uv tool:

```shell
uv tool install qm-template
```

For development, sync the project and run it from the virtual environment:

```shell
uv sync --group dev
uv run qm-template --help
```

## Configuration

The configuration file is optional and loaded from `/etc/qm-template/config.toml`.
Use `--config PATH` or `QM_TEMPLATE_CONFIG` to point elsewhere. Downloaded
images are stored in `/var/lib/qm-template` unless `paths.images_dir` overrides
it. Start from the example file:

```shell
install -d /etc/qm-template
cp qm-template.example.toml /etc/qm-template/config.toml
```

Command-line options override the configured defaults.

## Usage

### Download a cloud image

```shell
# default distro from the configuration file
qm-template download

# pick a distro, optionally override parameters
qm-template download debian
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# only print the resolved URL
qm-template download --dry-run alpine

# list distros and their configured defaults
qm-template distros
```

Interrupted downloads are resumed on the next run; partial files are stored as
`<image>.part`. The checksum fetched from the upstream source is saved next to
the image as `<image>.sha256` or `<image>.sha512`, depending on the upstream
algorithm.

### Create a VM template

```shell
# interactive image and VM ID selection
qm-template create

# filter images with a regular expression
qm-template create debian-13

# non-interactive
qm-template create --vm-id 9000 --vm-name debian-13-template

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

The resulting command is a single `qm create` invocation:

```shell
qm create 9000 --name debian-13-template \
    --cpu cputype=host --cores 1 --balloon 1024 --memory 1024 \
    --net0 model=virtio,firewall=1,bridge=vmbr0 \
    --scsihw virtio-scsi-single --agent type=virtio,enabled=1 \
    --machine q35 --ostype l26 --serial0 socket --vga serial0 \
    --scsi0 local-lvm:0,import-from=/path/to/image.qcow2 \
    --scsi1 local-lvm:cloudinit --boot order=scsi0 --ipconfig0 ip=dhcp \
    --ciupgrade 0 --ciuser debian --cipassword debian \
    --sshkeys ~/.ssh/id_ed25519.pub --template 1
```

## Supported distros

| Name        | Default release | Default variant | Notes                             |
| ----------- | --------------- | --------------- | --------------------------------- |
| `debian`    | `trixie`        | `genericcloud`  | `--release` accepts `-backports`  |
| `ubuntu`    | `resolute`      | `server`        | variant `minimal` also supported  |
| `rocky`     | `9`             | `GenericCloud`  | variant `GenericCloud-LVM`        |
| `almalinux` | `9`             | `GenericCloud`  | variant `GenericCloud-ext4`       |
| `fedora`    | `44`            | `Generic`       | variant `UEFI-UKI`                |
| `centos`    | `9`             | `GenericCloud`  | CentOS Stream                     |
| `alpine`    | `3.24`          | `generic`       | BIOS firmware, Cloud-Init enabled |
| `opensuse`  | `tumbleweed`    | `Minimal`       | `--release 15.6` for Leap         |
| `archlinux` | `latest`        | `cloudimg`      | variant `basic` also supported    |

## Development

```shell
uv sync --group dev
just lint        # ruff check --fix + ruff format
just typecheck   # ty check src/
just test        # pytest
just docs-build  # mkdocs build
```

Project layout:

```
qm-template/
├── pyproject.toml
├── qm-template.example.toml
├── src/qm_template/
│   ├── cli.py          # argument parsing and entry point
│   ├── commands.py     # download / create / distros commands
│   ├── config.py       # TOML settings
│   ├── checksum.py     # checksum parsing and verification
│   ├── download.py     # aria2c / wget / curl wrappers
│   ├── http.py         # HTTP helpers and directory listings
│   ├── log.py          # logging setup
│   ├── pve.py          # qm/pvesm integration
│   └── distros/        # one module per distro family
└── tests/
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/qm-template/>.

## References

- [Proxmox VE Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Debian Cloud Images](https://cloud.debian.org/images/cloud/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
