# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `qm-template download` resolves, downloads and verifies cloud images for
  Debian, Ubuntu, Rocky Linux, AlmaLinux, Fedora, CentOS Stream, Alpine,
  openSUSE and Arch Linux.
- Fetched checksums are saved next to each image as `<image>.sha256` or
  `<image>.sha512`, depending on the upstream algorithm.
- Images mirror the upstream layout as `<distro>/<release>/[<tag>/]<filename>`
  and are pinned to the newest dated build where the upstream provides one
  (Debian, Ubuntu server, Arch Linux, openSUSE Tumbleweed).
- `axel` is supported and preferred as a downloader, and
  `download.connections` controls the number of parallel connections used by
  `axel` and `aria2c`.
- `qm-template create` assembles a single `qm create ... --template 1` command
  to build a Proxmox VE VM template.
- `qm-template distros` lists the supported distros and their configured
  defaults.
- Optional TOML configuration loaded from `/etc/qm-template/config.toml`,
  overridable with `--config` or `QM_TEMPLATE_CONFIG`. Downloaded images are
  stored in `/var/lib/qm-template` by default.
- SSH public keys for Cloud-Init can be set inline with `create.sshkeys` and
  via the `create.sshkeys_files` key-file list; the contents of both are merged
  and deduplicated by SSH key fingerprint. Inline entries are validated as SSH
  public keys when the configuration is parsed. At least one key is required
  and no key file is assumed by default.
- `--dry-run` pretty prints the command that would run: `download` shows the
  first available downloader's command and `create` shows the assembled
  `qm create` invocation, one argument group per line.
- The default configuration is packaged in the wheel and written to
  `/etc/qm-template/config.toml` on first run when the file does not exist;
  paths given with `--config` or `QM_TEMPLATE_CONFIG` are never created
  implicitly.
