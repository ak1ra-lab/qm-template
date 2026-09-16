from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage

ARCH_TOKENS = {"amd64": "amd64", "aarch64": "arm64-aarch64"}


class FreeBSD(Distro):
    name = "freebsd"
    description = "FreeBSD"
    options = {
        "release": Option(
            "15.1",
            pattern=r"\d+\.\d+",
            note="release like 14.5 or 15.1",
        ),
        "fs": Option("ufs", ("ufs", "zfs"), note="guest filesystem: ufs or zfs"),
        "arch": Option("amd64", ("amd64", "aarch64")),
        "base_url": Option(
            "https://download.freebsd.org/ftp/releases/VM-IMAGES",
            note="upstream or mirror base URL",
            cli=False,
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        arch = params["arch"]
        base = f"{params['base_url']}/{release}-RELEASE/{arch}/Latest/"
        filename = (
            f"FreeBSD-{release}-RELEASE-{ARCH_TOKENS[arch]}"
            f"-BASIC-CLOUDINIT-{params['fs']}.qcow2.xz"
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}CHECKSUM.SHA256",
            algorithm="sha256",
            compression="xz",
        )
