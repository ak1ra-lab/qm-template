# 入门指南

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- Proxmox VE 主机，通常以 root 身份运行
- `create` 命令需要 Proxmox VE（`qm`、`pvesm`）
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

## 配置

配置文件是可选的，存在时默认从 `/etc/qm-template/config.toml` 加载；可通过
`--config PATH`/`-c` 或 `QM_TEMPLATE_CONFIG` 指定其他位置。没有配置文件时所有命令
都能正常工作。配置由 `pydantic-settings` 校验，未知的键和非法值会在报错中给出文件
与键路径。所有设置都可以用 `QM_TEMPLATE_*` 环境变量覆盖，嵌套层级用 `__` 分隔，
例如 `QM_TEMPLATE_DOWNLOAD__CONNECTIONS=4`；优先级为内置默认值 < 配置文件 <
环境变量 < 命令行选项。

下载的镜像默认存储在 `/var/lib/qm-template`，可由 `paths.images_dir` 覆盖，并按
上游目录结构存放：

```text
<images_dir>/<distro>/<release>/[<tag>/]<filename>
```

`download.preferred` 指定下载器优先级，`download.connections` 设置 `axel` 和
`aria2c` 的并行连接数。默认显示下载进度，可用 `download.quiet = true` 或
`-q`/`--quiet` 关闭。签名校验默认开启，会用 `gpg` 校验已签名的校验和或镜像；
没有安装 gnupg 等情况下可设 `download.verify_signature = false` 跳过。
`prepare.preferred` 指定 ISO 打包工具优先级，默认为 `genisoimage`、`xorriso`、
`mkisofs`。`cloudinit.user`/`password` 配置 Cloud-Init 用户，
`cloudinit.sshkeys` 以内联列表提供注入的 SSH 公钥，`cloudinit.sshkeys_files`
指向公钥文件列表，两者的内容会按 SSH 指纹合并去重；`create` 至少需要一个公钥，
`prepare` 在未配置公钥时会退化为仅密码登录。
`cloudinit.shell` 设置本地 seed ISO（`prepare`）创建用户的登录 shell；设为 `""`
则保留镜像默认 shell，Alpine Linux 可设为 `/bin/ash`。
`create.cpu` 设置传给 `qm` 的 CPU 类型（`cputype=...`，默认 `host`，性能最好但
无法跨 CPU 代际迁移）。`create.firmware`（`auto`、`bios` 或 `uefi`）选择固件；
`auto` 会对文件名包含 `uefi` 的镜像（例如 Fedora 的 `UEFI-UKI` 变体）使用
UEFI，其余使用 BIOS。UEFI 模板通过 `--bios ovmf` 和一块 EFI 磁盘创建
（`--efidisk0 <storage>:1,pre-enrolled-keys=0`，即不启用 Secure Boot）。
`create.tags`、`create.pool`、`create.onboot` 和 `create.description` 为模板添加
可选的 Proxmox 元数据。`vmid.start` 和 `vmid.step`（默认 `9000` 和 `1`）控制
VM ID 的自动选择。任何命令都可以加 `-v`（输出 debug 日志）或 `-vv`（额外输出
日志级别和时间戳）用于排查问题。

按发行版覆盖参数是可选的，位于 `[distro.<name>]` 下；这些覆盖不会出现在
`qm-template config` 打印的默认配置中，只在某个发行版需要偏离内置默认值时才添加：

```toml
[distro.debian]
release = "bookworm-backports"
arch = "arm64"
base_url = "https://mirror.example.org/debian-cloud"
```

`base_url` 用于把某个发行版指向上游或镜像站，镜像站必须保持上游的目录结构；校验和
文件及其签名也从同一个 base 获取。Ubuntu、Fedora、Rocky、AlmaLinux、openSUSE、
Alpine 和 Arch Linux 对元数据签名，校验和在被信任之前会先用 `gpg` 验证；签名公钥
只从发行版的官方来源获取（绝不从镜像站获取），上游提供稳定公钥时会校验固定的指纹。
Debian、CentOS Stream 和 FreeBSD 不对 cloud image 元数据签名，Amazon Linux 的
RSA 签名也尚未校验；对这些发行版，镜像站同时提供镜像和校验和，对真实性有要求时请
使用可信镜像，或用带外方式自行校验。

`qm-template distros` 会列出每个参数及其默认值和可选值，`qm-template distros
debian` 查看单个发行版。

## 生成配置文件

`qm-template config` 会把带注释的默认配置打印到 stdout，重定向即可生成起始配置；
`--full` 还会追加各发行版的默认参数表。工具不会自动写配置文件：

