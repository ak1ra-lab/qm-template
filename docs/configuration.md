# Configuration

## Configuration file

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

## Settings

`download.preferred` orders the downloaders and `download.connections` sets the
number of parallel connections for `axel` and `aria2c`. Downloads show progress
by default; `download.quiet = true` or `-q`/`--quiet` hides it. Signed
checksums and images are verified with `gpg`; set
`download.verify_signature = false` to skip verification, for example when
gnupg is not installed. `prepare.preferred` orders the ISO builders and
defaults to `genisoimage`, `xorriso`, `mkisofs`.

`cloudinit.user` is the Cloud-Init login name; when empty the distro's usual
name is used (`debian`, `freebsd`, `ec2-user` for Amazon Linux, ...) and
`admin` is used when the image is not stored under a known distro directory.
`cloudinit.password` is optional: an empty password means no password login,
so SSH keys are required in that case. `cloudinit.sshkeys`/`sshkeys_files`
list inline SSH public keys and key files whose contents are merged and
deduplicated by key fingerprint; `create` and `prepare` require at least one
key or a password. The password is masked in `--dry-run` output and debug
logs. `cloudinit.shell` sets the login shell of the user created by the local
seed ISO (`prepare`); set it to `""` to keep the image's default shell, or to
`/bin/ash` on Alpine Linux. Cloud-Init itself can configure several users in
`user-data`, but Proxmox VE's managed Cloud-Init only exposes a single
`ciuser`/`cipassword` (multiple users would need custom `cicustom` snippets),
so `[cloudinit]` intentionally describes one user.

`create.storage` is the Proxmox storage for the imported disk and the
Cloud-Init drive. `create.cpu` sets the CPU type passed to `qm` as
`cputype=...` (default `host`, which is fast but prevents migration across CPU
generations). `create.firmware` (`auto`, `bios` or `uefi`) selects the
firmware; `auto` uses UEFI for images whose filename contains `uefi` (for
example Fedora's `UEFI-UKI` variant) and BIOS for everything else. UEFI
templates are created with `--bios ovmf` and an EFI disk
(`--efidisk0 <storage>:1,pre-enrolled-keys=0`, so Secure Boot stays disabled).
`create.tags`, `create.pool`, `create.onboot` and `create.description` add
optional Proxmox metadata to the template. `vmid.start` and `vmid.step`
(defaults `9000` and `1`) drive automatic VM ID selection. Add `-v` (debug
messages) or `-vv` (also log levels and timestamps) to any command for
troubleshooting.

## Remote Proxmox VE hosts

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

See [Create a template](usage/create.md#remote-proxmox-ve-hosts) for what the
remote mode requires on the Proxmox VE side.

## Per-distro overrides

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

`config.example.toml` in the repository is a symlink to the same file that is
shipped inside the wheel.
