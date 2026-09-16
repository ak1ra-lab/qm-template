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

## Configuration

The configuration file is optional and loaded from
`/etc/qm-template/config.toml` when it exists; use `--config PATH`/`-c` or
`QM_TEMPLATE_CONFIG` to point elsewhere. All commands work without a
configuration file. Settings are validated with `pydantic-settings`; unknown
keys and invalid values are rejected with the file and key path in the error.
Every setting can also be overridden with a `QM_TEMPLATE_*` environment
variable that uses `__` for nesting, for example
`QM_TEMPLATE_DOWNLOAD__CONNECTIONS=4`; environment variables take precedence
over the file, and command-line options take precedence over both.

Downloaded images are stored in `/var/lib/qm-template` unless
`paths.images_dir` overrides it, mirroring the upstream layout:

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` orders the downloaders and `download.connections` sets the
number of parallel connections for `axel` and `aria2c`. Downloads show progress
by default; `download.quiet = true` or `-q`/`--quiet` hides it. Signed
checksums and images are verified with `gpg`; set
`download.verify_signature = false` to skip verification, for example when
gnupg is not installed. `prepare.preferred` orders the ISO builders and
defaults to `genisoimage`, `xorriso`, `mkisofs`.
`cloudinit.user`/`password` configure the Cloud-Init user, and
`cloudinit.sshkeys`/`sshkeys_files` list inline SSH public keys and key files
whose contents are merged and deduplicated by key fingerprint; `create`
requires at least one key, while `prepare` falls back to password login when
none is configured. `cloudinit.shell` sets the login shell of the user created
by the local seed ISO (`prepare`); set it to `""` to keep the image's default
shell, or to `/bin/ash` on Alpine Linux. `create.cpu` sets the CPU type passed
to `qm` as `cputype=...` (default `host`, which is fast but prevents migration
across CPU generations). `create.firmware` (`auto`, `bios` or `uefi`) selects
the firmware; `auto` uses UEFI for images whose filename contains `uefi` (for
example Fedora's `UEFI-UKI` variant) and BIOS for everything else. UEFI
templates are created with `--bios ovmf` and an EFI disk
(`--efidisk0 <storage>:1,pre-enrolled-keys=0`, so Secure Boot stays disabled).
`create.tags`, `create.pool`, `create.onboot` and `create.description` add
optional Proxmox metadata to the template. `vmid.start` and `vmid.step`
(defaults `9000` and `1`) drive automatic VM ID selection. Add `-v` (debug
messages) or `-vv` (also log levels and timestamps) to any command for
troubleshooting.

Optional `[pve.<name>]` sections describe remote Proxmox VE hosts for
`create --pve <name>`. They need `host`, `user`, `token_name` and
`token_secret`, plus `import_storage` to upload images; `node` is required on
clusters with more than one node, and `verify_ssl`, `port`, `timeout` and
`task_timeout` have sensible defaults. Nested `[pve.<name>.create]`,
`[pve.<name>.vmid]` and `[pve.<name>.cloudinit]` tables override the global
sections for that host only. Keep the token secret out of the file with
`QM_TEMPLATE_PVE__<NAME>__TOKEN_SECRET`, and make the file owner-readable only:

```toml
[pve.home]
host = "pve.home.arpa"
user = "qm-template@pve"
token_name = "automation"
token_secret = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
import_storage = "local"

[pve.home.vmid]
start = 9000
```

Per-distro overrides are optional and live under `[distro.<name>]`. They are
not included in the default configuration printed by `qm-template config`; add
them only when a distro should use something other than its built-in default:

```toml
[distro.debian]
release = "bookworm-backports"
arch = "arm64"
base_url = "https://mirror.example.org/debian-cloud"
```

Every parameter listed by `qm-template distros` is validated per distro and is
also exposed as a command-line option for `download` (for example `--release`,
`--variant`, `--fs` or `--firmware`); passing an option a distro does not
declare is an error. `base_url` is the exception: it is configuration-only.

`base_url` points a distro at an upstream or mirror that mirrors the expected
directory layout; the checksum file and its signature are fetched from the same
base. Where upstream signs its metadata (Ubuntu, Fedora, Rocky, AlmaLinux,
openSUSE, Alpine and Arch Linux) the signature is verified with `gpg` before
the checksum is trusted, and the signing keys are fetched from the distro's
canonical source - never from the mirror - with pinned fingerprints where
upstream publishes stable keys. Debian, CentOS Stream and FreeBSD do not sign
their cloud image metadata, and Amazon Linux's RSA signature is not verified
yet; for those a mirror serves both the image and its checksum, so use a
trusted mirror, or verify the checksum out of band, when authenticity matters.

`qm-template distros` shows every parameter with its default and accepted
values, and `qm-template distros debian` describes a single distro.

## Generate a configuration file

`qm-template config` prints the default configuration (with comments) to
stdout; redirect it to create a starting point. `--full` also appends the
per-distro default tables. The file is never written automatically:

```shell
install -d /etc/qm-template
qm-template config > /etc/qm-template/config.toml

# pin every distro parameter explicitly
qm-template config --full > /etc/qm-template/config.toml
```

`config.example.toml` in the repository is the same file as the plain
`qm-template config` output.

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

## Download an image

```shell
# default distro from the configuration file
qm-template download

# pick a distro, optionally override parameters
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# print the first available downloader's command without running it
qm-template download -n alpine

