# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

A Python CLI that downloads cloud images, creates Proxmox VE VM templates and
prepares local VM artifacts, with Cloud-Init support.

## Features

- **Multi-distro downloads**: Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora,
  CentOS Stream, Alpine, openSUSE, Arch Linux, FreeBSD and Amazon Linux 2023
- **Checksum verification**: SHA-256/SHA-512 fetched from each distro's official
  checksum files and saved next to the image (`<image>.sha256`/`.sha512`)
- **GPG signature verification**: signed checksums (Ubuntu, Fedora, Rocky,
  AlmaLinux, openSUSE) and signed images (Alpine, Arch Linux) are verified with
  `gpg` against keys fetched from the distro's canonical source, with pinned
  fingerprints where upstream publishes a stable key; disable it with
  `download.verify_signature = false`
- **Compressed images**: FreeBSD ships `.xz` archives; they are checked against
  the upstream SHA-256 sums and extracted to `.qcow2` after download
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
  `qm set` calls, including optional tags, pool, onboot and description
- **Automatic VM IDs**: the next free ID is picked from `qm list` (or the
  Proxmox config directory), starting at `vmid.start` (default 9000)
- **Configurable CPU type**: `create.cpu`/`--cpu` overrides the default
  `cputype=host` when migration across CPU generations matters
- **Local VM artifacts**: `prepare` converts an image to VDI, VMDK, QCOW2, raw
  or VHDX with `qemu-img` and builds a NoCloud seed ISO (user-data, meta-data
  and a DHCP network-config) with the first available of `genisoimage`,
  `xorriso` or `mkisofs`, both written next to the source image; SSH keys are
  optional, so the seed can rely on password login alone
- **Validated TOML configuration**: settings and per-distro overrides are
  validated with `pydantic-settings` (unknown keys are rejected with a hint),
  optional `[distro.<name>]` overrides, and `QM_TEMPLATE_*` environment
  variables that take precedence over the file
- **Shell completion**: `argcomplete` completes commands, options and
  per-distro parameter values
- **Discoverable distro parameters**: `qm-template distros` lists every
  parameter with its default and accepted values; `qm-template distros debian`
  describes a single distro
- **Mirror-friendly**: point any distro at an upstream or mirror through
  `[distro.<name>] base_url`, including the checksum file and its signature
- **Configuration template**: `qm-template config` prints a commented
  starting-point configuration and `--full` adds the per-distro default tables;
  the file is never written automatically
- **Verbose logging**: `-v` adds debug messages and `-vv` also prefixes log
  levels and timestamps

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) to install and develop
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command
- `gpg` for signature verification (Ubuntu, Fedora, Rocky, AlmaLinux,
  openSUSE, Alpine and Arch Linux); set `download.verify_signature = false` to
  skip it
