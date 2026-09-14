# Getting Started

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- A Proxmox VE host, normally running as root
- Proxmox VE (`qm`, `pvesm`) for the `create` command
- One of `axel`, `aria2c`, `wget` or `curl` for the `download` command

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
`/etc/qm-template/config.toml`. Use `--config PATH` or `QM_TEMPLATE_CONFIG` to
point elsewhere. Downloaded images are stored in `/var/lib/qm-template` unless
`paths.images_dir` overrides it, mirroring the upstream layout:

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` orders the downloaders and `download.connections` sets the
number of parallel connections for `axel` and `aria2c`. `create.sshkeys` lists
inline SSH public keys and `create.sshkeys_file` lists key files; the contents
of both are merged and deduplicated by key fingerprint for Cloud-Init. Start
from the example configuration:

```shell
install -d /etc/qm-template
cp qm-template.example.toml /etc/qm-template/config.toml
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
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed), so a newer build is downloaded
alongside the old one instead of overwriting it. Interrupted downloads are
resumed on the next run; partial files are stored as `<image>.part`. The
fetched checksum is saved next to the image as `<image>.sha256` or
`<image>.sha512`, depending on the upstream algorithm.

## Create a VM template

```shell
# interactive image and VM ID selection
qm-template create

# filter images with a regular expression on the relative path
qm-template create debian-13

# non-interactive
qm-template create --vm-id 9000 --vm-name debian-13-template

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

`create` requires a Proxmox VE host and runs a single
`qm create ... --template 1` command, which `--dry-run` pretty prints without
executing it.

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