# hide the downloader progress output
qm-template download -q alpine
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading anything.
Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed), and Amazon Linux 2023 resolves
`/latest/` to the current version and pins it, so a newer build is downloaded
alongside the old one instead of overwriting it. FreeBSD images are distributed
as `.xz` archives: the archive is verified, extracted to `.qcow2` and removed,
and a local checksum sidecar lets later runs detect the up-to-date image. `--tag`
pins a specific upstream build and is accepted by the distros that declare it
(Debian, Fedora, Arch Linux and Amazon Linux 2023; `qm-template distros` lists
them). Alpine images can be downloaded for BIOS or UEFI with `--firmware`
(`auto` follows the architecture), and the resulting filename makes `create`
pick the matching Proxmox firmware. Interrupted downloads are
resumed on the next run; partial files are stored as `<image>.part`. A failed
download is retried from scratch with the same downloader and never switches to
another one; a completed download that fails checksum verification is downloaded
once more from scratch before the command fails. Checksum files and directory
listings are retried with exponential backoff on transient 5xx and network
errors. Where upstream provides signed metadata - a signed checksum file for
Ubuntu, Fedora, Rocky, AlmaLinux and openSUSE, a signed image for Alpine and
Arch Linux - the signature is verified with `gpg` before the download is
trusted; keys are fetched from the distro's canonical source and pinned
fingerprints are checked where upstream publishes stable keys. Debian, CentOS
Stream and FreeBSD ship no cloud image signatures, and Amazon Linux's RSA
signature is not verified yet. The fetched checksum is saved next to the image
as `<image>.sha256` or `<image>.sha512`, depending on the upstream algorithm.

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

# override the firmware auto-detected from the image name
qm-template create --firmware uefi

# attach Proxmox metadata
qm-template create --tags template,cloud --pool templates --onboot

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

`create` requires a Proxmox VE host and runs a single
`qm create ... --template 1` command, which `--dry-run`/`-n` pretty prints
without executing it. When `--vm-id` is omitted, the IDs in use are collected
from `qm list` combined with `/etc/pve/qemu-server/*.conf` and the first
free ID at or after `vmid.start` (default `9000`), advancing by `vmid.step`, is
used. If `qm create` fails after leaving a VM config behind, the `qm destroy`
command needed to clean it up is reported.

## Remote Proxmox VE hosts

With `--pve NAME`, `create` talks to the Proxmox VE API instead of running
`qm`, so a single workstation can manage several hosts without installing
`qm-template` or downloading images on them:

```shell
qm-template create debian-13 --pve home --vm-name debian-13-template

# print the API requests instead of executing them
qm-template create debian-13 --pve home --dry-run
```

API mode requires Proxmox VE 8.4 or newer. The image is uploaded to the host's
`import_storage` with `content=import` and imported with
`scsi0=<create.storage>:0,import-from=<import_storage>:import/<file>`; an
uploaded file with the same name and size is reused, so repeat runs skip the
transfer. The image name is flattened from the path below `paths.images_dir`
and the format is detected from the file itself, so Ubuntu's `.img` images are
accepted. VM IDs come from the cluster (`GET /cluster/nextid`), and
`vmid.start`/`vmid.step` still apply. When creation fails, the incomplete VM is
removed again. `--dry-run` prints the upload and `POST
/api2/json/nodes/<node>/qemu` requests (the password stays visible, like the
local `qm create` command).

Prepare the remote host once:

- create a user and API token that may allocate VMs:

  ```shell
  pveum user add qm-template@pve
  pveum acl modify / --users qm-template@pve --roles PVEAdmin
  pveum user token add qm-template@pve automation --privsep 0
  ```

  Token permissions are limited to the user's own permissions; a narrower
  custom role works too, but creating a VM touches several privileges
  (`VM.Allocate`, `VM.Config.*`, `Datastore.AllocateSpace` and
  `Datastore.AllocateTemplate` for the upload). Privilege separation is on by
  default, so without `--privsep 0` a new token has no permissions of its own
  and needs a separate ACL entry
  (`pveum acl modify / --tokens 'qm-template@pve!automation' --roles PVEAdmin`).
- enable the `import` content type on a file-based storage (Datacenter ->
  Storage -> your storage -> Edit -> Content) and point `import_storage` at
  it. LVM/ZFS storages cannot hold import content; `create.storage` (for
  example `local-lvm`) remains the target for the VM disk and Cloud-Init
  drive. Import storage needs Proxmox VE 8.4+.
- set `verify_ssl = false` (or trust the PVE CA) when the host still uses its
  self-signed certificate.

Hosts older than 8.4 keep working with the default local mode.

## Prepare local VM artifacts

Most hypervisors cannot boot `.qcow2` directly, so guest disks have to be
converted. The hypervisor-agnostic `prepare` command picks a downloaded image,
converts it to a guest disk with `qemu-img` and packs a NoCloud seed into a
`CIDATA`-labelled ISO with the first available of `genisoimage`, `xorriso` or
`mkisofs`: `user-data`/`meta-data` built from the `[cloudinit]` settings plus a
DHCP `network-config` (needed because Debian cloud images do not fall back to a
generated network configuration). Both artifacts are written next to the source
image and only differ in suffix:

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
run Cloud-Init. SSH keys are optional for `prepare`: without them a warning is
logged and the seed only enables password login (`create` still requires keys).
An existing guest disk is kept and only the seed ISO is rebuilt, since
converting is expensive and the seed derives from the `[cloudinit]` settings;
pass `--force`/`-f` to convert again.

## List distros

```shell
# every distro, its parameters and the values each one accepts
qm-template distros

# one distro in detail
qm-template distros debian
```

Configured `[distro.<name>]` overrides are shown instead of the built-in
defaults:

```text
debian       Debian GNU/Linux
  release = trixie         choices: buster, bullseye, bookworm, trixie, forky (optionally with -backports)
  variant = genericcloud   choices: generic, genericcloud
  arch = amd64             choices: amd64, arm64
  tag = -                  dated build; the newest is used when omitted
  base_url = https://cdimage.debian.org/images/cloud upstream or mirror base URL; config file only
```

## Development

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```
