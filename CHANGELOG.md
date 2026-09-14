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
