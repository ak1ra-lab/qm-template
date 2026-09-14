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
- **Pinned builds**: dated builds are selected where the upstream offers them,
  and images mirror the upstream directory layout
- **Resumable downloads**: uses `axel`, `aria2c`, `wget` or `curl`, whichever
  is available, with a configurable number of parallel connections, progress
  output by default (silence it with `--quiet`) and a from-scratch retry when a
  download fails or fails checksum verification
- **Retrying metadata fetches**: checksum and directory listings survive
  transient 5xx/network errors with exponential backoff
- **Local image inventory**: `qm-template images` lists downloaded images with
  their size and checksum sidecar, and `--prune` removes superseded dated
  builds and orphaned checksum files
- **Complete `qm create` command**: the whole template is assembled into a
  single `qm create ... --template 1` invocation instead of a chain of
  `qm set` calls
- **Automatic VM IDs**: the next free ID is picked from `qm list` (or the
  Proxmox config directory), starting at `create.start_id` (default 9000)
- **Configurable CPU type**: `create.cpu`/`--cpu` overrides the default
  `cputype=host` when migration across CPU generations matters
- **TOML configuration**: read with `tomllib` from the standard library
- **Standard library only**: Python >= 3.11; external commands are limited to
  the downloader and the Proxmox VE `qm`/`pvesm` tools

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) to install and develop
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command

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

The configuration file is optional and loaded from
`/etc/qm-template/config.toml`. It is created with the built-in defaults on
first run; use `--config PATH` or `QM_TEMPLATE_CONFIG` to point elsewhere.
Downloaded images are stored in `/var/lib/qm-template` unless
`paths.images_dir` overrides it, mirroring the upstream layout:

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` orders the downloaders and `download.connections` sets the
number of parallel connections for `axel` and `aria2c`. Downloads show progress
by default; set `download.quiet = true` or pass `--quiet` to hide it.
`create.cpu` sets the CPU type passed as `cputype=...` (default `host`).
`create.start_id` and `create.step` drive automatic VM ID selection (default
`9000` and `1`). `create.sshkeys` lists inline SSH public keys and
`create.sshkeys_files` lists key files; the contents of both are merged and
deduplicated by key fingerprint for Cloud-Init, and at least one key is
required. To create the file manually instead:

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

# print the first available downloader's command without running it
qm-template download --dry-run alpine

# hide the downloader progress output
qm-template download --quiet alpine

# list downloaded images with size and checksum sidecar
qm-template images

# remove superseded dated builds and orphaned checksum files
qm-template images --prune

# list distros and their configured defaults
qm-template distros
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed): the newest build is selected, and a
newer build is downloaded alongside the old one instead of overwriting it.
Interrupted downloads are resumed on the next run; partial files are stored as
`<image>.part`. A failed download falls back to the next configured downloader
and is retried from scratch; a completed download that fails checksum
verification is downloaded once more from scratch before the command fails.
Checksum files and directory listings are retried with exponential backoff on
transient 5xx and network errors. The checksum fetched from the upstream source
is saved next to the image as `<image>.sha256` or `<image>.sha512`, depending on
the upstream algorithm.

`qm-template images [pattern]` prints one line per image with a human-readable
size and the checksum sidecar algorithm. `--prune` removes older builds whose
names differ only in build dates/versions, together with their checksum
sidecars, plus checksum files whose image is gone; it asks for confirmation
unless `--yes` is passed, and `--dry-run` only lists the files it would remove.

### Create a VM template

```shell
# interactive image selection; the VM ID is chosen automatically
qm-template create

# filter images with a regular expression on the relative path
qm-template create debian-13

# non-interactive with an explicit ID
qm-template create --vm-id 9000 --vm-name debian-13-template

# use a migration-friendly CPU type
qm-template create --cpu x86-64-v2-AES

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

When `--vm-id` is omitted, `qm-template` collects the IDs in use from
`qm list` (falling back to `/etc/pve/qemu-server/*.conf`) and picks the first
free ID at or after `create.start_id` (default `9000`), advancing by
`create.step` (default `1`); the 9000+ range keeps templates away from regular
VMs. If `qm create` fails, an existing but incomplete VM config is reported with
the `qm destroy` command needed to clean it up.

The resulting command is a single `qm create` invocation, which `--dry-run`
pretty prints as:

```shell
qm create 9000 \
    --name debian-13-template \
    --cpu cputype=host \
    --cores 1 \
    --balloon 1024 \
    --memory 1024 \
    --net0 model=virtio,firewall=1,bridge=vmbr0 \
    --scsihw virtio-scsi-single \
    --agent type=virtio,enabled=1 \
    --machine q35 \
    --ostype l26 \
    --serial0 socket \
    --vga serial0 \
    --scsi0 local-lvm:0,import-from=/path/to/image.qcow2 \
    --scsi1 local-lvm:cloudinit \
    --boot order=scsi0 \
    --ipconfig0 ip=dhcp \
    --ciupgrade 0 \
    --ciuser debian \
    --cipassword debian \
    --sshkeys ~/.ssh/id_ed25519.pub \
    --template 1
```

## Supported distros

| Name        | Default release | Default variant | Notes                             |
| ----------- | --------------- | --------------- | --------------------------------- |
| `debian`    | `trixie`        | `genericcloud`  | `--release` accepts `-backports`  |
| `ubuntu`    | `resolute`      | `server`        | variant `minimal` also supported  |
| `rocky`     | `10`            | `GenericCloud`  | variant `GenericCloud-LVM`        |
| `almalinux` | `10`            | `GenericCloud`  | variant `GenericCloud-ext4`       |
| `fedora`    | `44`            | `Generic`       | variant `UEFI-UKI`                |
| `centos`    | `10`            | `GenericCloud`  | CentOS Stream                     |
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
│   ├── commands.py     # download / create / images / distros commands
│   ├── config.py       # TOML settings and first-run config seeding
│   ├── checksum.py     # checksum parsing and verification
│   ├── config.default.toml  # default configuration shipped in the wheel
│   ├── download.py     # axel / aria2c / wget / curl wrappers
│   ├── http.py         # HTTP helpers, retries and directory listings
│   ├── images.py       # local image inventory and pruning
│   ├── log.py          # logging setup
│   ├── pve.py          # qm/pvesm integration and VM ID selection
│   ├── shell.py        # grouped command rendering and execution
│   └── distros/        # one module per distro family
└── tests/
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/qm-template/>.

## References

- [Proxmox VE Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Debian Cloud Images](https://cloud.debian.org/images/cloud/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