- `qemu-img` and one of `genisoimage`, `xorriso` or `mkisofs` for the
  `prepare` command

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
`/etc/qm-template/config.toml` when it exists; use `--config PATH`/`-c` or
`QM_TEMPLATE_CONFIG` to point elsewhere. All commands work without a
configuration file. Settings are validated with `pydantic-settings`; unknown
keys and invalid values are rejected with the file and key path in the error.
Every setting can also be overridden with a `QM_TEMPLATE_*` environment
variable that uses `__` for nesting, for example
`QM_TEMPLATE_DOWNLOAD__CONNECTIONS=4`; environment variables take precedence
over the file, and command-line options take precedence over both. Downloaded
images are stored in `/var/lib/qm-template` unless `paths.images_dir`
overrides it, mirroring the upstream layout:

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` orders the downloaders and `download.connections` sets the
number of parallel connections for `axel` and `aria2c`. Downloads show progress
by default; set `download.quiet = true` or pass `-q`/`--quiet` to hide it.
Signed checksums and images are verified with `gpg` unless
`download.verify_signature = false`. `cloudinit.user`/`password` configure the
Cloud-Init user, and `cloudinit.sshkeys`/`sshkeys_files` list inline SSH public
keys and key files whose contents are merged and deduplicated by fingerprint;
`create` requires at least one key, while `prepare` can fall back to password
login. `create.cpu` sets the CPU type passed as `cputype=...` (default `host`),
`create.tags`/`pool`/`onboot`/`description` add optional Proxmox metadata, and
`vmid.start`/`vmid.step` drive automatic VM ID selection (default `9000` and
`1`). `prepare.preferred` orders the ISO builders and defaults to
`genisoimage`, `xorriso`, `mkisofs`. Add `-v` (debug messages) or `-vv` (also
log levels and timestamps) to any command for troubleshooting. Optional
`[distro.<name>]` overrides are not written to the generated file:

```toml
[distro.debian]
release = "bookworm-backports"
arch = "arm64"
base_url = "https://mirror.example.org/debian-cloud"
```

`qm-template distros` lists every parameter with its default and accepted
values; each parameter is validated per distro and also has a `download`
command-line option (for example `--release`, `--fs` or `--firmware`), except
`base_url`, which is configuration-only. Passing an option a distro does not
declare is an error.

`base_url` points a distro at an upstream or mirror that mirrors the expected
directory layout; the checksum file and its signature are fetched from the same
base. Upstream signatures are verified against keys fetched from the distro's
canonical source (never from the mirror), and the expected fingerprints are
pinned where upstream publishes stable keys. Debian, CentOS Stream and FreeBSD
do not sign their cloud image metadata, and Amazon Linux signs its checksums
with RSA, which `qm-template` does not verify yet; for those a mirror serves
both the image and its checksum, so use a trusted mirror if authenticity
matters.

Print a starting-point configuration to stdout and redirect it; the file is
never written automatically:

```shell
install -d /etc/qm-template
qm-template config > /etc/qm-template/config.toml

# also append the per-distro default tables
qm-template config --full > /etc/qm-template/config.toml
```

Shell completion is provided by `argcomplete`; enable it once per shell:

```shell
eval "$(register-python-argcomplete qm-template)"   # bash; zsh needs bashcompinit
```

## Usage

### Download a cloud image

```shell
# default distro from the configuration file
qm-template download

# pick a distro, optionally override parameters
qm-template download debian
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594
qm-template download freebsd --fs zfs
qm-template download alpine --firmware uefi

# print the first available downloader's command without running it
qm-template download -n alpine

# hide the downloader progress output
qm-template download -q alpine

# list distros with the values each parameter accepts
qm-template distros

# print a commented starting-point configuration
qm-template config > config.toml
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed) and Amazon Linux 2023 resolves and
pins its current version: the newest build is selected, and a
newer build is downloaded alongside the old one instead of overwriting it.
FreeBSD images are distributed as `.xz` archives: the archive is verified
against the upstream SHA-256 sums, extracted to `.qcow2` and removed, with a
local checksum sidecar so later runs detect an up-to-date image without
downloading it again.
Interrupted downloads are resumed on the next run; partial files are stored as
`<image>.part`. A failed download is retried from scratch with the same
downloader and never switches to another one; a completed download that fails
checksum verification is downloaded once more from scratch before the command
fails. Checksum files and directory listings are retried with exponential
backoff on transient 5xx and network errors. Where upstream provides a signed
checksum file (or a signed image, for Alpine and Arch Linux) the signature is
verified with `gpg` before it is trusted; the signing key is fetched from the
distro's canonical source with pinned fingerprints, so a mirror cannot forge
it. The checksum fetched from the upstream source is saved next to the image as
`<image>.sha256` or `<image>.sha512`, depending on the upstream algorithm.

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

# attach Proxmox metadata
qm-template create --tags template,cloud --pool templates --onboot

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

