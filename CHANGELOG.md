# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `cloudinit.user` defaults to empty: the Cloud-Init login name is derived
  from the image's distro (Debian stays `debian`, FreeBSD becomes `freebsd`,
  Amazon Linux `ec2-user`, ...) and falls back to `admin` when the image is
  not stored under a known distro directory.
- `cloudinit.password` defaults to empty: no password login is configured
  unless one is set. `create` and `prepare` now both require at least one SSH
  key or a password, and unset `--cipassword`/`--sshkeys` options are omitted
  from the `qm create` command and the API request.

### Security

- Passwords and SSH public keys are masked as `********` in `--dry-run`
  previews, and passwords are masked in debug logs as well.

## [0.5.0] - 2026-09-16

### Added

- Add remote Proxmox VE API support: `create --pve <name>` creates the
  template on a remote host through its API (Proxmox VE >= 8.4) instead of
  running `qm` locally, so several hosts can be managed from one workstation.
  A `[pve.<name>]` section holds `host`, `user`, `token_name`, `token_secret`,
  `import_storage` and optional `node`, `verify_ssl`, `port`, `timeout` and
  `task_timeout`, and nested `[pve.<name>.create]`, `[pve.<name>.vmid]` and
  `[pve.<name>.cloudinit]` tables override the global sections for that host.
  Images are uploaded with the `import` content type (skipped when the same
  name and size already exists), imported with `import-from`, and an
  incomplete VM is removed again when creation fails. VM IDs are requested
  from the cluster while `vmid.start`/`vmid.step` still apply, and `--dry-run`
  prints the upload and create requests. The token secret can be kept out of
  the file with `QM_TEMPLATE_PVE__<NAME>__TOKEN_SECRET`; `create --pve`
  completes the configured host names.

### Changed

- Depend on `proxmoxer` (with `requests` and `requests-toolbelt`) for remote
  API mode.
- Split the documentation into Getting Started, Configuration and per-command
  Usage pages and add a Simplified Chinese README; the README is now a short
  overview that links to the documentation site.

## [0.4.0] - 2026-09-16

### Added

- Add FreeBSD (`freebsd`) VM images: `fs` selects `ufs` or `zfs`, `arch`
  supports `amd64` and `aarch64`, and only the `BASIC-CLOUDINIT` images are
  offered because `create` and `prepare` require Cloud-Init. FreeBSD ships
  `.xz` archives; the archive is verified against the upstream
  `CHECKSUM.SHA256`, extracted to `.qcow2` and removed, with a local checksum
  sidecar so a later run detects the up-to-date image.
- Add Amazon Linux 2023 (`amazonlinux`): the newest version is used when `tag`
  is omitted, otherwise `tag` pins a version like `2023.12.20260914.0`; `arch`
  supports `x86_64` and `aarch64`, and the checksum comes from the version's
  `SHA256SUMS`. Amazon's RSA-signed `SHA256SUMS` is not verified yet, only the
  HTTPS checksum.
- Add `firmware` (`auto`, `bios` or `uefi`) to the Alpine parameters; `auto`
  selects BIOS on `x86_64`, UEFI on `aarch64`, and the resulting filename makes
  `create` choose the matching Proxmox firmware.
- Verify upstream GPG signatures when downloading: Ubuntu, Fedora, Rocky Linux,
  AlmaLinux and openSUSE provide signed checksum files (Fedora clearsigned,
  the rest detached), while Alpine and Arch Linux sign the image itself.
  Signing keys are fetched from each distro's canonical source (never from the
  configured mirror) and pinned fingerprints are checked where upstream
  publishes a stable key; Debian and CentOS Stream provide no signatures and
  are skipped. Set `download.verify_signature = false` to skip verification,
  for example when gnupg is not installed.
- Add `-v`/`--verbose` to every command: `-v` enables debug messages and
  `-vv` also prefixes the log level and timestamp.
- Add `create.tags`, `create.pool`, `create.onboot` and `create.description`
  with the `--tags`, `--pool`, `--onboot`/`--no-onboot` and `--description`
  options to attach Proxmox metadata to the created template.
- Add `prepare.preferred` to choose the seed ISO builder; `prepare` now uses
  the first available of `genisoimage`, `xorriso` or `mkisofs` instead of
  requiring `genisoimage`.
