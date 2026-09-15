# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

A Python CLI that downloads cloud images, creates Proxmox VE VM templates and
prepares VirtualBox artifacts, with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE and Arch Linux
- **Checksum verification**: SHA-256/SHA-512 fetched from each distro's official
  checksum files and saved next to the image (`<image>.sha256`/`.sha512`)
- **Pinned builds**: dated builds are selected where the upstream offers them,
  and images mirror the upstream directory layout
- **Resumable downloads**: uses the first available of `axel`, `aria2c`, `wget`
  or `curl`, with a configurable number of parallel connections, progress
  output by default (silence it with `--quiet`) and a from-scratch retry with
  the same downloader when a download fails or fails checksum verification
- **Retrying metadata fetches**: checksum and directory listings survive
  transient 5xx/network errors with exponential backoff
- **Complete `qm create` command**: the whole template is assembled into a
  single `qm create ... --template 1` invocation instead of a chain of
  `qm set` calls
- **Automatic VM IDs**: the next free ID is picked from `qm list` (or the
  Proxmox config directory), starting at `create.start_id` (default 9000)
- **Configurable CPU type**: `create.cpu`/`--cpu` overrides the default
  `cputype=host` when migration across CPU generations matters
- **Local VM artifacts**: `prepare` converts an image to VDI, VMDK, QCOW2, raw
  or VHDX with `qemu-img` and builds a NoCloud seed ISO with `genisoimage`,
  both written next to the source image
- **TOML configuration**: read with `tomllib` from the standard library
- **Standard library only**: Python >= 3.11; external commands are limited to
  the downloader, the Proxmox VE `qm`/`pvesm` tools and `prepare`'s
  `qemu-img`/`genisoimage`

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) to install and develop
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command
- `qemu-img` and `genisoimage` for the `prepare` command

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
`cloudinit.user`/`password` configure the Cloud-Init user, and
`cloudinit.sshkeys`/`sshkeys_files` list inline SSH public keys and key files
whose contents are merged and deduplicated by fingerprint; at least one key is
required. `create.cpu` sets the CPU type passed as `cputype=...` (default
`host`), and `create.start_id`/`create.step` drive automatic VM ID selection
(default `9000` and `1`). To create the file manually instead:

```shell
install -d /etc/qm-template
cp config.example.toml /etc/qm-template/config.toml
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

# list distros and their configured defaults
qm-template distros
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed): the newest build is selected, and a
newer build is downloaded alongside the old one instead of overwriting it.
Interrupted downloads are resumed on the next run; partial files are stored as
`<image>.part`. A failed download is retried from scratch with the same
downloader and never switches to another one; a completed download that fails
checksum verification is downloaded once more from scratch before the command
fails. Checksum files and directory listings are retried with exponential
backoff on transient 5xx and network errors. The checksum fetched from the
upstream source is saved next to the image as `<image>.sha256` or
`<image>.sha512`, depending on the upstream algorithm.

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

### Prepare local VM artifacts

Most hypervisors cannot boot `.qcow2` directly, so guest disks have to be
converted. The hypervisor-agnostic `prepare` command selects a downloaded
image, converts it to a guest disk with `qemu-img` and packs a NoCloud
`user-data`/`meta-data` pair built from the `[cloudinit]` settings into a
`CIDATA`-labelled seed ISO with `genisoimage`. Both artifacts are written next
to the source image and only differ in suffix:

```shell
# debian-13.qcow2 -> debian-13.vdi + debian-13.iso
qm-template prepare debian-13

# other hypervisors: vmdk (VMware/VirtualBox), raw or vhdx (Hyper-V)
qm-template prepare --format vmdk debian-13

# override the hostname recorded in the seed
qm-template prepare --vm-name debian-13-vbox debian-13

# preview every command without running or writing anything
qm-template prepare --dry-run debian-13
```

Supported formats are `vdi` (default), `vmdk`, `qcow2`, `raw` and `vhdx`; the
extension follows the format (`--format vdi` writes `<image>.vdi`). Choosing
`qcow2` for a `.qcow2` source is rejected because it would overwrite the source
image. For VirtualBox, attach the `.vdi` as a SATA hard disk and the seed ISO
as a CD-ROM. Use the `generic`/`genericcloud` image variants: Debian's
`nocloud` variant does not run Cloud-Init. Existing artifacts are never
overwritten unless `--force` is passed.

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
├── config.example.toml
├── src/qm_template/
│   ├── cli.py          # argument parsing and entry point
│   ├── commands.py     # download / create / prepare / distros commands
│   ├── config.py       # TOML settings and first-run config seeding
│   ├── checksum.py     # checksum parsing and verification
│   ├── cloudinit.py    # SSH key collection and seed user-data/meta-data
│   ├── config.default.toml  # default configuration shipped in the wheel
│   ├── download.py     # axel / aria2c / wget / curl wrappers
│   ├── http.py         # HTTP helpers, retries and directory listings
│   ├── images.py       # local image discovery
│   ├── log.py          # logging setup
│   ├── pve.py          # qm/pvesm integration and VM ID selection
│   ├── shell.py        # grouped command rendering and execution
│   ├── prepare.py      # qemu-img / genisoimage wrappers
│   └── distros/        # one module per distro family
└── tests/
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/qm-template/>.

## References

- [Proxmox VE Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Debian Cloud Images](https://cloud.debian.org/images/cloud/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