When `--vm-id` is omitted, `qm-template` collects the IDs in use from
`qm list` combined with `/etc/pve/qemu-server/*.conf` and picks the first
free ID at or after `vmid.start` (default `9000`), advancing by `vmid.step`
(default `1`); the 9000+ range keeps templates away from regular VMs. If
`qm create` fails, an existing but incomplete VM config is reported with the
`qm destroy` command needed to clean it up.

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
    --sshkeys /tmp/qm-template-sshkeys-XXXX.pub \
    --template 1
```

### Prepare local VM artifacts

Most hypervisors cannot boot `.qcow2` directly, so guest disks have to be
converted. The hypervisor-agnostic `prepare` command selects a downloaded
image, converts it to a guest disk with `qemu-img` and packs a NoCloud seed
into a `CIDATA`-labelled ISO with the first available of `genisoimage`,
`xorriso` or `mkisofs`: `user-data`/`meta-data` built from the `[cloudinit]`
settings plus a DHCP `network-config` (needed because Debian cloud images do
not fall back to a generated network configuration). Both artifacts are written
next to the source image and only differ in suffix:

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
`nocloud` variant does not run Cloud-Init. Without configured SSH keys the seed
only enables password login (with a warning); `create`, by contrast, still
requires keys. An existing guest disk is kept and only the seed ISO is rebuilt,
since converting is expensive and the seed derives from the `[cloudinit]`
settings; pass `--force`/`-f` to convert again.

## Supported distros

`qm-template distros` is the authoritative list, including the accepted values
of every parameter. `--tag` pins a specific build and is accepted by the distros
that declare it (Debian, Fedora, Arch Linux and Amazon Linux 2023); using it
with any other distro is an error. Defaults:

| Name          | Default release | Default variant | Notes                                        |
| ------------- | --------------- | --------------- | -------------------------------------------- |
| `debian`      | `trixie`        | `genericcloud`  | `--release` accepts `-backports`             |
| `ubuntu`      | `resolute`      | `server`        | variant `minimal` also supported             |
| `rocky`       | `10`            | `GenericCloud`  | variant `GenericCloud-LVM`                   |
| `almalinux`   | `10`            | `GenericCloud`  | variant `GenericCloud-ext4`                  |
| `fedora`      | `44`            | `Generic`       | variant `UEFI-UKI`                           |
| `centos`      | `10`            | -               | CentOS Stream                                |
| `alpine`      | `3.24`          | `generic`       | `--firmware auto/bios/uefi`; Cloud-Init      |
| `opensuse`    | `tumbleweed`    | -               | `--release 15.6` for Leap                    |
| `archlinux`   | newest build    | -               | pick a build with `--tag`                    |
| `freebsd`     | `15.1`          | -               | `.xz` archive; `--fs ufs`/`zfs`              |
| `amazonlinux` | newest version  | -               | AL2023; pick a version with `--tag`          |

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
│   ├── cli.py          # argument parsing, completion and entry point
│   ├── commands.py     # download / create / prepare / distros / config commands
│   ├── config.py       # pydantic-settings models and configuration loading
│   ├── checksum.py     # checksum parsing and verification
│   ├── cloudinit.py    # SSH key collection and seed user-data/meta-data
│   ├── config.default.toml  # default configuration shipped in the wheel
│   ├── download.py     # axel / aria2c / wget / curl wrappers
│   ├── http.py         # HTTP helpers, retries and directory listings
│   ├── images.py       # local image discovery
│   ├── log.py          # logging setup
│   ├── pve.py          # qm/pvesm integration and VM ID selection
│   ├── shell.py        # grouped command rendering and execution
│   ├── signature.py    # gpg signature verification of checksums and images
│   ├── prepare.py      # qemu-img / genisoimage / xorriso / mkisofs wrappers
│   └── distros/        # one module per distro family
└── tests/
```

## Documentation

The published documentation site lives at <https://ak1ra-lab.github.io/qm-template/>.

## References

- [Proxmox VE Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Debian Cloud Images](https://cloud.debian.org/images/cloud/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
