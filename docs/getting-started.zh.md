# 入门指南

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- Proxmox VE 主机，通常以 root 身份运行
- `create` 命令需要 Proxmox VE（`qm`、`pvesm`）
- `download` 命令需要 `axel`、`aria2c`、`wget` 或 `curl` 之一

## 安装

以 uv tool 方式安装 CLI：

```shell
uv tool install qm-template
```

从源码安装：

```shell
uv tool install .
```

## 配置

配置文件是可选的，默认从 `/etc/qm-template/config.toml` 加载。可通过
`--config PATH` 或 `QM_TEMPLATE_CONFIG` 指定其他位置。下载的镜像默认存储在
`/var/lib/qm-template`，可由 `paths.images_dir` 覆盖，并按上游目录结构存放：

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` 指定下载器优先级，`download.connections` 设置 `axel` 和
`aria2c` 的并行连接数。从示例配置开始：

```shell
install -d /etc/qm-template
cp qm-template.example.toml /etc/qm-template/config.toml
```

命令行选项会覆盖配置文件中的默认值。

## 下载镜像

```shell
# 使用配置文件中的默认发行版
qm-template download

# 指定发行版，并可覆盖参数
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# 仅打印解析后的 URL
qm-template download --dry-run alpine
```

上游提供日期快照的发行版（Debian、Ubuntu server、Arch Linux、openSUSE
Tumbleweed）会固定到最新构建，新构建会与旧构建并存而不是覆盖。中断的下载会在下次运行时
续传，未完成的文件保存为 `<image>.part`。获取到的校验和会与镜像一起保存为
`<image>.sha256` 或 `<image>.sha512`，取决于上游使用的算法。

## 创建虚拟机模板

```shell
# 交互式选择镜像和 VM ID
qm-template create

# 使用正则表达式按相对路径过滤镜像
qm-template create debian-13

# 非交互式
qm-template create --vm-id 9000 --vm-name debian-13-template

# 仅查看组装好的命令，不执行
qm-template create --dry-run --vm-id 9000
```

`create` 需要 Proxmox VE 主机，并执行单条 `qm create ... --template 1` 命令。

## 列出发行版

```shell
qm-template distros
```

## 开发

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```
