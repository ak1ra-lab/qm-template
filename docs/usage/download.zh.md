# 下载镜像

```shell
# 使用配置文件中的默认发行版
qm-template download

# 指定发行版，并可覆盖参数
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594
qm-template download freebsd --fs zfs
qm-template download alpine --firmware uefi

# 仅打印首个可用下载器的命令（不执行）
qm-template download -n alpine

# 关闭下载进度输出
qm-template download -q alpine
```

`--dry-run` 会解析镜像并 pretty print 首个可用下载器的命令，每个参数组一行，不执行
下载。下载器顺序与并行连接数来自
[`download.preferred`/`download.connections`](../configuration.md)。

上游提供日期快照的发行版（Debian、Ubuntu server、Arch Linux、openSUSE
Tumbleweed）会固定到最新构建，Amazon Linux 2023 会把 `/latest/` 解析为当前版本并
固定，新构建会与旧构建并存而不是覆盖。FreeBSD 镜像以 `.xz` 归档分发：归档会先校验，
再解压为 `.qcow2` 并删除归档，同时保存本地校验和 sidecar，后续运行可直接判定为最新。
`--tag` 用于固定具体构建，只有声明了该参数的发行版才接受（Debian、Fedora、Arch
Linux 和 Amazon Linux 2023，`qm-template distros` 会列出）。Alpine 镜像可用
`--firmware` 选择 BIOS 或 UEFI（`auto` 按架构决定），生成的文件名会让 `create`
自动选择对应的 Proxmox 固件。

中断的下载会在下次运行时续传，未完成的文件保存为 `<image>.part`。下载失败会使用
同一个下载器从零重试，不会切换到其他下载器；下载完成但校验和不匹配时会再从头下载
一次，仍失败才报错。校验和文件与目录列表在遇到瞬时 5xx 或网络错误时会按指数退避
重试。

上游提供签名元数据时（Ubuntu、Fedora、Rocky、AlmaLinux、openSUSE 提供已签名的
校验和文件，Alpine 和 Arch Linux 直接签名镜像），会在信任下载内容之前用 `gpg`
验证签名；公钥从发行版官方来源获取，上游提供稳定公钥时还会校验固定指纹。Debian、
CentOS Stream 和 FreeBSD 没有 cloud image 签名，Amazon Linux 的 RSA 签名也尚未
校验。获取到的校验和会与镜像一起保存为 `<image>.sha256` 或 `<image>.sha512`，
取决于上游使用的算法。设置 `download.verify_signature = false` 可跳过签名校验。
