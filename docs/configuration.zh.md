# 配置

## 配置文件

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

## 设置

`download.preferred` 指定下载器优先级，`download.connections` 设置 `axel` 和
`aria2c` 的并行连接数。默认显示下载进度，可用 `download.quiet = true` 或
`-q`/`--quiet` 关闭。签名校验默认开启，会用 `gpg` 校验已签名的校验和或镜像；
没有安装 gnupg 等情况下可设 `download.verify_signature = false` 跳过。
`prepare.preferred` 指定 ISO 打包工具优先级，默认为 `genisoimage`、`xorriso`、
`mkisofs`。

`cloudinit.user` 是 Cloud-Init 的登录用户名；为空时使用发行版惯用名（Debian 为
`debian`、FreeBSD 为 `freebsd`、Amazon Linux 为 `ec2-user` 等），镜像不在已知
发行版目录下时回退为 `admin`。`cloudinit.password` 可选：为空表示不启用密码登录，
此时需要配置 SSH 公钥。`cloudinit.sshkeys` 以内联列表提供注入的 SSH 公钥，
`cloudinit.sshkeys_files` 指向公钥文件列表，两者的内容会按 SSH 指纹合并去重；
`create` 和 `prepare` 都要求至少配置一个公钥或密码。密码在 `--dry-run` 输出和
debug 日志中都会被打码。`cloudinit.shell` 设置本地 seed ISO（`prepare`）创建用户
的登录 shell；设为 `""` 则保留镜像默认 shell，Alpine Linux 可设为 `/bin/ash`。
Cloud-Init 本身支持在 `user-data` 中配置多个用户，但 Proxmox VE 托管的
Cloud-Init 只暴露单个 `ciuser`/`cipassword`（多用户需要自定义 `cicustom`
snippets），因此 `[cloudinit]` 有意只描述一个用户。

`create.storage` 是导入磁盘和 Cloud-Init 驱动器使用的 Proxmox 存储。
`create.cpu` 设置传给 `qm` 的 CPU 类型（`cputype=...`，默认 `host`，性能最好但
无法跨 CPU 代际迁移）。`create.firmware`（`auto`、`bios` 或 `uefi`）选择固件；
`auto` 会对文件名包含 `uefi` 的镜像（例如 Fedora 的 `UEFI-UKI` 变体）使用
UEFI，其余使用 BIOS。UEFI 模板通过 `--bios ovmf` 和一块 EFI 磁盘创建
（`--efidisk0 <storage>:1,pre-enrolled-keys=0`，即不启用 Secure Boot）。
`create.tags`、`create.pool`、`create.onboot` 和 `create.description` 为模板添加
可选的 Proxmox 元数据。`vmid.start` 和 `vmid.step`（默认 `9000` 和 `1`）控制
VM ID 的自动选择。任何命令都可以加 `-v`（输出 debug 日志）或 `-vv`（额外输出
日志级别和时间戳）用于排查问题。

## 远程 Proxmox VE 主机

远程主机可选，位于 `[pve.<name>]` 下，供 `create --pve <name>` 使用。必填
`host`、`user`、`token_name`、`token_secret`，上传镜像还需要 `import_storage`；
多节点集群必须设置 `node`，`verify_ssl`、`port`、`timeout`、`task_timeout`
均有默认值。嵌套的 `[pve.<name>.create]`、`[pve.<name>.vmid]` 和
`[pve.<name>.cloudinit]` 只覆盖该主机的全局配置。可用
`QM_TEMPLATE_PVE__<NAME>__TOKEN_SECRET` 避免把 token secret 写进文件，并确保
配置文件仅所有者可读：

```toml
[pve.home]
host = "pve.home.arpa"
user = "qm-template@pve"
token_name = "automation"
token_secret = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
import_storage = "local"

[pve.home.vmid]
start = 9000
```

远程模式对 Proxmox VE 侧的要求见[创建虚拟机模板](usage/create.md)。

## 按发行版覆盖

按发行版覆盖参数是可选的，位于 `[distro.<name>]` 下；这些覆盖不会出现在
`qm-template config` 打印的默认配置中，只在某个发行版需要偏离内置默认值时才添加：

```toml
[distro.debian]
release = "bookworm-backports"
arch = "arm64"
base_url = "https://mirror.example.org/debian-cloud"
```

`qm-template distros` 列出的每个参数都会按发行版校验，并且在 `download` 中有对应的
命令行选项（例如 `--release`、`--variant`、`--fs`、`--firmware`）；给某个发行版传入
它没有声明的参数会报错。唯一的例外是 `base_url`，它只能通过配置文件设置。

`base_url` 用于把某个发行版指向上游或镜像站，镜像站必须保持上游的目录结构；校验和
文件及其签名也从同一个 base 获取。Ubuntu、Fedora、Rocky、AlmaLinux、openSUSE、
Alpine 和 Arch Linux 对元数据签名，校验和在被信任之前会先用 `gpg` 验证；签名公钥
只从发行版的官方来源获取（绝不从镜像站获取），上游提供稳定公钥时会校验固定的指纹。
Debian、CentOS Stream 和 FreeBSD 不对 cloud image 元数据签名，Amazon Linux 的
RSA 签名也尚未校验；对这些发行版，镜像站同时提供镜像和校验和，对真实性有要求时请
使用可信镜像，或用带外方式自行校验。

## 生成配置文件

`qm-template config` 会把带注释的默认配置打印到 stdout，重定向即可生成起始配置；
`--full` 还会追加各发行版的默认参数表。工具不会自动写配置文件：

```shell
install -d /etc/qm-template
qm-template config > /etc/qm-template/config.toml

# 显式固定每个发行版的参数
qm-template config --full > /etc/qm-template/config.toml
```

仓库中的 `config.example.toml` 是指向打包进 wheel 的同一文件的符号链接。
