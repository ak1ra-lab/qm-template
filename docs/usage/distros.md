# List distros

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

## Supported distros

`qm-template distros` is the authoritative list, including the accepted values
of every parameter. `--tag` pins a specific build and is accepted by the
distros that declare it (Debian, Fedora, Arch Linux and Amazon Linux 2023);
using it with any other distro is an error. Defaults:

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

Every parameter is configured under `[distro.<name>]` and most are also
available as `download` options; see
[Configuration](../configuration.md#per-distro-overrides).
