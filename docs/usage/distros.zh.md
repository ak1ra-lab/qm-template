# 列出发行版

```shell
# 列出所有发行版、参数及每个参数的可选值
qm-template distros

# 查看单个发行版
qm-template distros debian
```

已配置的 `[distro.<name>]` 覆盖值会取代内置默认值显示：

```text
debian       Debian GNU/Linux
  release = trixie         choices: buster, bullseye, bookworm, trixie, forky (optionally with -backports)
  variant = genericcloud   choices: generic, genericcloud
  arch = amd64             choices: amd64, arm64
  tag = -                  dated build; the newest is used when omitted
  base_url = https://cdimage.debian.org/images/cloud upstream or mirror base URL; config file only
```

## 支持的发行版

`qm-template distros` 是最权威的列表，包含每个参数的可选值。`--tag` 用于固定具体
构建，只有声明了该参数的发行版才接受（Debian、Fedora、Arch Linux 和 Amazon Linux
2023），对其他发行版使用会报错。默认值如下：

| 名称          | 默认 release   | 默认 variant   | 说明                                          |
| ------------- | -------------- | -------------- | --------------------------------------------- |
| `debian`      | `trixie`       | `genericcloud` | `--release` 支持 `-backports`                 |
| `ubuntu`      | `resolute`     | `server`       | 也支持 `minimal` 变体                         |
| `rocky`       | `10`           | `GenericCloud` | 另有 `GenericCloud-LVM` 变体                  |
| `almalinux`   | `10`           | `GenericCloud` | 另有 `GenericCloud-ext4` 变体                 |
| `fedora`      | `44`           | `Generic`      | 另有 `UEFI-UKI` 变体                          |
| `centos`      | `10`           | -              | CentOS Stream                                 |
| `alpine`      | `3.24`         | `generic`      | `--firmware auto/bios/uefi`；Cloud-Init       |
| `opensuse`    | `tumbleweed`   | -              | `--release 15.6` 选择 Leap                    |
| `archlinux`   | 最新构建       | -              | 用 `--tag` 选择构建                           |
| `freebsd`     | `15.1`         | -              | `.xz` 归档；`--fs ufs`/`zfs`                  |
| `amazonlinux` | 最新版本       | -              | AL2023；用 `--tag` 选择版本                   |

每个参数都在 `[distro.<name>]` 下配置，大多数也有对应的 `download` 选项；见
[配置](../configuration.md)。
