# Getting Started

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command
- `qemu-img` and `genisoimage` for the `prepare` command

## Installation

Install the CLI as a uv tool:

```shell
uv tool install qm-template
```

From a checkout:

```shell
uv tool install .
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
by default; `download.quiet = true` or `--quiet` hides it.
`cloudinit.user`/`password` configure the Cloud-Init user, and
`cloudinit.sshkeys`/`sshkeys_files` list inline SSH public keys and key files
whose contents are merged and deduplicated by key fingerprint; at least one key
is required. `create.cpu` sets the CPU type passed to `qm` as `cputype=...`
(default `host`, which is fast but prevents migration across CPU generations).
`create.start_id` and `create.step` (defaults `9000` and `1`) drive automatic
VM ID selection. To create the file manually instead:

```shell
install -d /etc/qm-template
cp config.example.toml /etc/qm-template/config.toml
```

Command-line options override the configured defaults.

## Download an image

```shell
# default distro from the configuration file
qm-template download

# pick a distro, optionally override parameters
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# print the first available downloader's command without running it
qm-template download --dry-run alpine

# hide the downloader progress output
qm-template download --quiet alpine
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed), so a newer build is downloaded
alongside the old one instead of overwriting it. Interrupted downloads are
resumed on the next run; partial files are stored as `<image>.part`. A failed
download is retried from scratch with the same downloader and never switches to
another one; a completed download that fails checksum verification is downloaded
once more from scratch before the command fails. Checksum files and directory
listings are retried with exponential backoff on transient 5xx and network
errors. The fetched checksum is saved next to the image as `<image>.sha256` or
`<image>.sha512`, depending on the upstream algorithm.

## Create a VM template

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

`create` requires a Proxmox VE host and runs a single
`qm create ... --template 1` command, which `--dry-run` pretty prints without
executing it. When `--vm-id` is omitted, the IDs in use are collected from
`qm list` (falling back to `/etc/pve/qemu-server/*.conf`) and the first free ID
at or after `create.start_id` (default `9000`), advancing by `create.step`, is
used. If `qm create` fails after leaving a VM config behind, the `qm destroy`
command needed to clean it up is reported.

## Prepare local VM artifacts

Most hypervisors cannot boot `.qcow2` directly, so guest disks have to be
converted. The hypervisor-agnostic `prepare` command picks a downloaded image,
converts it to a guest disk with `qemu-img` and packs a NoCloud
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
extension follows the format. Choosing `qcow2` for a `.qcow2` source is
rejected because it would overwrite the source image. For VirtualBox, attach
the `.vdi` as a SATA hard disk and the seed ISO as a CD-ROM. Use the
`generic`/`genericcloud` image variants: Debian's `nocloud` variant does not
run Cloud-Init. Existing artifacts are never overwritten unless `--force` is
passed.

## List distros

```shell
qm-template distros
```

## Development

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```
