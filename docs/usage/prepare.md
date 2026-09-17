# Prepare local artifacts

Most hypervisors cannot boot `.qcow2` directly, so guest disks have to be
converted. The hypervisor-agnostic `prepare` command picks a downloaded image,
converts it to a guest disk with `qemu-img` and packs a NoCloud seed into a
`CIDATA`-labelled ISO with the first available of `genisoimage`, `xorriso` or
`mkisofs`: `user-data`/`meta-data` built from the `[cloudinit]` settings plus a
DHCP `network-config` (needed because Debian cloud images do not fall back to a
generated network configuration). Both artifacts are written next to the source
image and only differ in suffix:

```shell
# debian-13.qcow2 -> debian-13.vdi + debian-13.iso
qm-template prepare debian-13

# other hypervisors: vmdk (VMware/VirtualBox), raw or vhdx (Hyper-V)
qm-template prepare --format vmdk debian-13

# override the hostname recorded in the seed
qm-template prepare --vm-name debian-13-vbox debian-13

# preview every command without running or writing anything
qm-template prepare --dry-run debian-13
```

Supported formats are `vdi` (default), `vmdk`, `qcow2`, `raw` and `vhdx`; the
extension follows the format. Choosing `qcow2` for a `.qcow2` source is
rejected because it would overwrite the source image. For VirtualBox, attach
the `.vdi` as a SATA hard disk and the seed ISO as a CD-ROM. Use the
`generic`/`genericcloud` image variants: Debian's `nocloud` variant does not
run Cloud-Init.

Like `create`, `prepare` requires a login method: at least one SSH key or a
password. With only a password, the seed enables password login. An existing
guest disk is kept and only the seed ISO is rebuilt, since converting is
expensive and the seed derives from the `[cloudinit]`
[configuration](../configuration.md#settings); pass `--force`/`-f` to convert
again.
