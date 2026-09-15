# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

- Move the Cloud-Init settings out of `[create]` into a new top-level
  `[cloudinit]` section and drop the redundant `ci` prefix (`user`,
  `password`, `sshkeys`, `sshkeys_files`), since they are shared by `create`
  and `prepare`; `[create]` keeps the Proxmox-specific keys.

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
