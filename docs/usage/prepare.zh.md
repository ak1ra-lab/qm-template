# 准备本地产物

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
（转换开销大、而 seed 由 `[cloudinit]` [配置](../configuration.md)决定）；需要重新
转换时传入 `--force`/`-f`。
