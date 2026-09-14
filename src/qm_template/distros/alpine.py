import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, RemoteImage


class Alpine(Distro):
    name = "alpine"
    description = "Alpine Linux"
    defaults = {"release": "3.24", "variant": "generic", "arch": "x86_64"}

    base_url = "https://dl-cdn.alpinelinux.org/alpine"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{self.base_url}/v{release}/releases/cloud/"
        filename = self.newest_in(
            base,
            rf"{re.escape(variant)}_alpine-{re.escape(release)}\.\d+"
            rf"-{re.escape(arch)}-bios-cloudinit-r0\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.sha512",
            algorithm="sha512",
        )
