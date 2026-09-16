# qm-template

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/qm-template/.github%2Fworkflows/publish-to-pypi.yaml)](https://github.com/ak1ra-lab/qm-template/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/qm-template)](https://pypi.org/project/qm-template/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/qm-template/)

[English](README.md) | **简体中文**

一个 Python CLI，用于下载 cloud image、创建支持 Cloud-Init 的 Proxmox VE 虚拟机
模板，并准备本地虚拟机产物。

## 特性

- **多发行版下载**：Debian、Ubuntu、Rocky Linux、AlmaLinux、Fedora、
  CentOS Stream、Alpine、openSUSE、Arch Linux、FreeBSD 和 Amazon Linux 2023，
  支持固定构建、断点续传以及校验和/签名验证。
- **Proxmox VE 模板**：单条 `qm create ... --template 1` 命令，自动选择 VM ID，
  可配置 CPU、固件和元数据；或用 `create --pve <name>` 通过 API 在远程主机
  （Proxmox VE >= 8.4）上创建模板。
- **本地虚拟机产物**：`prepare` 可把镜像转换为 VDI、VMDK、QCOW2、raw 或 VHDX，
  并生成适用于任何 hypervisor 的 NoCloud seed ISO。
- **配置校验**：TOML 配置，支持可选的按发行版与按主机覆盖、`QM_TEMPLATE_*`
  环境变量，以及未知键拒绝。
- **Shell 补全**：命令、选项、按发行版参数和远程主机名均可补全。

## 快速开始

```shell
uv tool install qm-template

qm-template download debian                  # 下载并校验镜像
qm-template create --vm-id 9000              # 在本机 Proxmox VE 主机上创建模板
qm-template create debian-13 --pve home      # 或通过 API 在远程主机上创建
qm-template prepare debian-13 --format vmdk  # 为其他 hypervisor 生成磁盘和 seed ISO
```

## 文档

完整文档：<https://ak1ra-lab.github.io/qm-template/zh/>

- [入门指南](https://ak1ra-lab.github.io/qm-template/zh/getting-started/)
- [配置](https://ak1ra-lab.github.io/qm-template/zh/configuration/)
- [使用](https://ak1ra-lab.github.io/qm-template/zh/usage/download/)

## 环境要求

- Python >= 3.11 和 [uv](https://docs.astral.sh/uv/)
- `create` 需要 Proxmox VE 主机：本地使用 `qm`/`pvesm`，或用 `--pve` 通过 API
  访问远程主机（Proxmox VE >= 8.4）
- `download` 需要 `axel`、`aria2c`、`wget` 或 `curl` 之一，签名校验需要 `gpg`
- `prepare` 需要 `qemu-img` 以及 `genisoimage`、`xorriso`、`mkisofs` 之一

## 开发

```shell
uv sync --group dev
just lint        # ruff check --fix + ruff format
just typecheck   # ty check src/
just test        # pytest
just docs-build  # mkdocs build
```
