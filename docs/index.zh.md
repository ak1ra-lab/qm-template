# qm-template

一个 Python CLI，用于下载 cloud image 并创建支持 Cloud-Init 的 Proxmox VE 虚拟机模板。

## 特性

- **多发行版下载**：Debian、Ubuntu、Rocky Linux、AlmaLinux、Fedora、
  CentOS Stream、Alpine、openSUSE 和 Arch Linux。
- **校验和验证**：从各发行版官方校验和文件获取 SHA-256/SHA-512，并与镜像一起保存为
  `<image>.sha256`/`.sha512`。
- **断点续传**：使用可用的 `axel`、`aria2c`、`wget` 或 `curl`，默认显示进度
  （可用 `--quiet` 关闭），并支持失败重试。
- **单条 `qm create ... --template 1` 命令**，而不是一串 `qm set` 调用；自动选择
  下一个空闲 VM ID，并可配置 CPU 类型。
- **本地镜像清单**：`qm-template images` 列出已下载镜像，并支持清理被取代的日期构建。
- **TOML 配置**：使用标准库的 `tomllib` 读取。

## 快速开始

```shell
uv tool install qm-template
qm-template download debian
qm-template distros
```

配置、用法和开发说明请参阅[入门指南](getting-started.md)。
