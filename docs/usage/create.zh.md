# 创建虚拟机模板

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
`--dry-run`/`-n` 会 pretty print 组装好的命令而不执行：

```shell
qm create 9000 \
    --name debian-13-template \
    --cpu cputype=host \
    --cores 1 \
    --balloon 1024 \
    --memory 1024 \
    --net0 model=virtio,firewall=1,bridge=vmbr0 \
    --scsihw virtio-scsi-single \
    --agent type=virtio,enabled=1 \
    --machine q35 \
    --ostype l26 \
    --serial0 socket \
    --vga serial0 \
    --scsi0 local-lvm:0,import-from=/path/to/image.qcow2 \
    --scsi1 local-lvm:cloudinit \
    --boot order=scsi0 \
    --ipconfig0 ip=dhcp \
    --ciupgrade 0 \
    --ciuser debian \
    --cipassword '********' \
    --sshkeys /tmp/qm-template-sshkeys-XXXX.pub \
    --template 1
```

登录名来自 `cloudinit.user`，为空时使用发行版惯用名（上面镜像即 `debian`）；
未配置密码时不输出 `--cipassword`，未配置公钥时不输出 `--sshkeys`。预览中的
secret 都被打码，照抄打印结果执行前需要把掩码替换为真实值。

省略 `--vm-id` 时，会从 `qm list` 与 `/etc/pve/qemu-server/*.conf` 合并收集已占用
的 ID，并使用从 `vmid.start`（默认 `9000`）开始、以 `vmid.step` 递增的首个空闲 ID。
如果 `qm create` 失败并留下了 VM 配置，会提示用于清理的 `qm destroy` 命令。模板的
资源和元数据来自[配置](../configuration.md)，可用 `--storage`、`--cores`、
`--memory`、`--cpu`、`--bridge`、`--tags`、`--pool`、`--onboot`、`--description`
和 `--firmware` 覆盖。

## 远程 Proxmox VE 主机

使用 `--pve NAME` 时，`create` 通过 Proxmox VE API 而不是本地 `qm` 创建模板，
因此一台工作站可以管理多台主机，无需在主机上安装 `qm-template` 或下载镜像：

```shell
qm-template create debian-13 --pve home --vm-name debian-13-template

# 仅打印 API 请求，不执行
qm-template create debian-13 --pve home --dry-run
```

API 模式要求 Proxmox VE 8.4 或更新。镜像以 `content=import` 上传到主机的
`import_storage`，然后通过
`scsi0=<create.storage>:0,import-from=<import_storage>:import/<file>` 导入；
同名同大小的镜像会直接复用，重复运行无需再次传输。镜像名由
`paths.images_dir` 下的相对路径展平而来，格式从文件内容判断，因此 Ubuntu 的
`.img` 镜像也能使用。VM ID 从集群获取（`GET /cluster/nextid`），
`vmid.start`/`vmid.step` 依然有效。创建失败时会自动删除残留的 VM。`--dry-run`
会打印上传和 `POST /api2/json/nodes/<node>/qemu` 请求（与本地 `qm create`
一样，密码和 SSH 公钥都会被打码）。选中的主机可以覆盖全局的 `[create]`、`[vmid]` 和
`[cloudinit]` 设置，见[配置](../configuration.md)。

远程主机需要一次性准备：

- 创建可分配 VM 的用户和 API token：

  ```shell
  pveum user add qm-template@pve
  pveum acl modify / --users qm-template@pve --roles PVEAdmin
  pveum user token add qm-template@pve automation --privsep 0
  ```

  token 权限不超过用户自身权限；也可以使用更小的自定义角色，但创建 VM 涉及
  多项权限（`VM.Allocate`、`VM.Config.*`、`Datastore.AllocateSpace`，上传还需要
  `Datastore.AllocateTemplate`）。权限分离（privilege separation）默认开启，
  不加 `--privsep 0` 时新 token 自身没有任何权限，需要单独授权：
  `pveum acl modify / --tokens 'qm-template@pve!automation' --roles PVEAdmin`。
- 为某个基于文件的存储启用 `import` 内容类型（数据中心 -> 存储 -> 选择存储 ->
  编辑 -> 内容），并把 `import_storage` 指向它。LVM/ZFS 存储无法存放 import
  内容；`create.storage`（例如 `local-lvm`）仍然是 VM 磁盘和 Cloud-Init
  驱动器的目标存储。import 存储需要 Proxmox VE 8.4+。
- 主机仍在使用自签名证书时，设置 `verify_ssl = false`（或信任 PVE CA）。

低于 8.4 的主机可以继续使用默认的本地模式。
