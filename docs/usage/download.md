# Download images

```shell
# default distro from the configuration file
qm-template download

# pick a distro, optionally override parameters
qm-template download ubuntu --release noble --variant minimal
qm-template download debian --release bookworm --tag 20260907-2594
qm-template download freebsd --fs zfs
qm-template download alpine --firmware uefi

# print the first available downloader's command without running it
qm-template download -n alpine

# hide the downloader progress output
qm-template download -q alpine
```

`--dry-run` resolves the image and pretty prints the command of the first
available downloader, one argument group per line, without downloading
anything. The downloader order and connection count come from
[`download.preferred`/`download.connections`](../configuration.md#settings).

Builds are pinned where the upstream provides dated snapshots (Debian, Ubuntu
server, Arch Linux, openSUSE Tumbleweed), and Amazon Linux 2023 resolves
`/latest/` to the current version and pins it, so a newer build is downloaded
alongside the old one instead of overwriting it. FreeBSD images are distributed
as `.xz` archives: the archive is verified, extracted to `.qcow2` and removed,
and a local checksum sidecar lets later runs detect the up-to-date image.
`--tag` pins a specific upstream build and is accepted by the distros that
declare it (Debian, Fedora, Arch Linux and Amazon Linux 2023;
`qm-template distros` lists them). Alpine images can be downloaded for BIOS or
UEFI with `--firmware` (`auto` follows the architecture), and the resulting
filename makes `create` pick the matching Proxmox firmware.

Interrupted downloads are resumed on the next run; partial files are stored as
`<image>.part`. A failed download is retried from scratch with the same
downloader and never switches to another one; a completed download that fails
checksum verification is downloaded once more from scratch before the command
fails. Checksum files and directory listings are retried with exponential
backoff on transient 5xx and network errors.

Where upstream provides signed metadata - a signed checksum file for Ubuntu,
Fedora, Rocky, AlmaLinux and openSUSE, a signed image for Alpine and Arch
Linux - the signature is verified with `gpg` before the download is trusted;
keys are fetched from the distro's canonical source and pinned fingerprints are
checked where upstream publishes stable keys. Debian, CentOS Stream and FreeBSD
ship no cloud image signatures, and Amazon Linux's RSA signature is not
verified yet. The fetched checksum is saved next to the image as
`<image>.sha256` or `<image>.sha512`, depending on the upstream algorithm. Set
`download.verify_signature = false` to skip signature verification.
