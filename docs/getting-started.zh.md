# 入门指南

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- Proxmox VE 主机，通常以 root 身份运行
- `create` 命令需要 Proxmox VE（`qm`、`pvesm`）
- `download` 命令需要 `axel`、`aria2c`、`wget` 或 `curl` 之一
- `prepare` 命令需要 `qemu-img` 和 `genisoimage`

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

配置文件是可选的，默认从 `/etc/qm-template/config.toml` 加载，首次运行时会自动
写入内置默认配置。可通过 `--config PATH` 或 `QM_TEMPLATE_CONFIG` 指定其他位置。
下载的镜像默认存储在 `/var/lib/qm-template`，可由 `paths.images_dir` 覆盖，并按
上游目录结构存放：

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` 指定下载器优先级，`download.connections` 设置 `axel` 和
`aria2c` 的并行连接数。默认显示下载进度，可用 `download.quiet = true` 或
`--quiet` 关闭。`cloudinit.user`/`password` 配置 Cloud-Init 用户，
`cloudinit.sshkeys` 以内联列表提供注入的 SSH 公钥，`cloudinit.sshkeys_files`
指向公钥文件列表，两者的内容会按 SSH 指纹合并去重，且至少需要配置一个公钥。
`create.cpu` 设置传给 `qm` 的 CPU 类型（`cputype=...`，默认 `host`，性能最好但
无法跨 CPU 代际迁移）。`create.start_id` 和 `create.step`（默认 `9000` 和 `1`）
控制 VM ID 的自动选择。也可以手动创建示例配置：

```shell
install -d /etc/qm-template
cp config.example.toml /etc/qm-template/config.toml
```

命令行选项会覆盖配置文件中的默认值。

## 下载镜像

```shell
# 使用配置文件中的默认发行版
qm-template download

# 指定发行版，并可覆盖参数
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# 仅打印首个可用下载器的命令（不执行）
qm-template download --dry-run alpine

# 关闭下载进度输出
qm-template download --quiet alpine
```

`--dry-run` 会解析镜像并 pretty print 首个可用下载器的命令，每个参数组一行，不执行下载。
上游提供日期快照的发行版（Debian、Ubuntu server、Arch Linux、openSUSE
Tumbleweed）会固定到最新构建，新构建会与旧构建并存而不是覆盖。中断的下载会在下次运行时
续传，未完成的文件保存为 `<image>.part`。下载失败会使用同一个下载器从零重试，不会切换
到其他下载器；下载完成但校验和不匹配时会再从头下载一次，仍失败才报错。校验和文件与目录
列表在遇到瞬时 5xx 或网络错误时会按指数退避重试。获取到的校验和会与镜像一起保存为
`<image>.sha256` 或 `<image>.sha512`，取决于上游使用的算法。

## 创建虚拟机模板

```shell
# 交互式选择镜像，VM ID 自动选择
qm-template create

# 使用正则表达式按相对路径过滤镜像
qm-template create debian-13

# 非交互式，显式指定 ID
qm-template create --vm-id 9000 --vm-name debian-13-template

# 使用便于迁移的 CPU 类型
qm-template create --cpu x86-64-v2-AES

# 仅查看组装好的命令，不执行
qm-template create --dry-run --vm-id 9000
```

`create` 需要 Proxmox VE 主机，并执行单条 `qm create ... --template 1` 命令；
`--dry-run` 会 pretty print 组装好的命令而不执行。省略 `--vm-id` 时，会从 `qm list`
（回退到 `/etc/pve/qemu-server/*.conf`）收集已占用的 ID，并使用从
`create.start_id`（默认 `9000`）开始、以 `create.step` 递增的首个空闲 ID。如果
`qm create` 失败并留下了 VM 配置，会提示用于清理的 `qm destroy` 命令。

## 准备本地虚拟机产物

多数 hypervisor 无法直接启动 `.qcow2`，需要先转换磁盘格式。与 hypervisor 无关的
`prepare` 命令会选择已下载镜像，用 `qemu-img` 转换成客户机磁盘，再用 `genisoimage`
把 NoCloud seed 打包成卷标为 `CIDATA` 的 ISO：按 `[cloudinit]` 配置生成的
`user-data`/`meta-data`，以及一份 DHCP `network-config`（Debian cloud image 不会
自动生成网络配置，缺了它网卡不会被配置）。两个产物与源镜像同目录存放，仅后缀不同：

```shell
# debian-13.qcow2 -> debian-13.vdi + debian-13.iso
qm-template prepare debian-13

# 其他 hypervisor：vmdk（VMware/VirtualBox）、raw 或 vhdx（Hyper-V）
qm-template prepare --format vmdk debian-13

# 覆盖 seed 中记录的主机名
qm-template prepare --vm-name debian-13-vbox debian-13

# 仅预览所有命令，不执行、不写入
qm-template prepare --dry-run debian-13
```

支持的格式为 `vdi`（默认）、`vmdk`、`qcow2`、`raw` 和 `vhdx`，后缀随格式变化。
源镜像是 `.qcow2` 时选择 `qcow2` 会被拒绝，因为会覆盖源镜像。VirtualBox 中把
`.vdi` 挂为 SATA 硬盘、把 seed ISO 挂为 CD-ROM 即可。请使用
`generic`/`genericcloud` 变体：Debian 的 `nocloud` 变体不运行 Cloud-Init。已存在的
客户机磁盘会保留，只重建 seed ISO（转换开销大、而 seed 由 `[cloudinit]` 配置决定）；
需要重新转换时传入 `--force`。

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
