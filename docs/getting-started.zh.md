# 入门指南

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- Proxmox VE 主机，通常以 root 身份运行；或通过 API 访问的远程主机
  （Proxmox VE >= 8.4），配合 `create --pve` 使用
- `create` 在未使用 `--pve` 时需要 Proxmox VE（`qm`、`pvesm`）
- `download` 命令需要 `axel`、`aria2c`、`wget` 或 `curl` 之一
- 签名校验需要 `gpg`；Ubuntu、Fedora、Rocky、AlmaLinux、openSUSE、Alpine 和
  Arch Linux 提供已签名元数据
- `prepare` 命令需要 `qemu-img` 以及 `genisoimage`、`xorriso`、`mkisofs` 之一

## 安装

以 uv tool 方式安装 CLI：

```shell
uv tool install qm-template
```

从源码安装：

```shell
uv tool install .
```

## 快速开始

```shell
# 下载并校验 cloud image
qm-template download debian

# 在本机 Proxmox VE 主机上创建模板
qm-template create --vm-id 9000

# 或通过 API 在远程主机上创建
qm-template create debian-13 --pve home

# 为其他 hypervisor 转换镜像并生成 NoCloud seed ISO
qm-template prepare debian-13
```

`download` 会解析最新构建，校验上游校验和与签名，并按 `paths.images_dir` 存放。
`create` 把镜像转换为模板：默认用本地 `qm`，加 `--pve` 则通过 Proxmox VE API 在
远程主机上创建。`prepare` 会在镜像旁写出转换后的磁盘和 `CIDATA` seed ISO。没有
配置文件时所有命令都能工作；可用设置见[配置](configuration.md)，各命令细节见
[使用](usage/download.md)。

## Shell 补全

补全由随 CLI 一起安装的 `argcomplete` 提供，每个 shell 启用一次即可：

```shell
# bash
eval "$(register-python-argcomplete qm-template)"

# zsh
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete qm-template)"
```

把对应行加入 `~/.bashrc`/`~/.zshrc`。补全覆盖命令名、选项以及按发行版的参数值；
每个发行版参数选项（`--release`、`--variant`、`--arch`、`--tag`、`--fs`、
`--firmware` 等）都会根据命令行中指定的发行版给出候选值，不支持某个参数的发行版
不会给出该参数的候选。`create --pve` 会补全 `[pve.<name>]` 中配置的主机名。

## 开发

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```

提交前的最终检查是 `uv run pre-commit run --all-files`。
