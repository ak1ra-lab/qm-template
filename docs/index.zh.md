# qm-template

一个 Python CLI，用于下载 cloud image、创建支持 Cloud-Init 的 Proxmox VE 虚拟机模板，
并准备本地虚拟机产物。

## 特性

- **多发行版下载**：Debian、Ubuntu、Rocky Linux、AlmaLinux、Fedora、
  CentOS Stream、Alpine、openSUSE、Arch Linux、FreeBSD 和 Amazon Linux 2023。
- **校验和验证**：从各发行版官方校验和文件获取 SHA-256/SHA-512，并与镜像一起保存为
  `<image>.sha256`/`.sha512`。
- **GPG 签名校验**：对已签名的校验和或镜像进行验证，公钥来自发行版官方来源并校验
  固定指纹。
- **断点续传**：使用首个可用的 `axel`、`aria2c`、`wget` 或 `curl`，默认显示进度
  （可用 `--quiet` 关闭），并支持失败重试。
- **单条 `qm create ... --template 1` 命令**，而不是一串 `qm set` 调用；自动选择
  下一个空闲 VM ID，可配置 CPU 类型，并支持可选的 tags、pool、onboot 和 description。
- **远程 Proxmox VE 主机**：`create --pve <name>` 通过 API（Proxmox VE >= 8.4）
  和 API token 在远程主机上创建模板，镜像上传到 `import` 类型的存储并在后续运行中
  复用。每台主机位于 `[pve.<name>]` 配置段，可覆盖该主机的 `[create]`、`[vmid]` 和
  `[cloudinit]` 设置。
- **本地虚拟机产物**：`qm-template prepare` 通过 `qemu-img` 转换磁盘格式
  （VDI、VMDK、QCOW2、raw 或 VHDX），并用 `genisoimage`/`xorriso`/`mkisofs` 生成
  NoCloud seed ISO，两者与源镜像同目录存放。
- **配置校验**：设置及可选的 `[distro.<name>]` 覆盖值由 `pydantic-settings` 校验，
  可用 `QM_TEMPLATE_*` 环境变量覆盖配置文件，`qm-template config` 会把起始配置
  打印到 stdout。
- **镜像站友好**：通过 `[distro.<name>] base_url` 把任意发行版指向上游或镜像站，
  已签名的校验和文件也来自同一 base。
- **Shell 补全**：由 `argcomplete` 提供，包括每个发行版支持的参数值。
- **调试日志**：任何命令都可以用 `-v`/`-vv` 提高日志详细程度。

## 快速开始

```shell
uv tool install qm-template
qm-template download debian
qm-template create --vm-id 9000
```

## 文档

- [入门指南](getting-started.md)
- [配置](configuration.md)
- [下载镜像](usage/download.md)
- [创建虚拟机模板](usage/create.md)
- [准备本地产物](usage/prepare.md)
- [列出发行版](usage/distros.md)