- Allow `prepare` to run without SSH keys: the seed then only enables password
  login and a warning is logged. `create` still requires at least one key.

### Changed

- Drive the download CLI and the `[distro.<name>]` configuration from each
  distro's declared options: every option (for example FreeBSD's `fs` and
  Alpine's `firmware`) is now configurable both in the configuration file and
  through a matching command-line flag, with per-distro validation and
  completion. `base_url` remains configuration-only. Free-form values such as
  Alpine's release series or Amazon's version are validated against a pattern
  before any network access.
- Select a build or version with `tag` for Arch Linux and Amazon Linux 2023
  instead of overloading `release` with a `latest` sentinel; omitting `tag`
  keeps resolving the newest one. `--tag` is accepted by every distro that
  declares the parameter.
- Reject unsupported `[distro.<name>]` keys and values with the distro's own
  parameter list, and accept arbitrary declared parameters instead of a fixed
  five-key set.

### Removed

- Remove the FreeBSD `variant` parameter: only the upstream `BASIC-CLOUDINIT`
  images are supported, so the no-Cloud-Init images can no longer be selected
  by mistake.
- Remove the single-choice `variant` parameters of CentOS Stream, openSUSE and
  Arch Linux; they were constants rather than knobs. Arch Linux now selects the
  build with `tag`.

## [0.3.2] - 2026-09-16

### Fixed

- Report `qm` and `pvesm` start-up failures without a Python traceback when
  the command disappears between detection and execution; `qm list` and
  `pvesm status` keep their best-effort fallbacks.

## [0.3.1] - 2026-09-15

### Added