```shell
install -d /etc/qm-template
qm-template config > /etc/qm-template/config.toml

# 显式固定每个发行版的参数
qm-template config --full > /etc/qm-template/config.toml
```

仓库中的 `config.example.toml` 与不带参数的 `qm-template config` 输出相同。

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
`--release`/`--variant`/`--arch`/`--tag` 会根据命令行中指定的发行版给出候选值，
不支持某个参数的发行版不会给出该参数的候选。

## 下载镜像

```shell
# 使用配置文件中的默认发行版
qm-template download

# 指定发行版，并可覆盖参数
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594

# 仅打印首个可用下载器的命令（不执行）
qm-template download -n alpine

# 关闭下载进度输出
qm-template download -q alpine
```

`--dry-run` 会解析镜像并 pretty print 首个可用下载器的命令，每个参数组一行，不执行下载。
上游提供日期快照的发行版（Debian、Ubuntu server、Arch Linux、openSUSE
Tumbleweed）会固定到最新构建，Amazon Linux 2023 会把 `/latest/` 解析为当前版本并
固定，新构建会与旧构建并存而不是覆盖。FreeBSD 镜像以 `.xz` 归档分发：归档会先校验，
再解压为 `.qcow2` 并删除归档，同时保存本地校验和 sidecar，后续运行可直接判定为最新。
`--tag` 用于选择具体构建，只有支持它的发行版才会接受（目前是 Debian 和 Fedora，
`qm-template distros` 会标注）。中断的下载会在下次运行时
续传，未完成的文件保存为 `<image>.part`。下载失败会使用同一个下载器从零重试，不会切换
到其他下载器；下载完成但校验和不匹配时会再从头下载一次，仍失败才报错。校验和文件与目录
列表在遇到瞬时 5xx 或网络错误时会按指数退避重试。上游提供签名元数据时（Ubuntu、
Fedora、Rocky、AlmaLinux、openSUSE 提供已签名的校验和文件，Alpine 和 Arch Linux
直接签名镜像），会在信任下载内容之前用 `gpg` 验证签名；公钥从发行版官方来源获取，
上游提供稳定公钥时还会校验固定指纹。Debian、CentOS Stream 和 FreeBSD 没有 cloud
image 签名，Amazon Linux 的 RSA 签名也尚未校验。获取到的校验和会与镜像一起保存为
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

# 覆盖根据镜像名自动判定的固件
qm-template create --firmware uefi

# 附加 Proxmox 元数据
qm-template create --tags template,cloud --pool templates --onboot

# 仅查看组装好的命令，不执行
qm-template create --dry-run --vm-id 9000
```

`create` 需要 Proxmox VE 主机，并执行单条 `qm create ... --template 1` 命令；
`--dry-run`/`-n` 会 pretty print 组装好的命令而不执行。省略 `--vm-id` 时，会从
`qm list` 与 `/etc/pve/qemu-server/*.conf` 合并收集已占用的 ID，并使用从
`vmid.start`（默认 `9000`）开始、以 `vmid.step` 递增的首个空闲 ID。如果
`qm create` 失败并留下了 VM 配置，会提示用于清理的 `qm destroy` 命令。

## 准备本地虚拟机产物

多数 hypervisor 无法直接启动 `.qcow2`，需要先转换磁盘格式。与 hypervisor 无关的
`prepare` 命令会选择已下载镜像，用 `qemu-img` 转换成客户机磁盘，再用
`genisoimage`、`xorriso`、`mkisofs` 中首个可用的工具把 NoCloud seed 打包成卷标为
`CIDATA` 的 ISO：按 `[cloudinit]` 配置生成的 `user-data`/`meta-data`，以及一份
DHCP `network-config`（Debian cloud image 不会自动生成网络配置，缺了它网卡不会被
配置）。两个产物与源镜像同目录存放，仅后缀不同：

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
`generic`/`genericcloud` 变体：Debian 的 `nocloud` 变体不运行 Cloud-Init。
`prepare` 不强制要求 SSH 公钥：未配置时会记录警告，seed 仅启用密码登录
（`create` 仍然要求至少一个公钥）。已存在的客户机磁盘会保留，只重建 seed ISO
（转换开销大、而 seed 由 `[cloudinit]` 配置决定）；需要重新转换时传入
`--force`/`-f`。

## 列出发行版

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
  base_url = https://cdimage.debian.org/images/cloud upstream or mirror base URL
```

## 开发

```shell
uv sync --group dev
just lint
just typecheck
just test
just docs-build
```
