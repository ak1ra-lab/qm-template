# Create a template

```shell
# interactive image selection; the VM ID is chosen automatically
qm-template create

# filter images with a regular expression on the relative path
qm-template create debian-13

# non-interactive with an explicit ID
qm-template create --vm-id 9000 --vm-name debian-13-template

# use a migration-friendly CPU type
qm-template create --cpu x86-64-v2-AES

# override the firmware auto-detected from the image name
qm-template create --firmware uefi

# attach Proxmox metadata
qm-template create --tags template,cloud --pool templates --onboot

# inspect the assembled command without running it
qm-template create --dry-run --vm-id 9000
```

`create` requires a Proxmox VE host and runs a single
`qm create ... --template 1` command, which `--dry-run`/`-n` pretty prints
without executing it:

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
    --cipassword debian \
    --sshkeys /tmp/qm-template-sshkeys-XXXX.pub \
    --template 1
```

When `--vm-id` is omitted, the IDs in use are collected from `qm list`
combined with `/etc/pve/qemu-server/*.conf` and the first free ID at or after
`vmid.start` (default `9000`), advancing by `vmid.step`, is used. If `qm
create` fails after leaving a VM config behind, the `qm destroy` command
needed to clean it up is reported. The resources and metadata of the template
come from the [configuration](../configuration.md#settings) and can be overridden
with `--storage`, `--cores`, `--memory`, `--cpu`, `--bridge`, `--tags`,
`--pool`, `--onboot`, `--description` and `--firmware`.

## Remote Proxmox VE hosts

With `--pve NAME`, `create` talks to the Proxmox VE API instead of running
`qm`, so a single workstation can manage several hosts without installing
`qm-template` or downloading images on them:

```shell
qm-template create debian-13 --pve home --vm-name debian-13-template

# print the API requests instead of executing them
qm-template create debian-13 --pve home --dry-run
```

API mode requires Proxmox VE 8.4 or newer. The image is uploaded to the host's
`import_storage` with `content=import` and imported with
`scsi0=<create.storage>:0,import-from=<import_storage>:import/<file>`; an
uploaded file with the same name and size is reused, so repeat runs skip the
transfer. The image name is flattened from the path below `paths.images_dir`
and the format is detected from the file itself, so Ubuntu's `.img` images are
accepted. VM IDs come from the cluster (`GET /cluster/nextid`), and
`vmid.start`/`vmid.step` still apply. When creation fails, the incomplete VM is
removed again. `--dry-run` prints the upload and `POST
/api2/json/nodes/<node>/qemu` requests (the password stays visible, like the
local `qm create` command). The selected host can override the global
`[create]`, `[vmid]` and `[cloudinit]` settings; see
[Configuration](../configuration.md#remote-proxmox-ve-hosts).

Prepare the remote host once:

- create a user and API token that may allocate VMs:

  ```shell
  pveum user add qm-template@pve
  pveum acl modify / --users qm-template@pve --roles PVEAdmin
  pveum user token add qm-template@pve automation --privsep 0
  ```

  Token permissions are limited to the user's own permissions; a narrower
  custom role works too, but creating a VM touches several privileges
  (`VM.Allocate`, `VM.Config.*`, `Datastore.AllocateSpace` and
  `Datastore.AllocateTemplate` for the upload). Privilege separation is on by
  default, so without `--privsep 0` a new token has no permissions of its own
  and needs a separate ACL entry
  (`pveum acl modify / --tokens 'qm-template@pve!automation' --roles PVEAdmin`).
- enable the `import` content type on a file-based storage (Datacenter ->
  Storage -> your storage -> Edit -> Content) and point `import_storage` at
  it. LVM/ZFS storages cannot hold import content; `create.storage` (for
  example `local-lvm`) remains the target for the VM disk and Cloud-Init
  drive. Import storage needs Proxmox VE 8.4+.
- set `verify_ssl = false` (or trust the PVE CA) when the host still uses its
  self-signed certificate.

Hosts older than 8.4 keep working with the default local mode.