- Add `create.firmware` and `--firmware` (`auto`, `bios` or `uefi`) to
  `qm-template create`; `auto` uses UEFI for images whose filename contains
  `uefi` (for example Fedora's `UEFI-UKI` variant) and creates them with
  `--bios ovmf` and an EFI disk, while BIOS templates are unchanged.
- Add `cloudinit.shell` to set the login shell of the user created by the
  `prepare` seed; the default stays `/bin/bash` and an empty value keeps the
  image default, so Alpine images without bash can be prepared too.

### Removed

- Remove the `basic` variant from the Arch Linux parameters; only `cloudimg`
  ships Cloud-Init.

### Fixed

- Fix Alpine Linux `aarch64` resolution: upstream provides only UEFI images
  for `aarch64`, so the resolver now selects `bios` for `x86_64` and `uefi`
  for `aarch64` instead of always requiring `bios`.

## [0.3.0] - 2026-09-15

### Added

- Add `qm-template prepare` to build local VM artifacts from a downloaded
  image: `qemu-img` converts it to a guest disk (`--format vdi` (default),
  `vmdk`, `qcow2`, `raw` or `vhdx`) and a NoCloud seed with `user-data`,
  `meta-data` and a DHCP `network-config` is packed into a `CIDATA`-labelled
  ISO with `genisoimage`. Both artifacts are written next to the source image
  with the same stem (`<image>.qcow2` becomes `<image>.vdi` and
  `<image>.iso`); an existing guest disk is kept unless `--force` is passed,
  while the seed ISO is rebuilt on every run. `--vm-name` and `--dry-run` are
  also supported.
- Add `qm-template config` to print a commented starting-point configuration
  to stdout; `--full` appends the per-distro default tables. The configuration
  file is optional and never written automatically.
- Validate settings with `pydantic-settings`: unknown keys and invalid values
  are reported with the file and key path, moved keys get a migration hint,
  and `QM_TEMPLATE_*` environment variables (nested with `__`) override the
  file.
- List every distro parameter with its default and accepted values in
  `qm-template distros`, and describe a single distro with
  `qm-template distros <name>`.
- Allow pointing a distro at an upstream or mirror with the `base_url`
  parameter in `[distro.<name>]`; the checksum file is fetched from the same
  base.
- Complete commands, options and per-distro parameter values with
  `argcomplete`, and add the short options `-c/--config`, `-V/--version`,
  `-n/--dry-run`, `-q/--quiet` and `-f/--force`.

### Changed

- Change the configuration layout (breaking): move the Cloud-Init settings out
  of `[create]` into a top-level `[cloudinit]` section and drop the redundant
  `ci` prefix (`user`, `password`, `sshkeys`, `sshkeys_files`); move the
  per-distro overrides from `[download.<distro>]` to `[distro.<distro>]` and
  stop including them in the generated default configuration; move automatic
  VM ID selection from `create.start_id`/`create.step` to
  `vmid.start`/`vmid.step`.
- Validate distro parameter values against the values each distro accepts
  instead of failing later while resolving the image URL, and reject `--tag`
  with an error for distros that do not support it instead of warning and
  ignoring it.
- Stop writing `/etc/qm-template/config.toml` on the first run; every command
  works without a configuration file.
- Depend on `pydantic-settings` and `argcomplete`; the CLI is no longer
  standard-library-only.

### Removed

- Remove the `qm-template images` command and its `--prune`/`--dry-run`/`--yes`
  options; `tree -h <images_dir>` shows the same local inventory.

### Fixed

- Never switch to the next configured downloader after a failure: the first
  available downloader is kept and retried from scratch instead, matching the
  documented "first available command is used" behavior.

## [0.2.0] - 2026-09-14

### Added

- Add `qm-template images` to list local images with their size and checksum
  sidecar; `--prune` removes older builds whose names differ only in
  dates/versions, their sidecars and orphaned checksum files, `--dry-run` only
  lists the affected files and `--yes` skips the confirmation prompt.
- Choose the next free VM ID automatically from `qm list`, falling back to
  `/etc/pve/qemu-server/*.conf`; `create.start_id` (default 9000) sets the first
  candidate, `create.step` sets the increment and `--vm-id` still forces a
  specific ID.
- Set the CPU type with `create.cpu` or `--cpu`, passed as `cputype=...`
  (default `host`, as before).
- Hide downloader progress output with `download.quiet` or
  `--quiet`/`--no-quiet`.
- Retry checksum files and directory listings with exponential backoff on
  transient network and 5xx errors.

### Changed

- Show downloader progress by default: aria2c no longer runs with
  `--console-log-level=warn --summary-interval=0`, while wget and curl keep
  their progress bars unless `--quiet` is used.
- Download an image once more from scratch when it passes the downloaders but
  fails checksum verification.
- Report the `qm destroy` command needed to clean up an incomplete VM left
  behind by a failed `qm create`.

## [0.1.0] - 2026-09-14

### Added

- `qm-template download` resolves, downloads and verifies cloud images for
  Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora, CentOS Stream, Alpine,
  openSUSE and Arch Linux.
- Fetched checksums are saved next to each image as `<image>.sha256` or
  `<image>.sha512`, depending on the upstream algorithm.
- Images mirror the upstream layout as `<distro>/<release>/[<tag>/]<filename>`
  and are pinned to the newest dated build where the upstream provides one
  (Debian, Ubuntu server, Arch Linux, openSUSE Tumbleweed).
- Downloads use the first available command from `download.preferred` (`axel`,
  `aria2c`, `wget` or `curl`); `download.connections` sets the number of
  parallel connections for `axel` and `aria2c`.
- `qm-template create` assembles a single `qm create ... --template 1` command
  that builds a Proxmox VE VM template with Cloud-Init.
- `qm-template distros` lists the supported distros and their configured
  defaults.
- Optional TOML configuration is loaded from `/etc/qm-template/config.toml`,
  overridable with `--config` or `QM_TEMPLATE_CONFIG`, and downloaded images
  are stored in `/var/lib/qm-template` by default. Unknown configuration keys
  are rejected while the file is parsed.
- The default configuration is shipped in the package and written to
  `/etc/qm-template/config.toml` on first run when the file does not exist;
  paths given with `--config` or `QM_TEMPLATE_CONFIG` are never created
  implicitly.
- SSH public keys for Cloud-Init can be set inline with `create.sshkeys` and
  via the `create.sshkeys_files` key-file list. The contents of both are merged
  and deduplicated by SSH key fingerprint, inline entries are validated while
  the configuration is parsed, and at least one key is required.
- `--dry-run` pretty prints the command that would run: `download` shows the
  first available downloader's command and `create` shows the assembled
  `qm create` invocation, one argument group per line.
