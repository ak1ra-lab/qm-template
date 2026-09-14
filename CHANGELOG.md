# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
