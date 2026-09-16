from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.signature import Signature

ARCH_BOXES_SIGNING_KEY = "1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F"
ARCH_BOXES_KEY_URL = (
    "https://keyserver.ubuntu.com/pks/lookup"
    f"?op=get&search=0x{ARCH_BOXES_SIGNING_KEY}&options=mr"
)


class ArchLinux(Distro):
    name = "archlinux"
    description = "Arch Linux"
    options = {
        "release": Option("latest", note="latest or a build, e.g. v20260901.583572"),
        "variant": Option("cloudimg", ("cloudimg",)),
        "arch": Option("x86_64", ("x86_64",)),
        "base_url": Option(
            "https://geo.mirror.pkgbuild.com/images",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base_url = params["base_url"]
        if release == "latest":
            release = self.newest_in(f"{base_url}/", r"v\d{8}\.\d+")
        base = f"{base_url}/{release}/"
        filename = f"Arch-Linux-{arch}-{variant}.qcow2"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.SHA256",
            algorithm="sha256",
            signature=Signature(
                url=f"{base}{filename}.sig",
                key_url=ARCH_BOXES_KEY_URL,
                target="image",
                fingerprint=ARCH_BOXES_SIGNING_KEY,
            ),
        )
