import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage


class Alpine(Distro):
    name = "alpine"
    description = "Alpine Linux"
    options = {
        "release": Option("3.24", note="version series, e.g. 3.23, 3.24"),
        "variant": Option("generic", ("generic", "nocloud")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://dl-cdn.alpinelinux.org/alpine",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        firmware = "bios" if arch == "x86_64" else "uefi"
        base = f"{params['base_url']}/v{release}/releases/cloud/"
        filename = self.newest_in(
            base,
            rf"{re.escape(variant)}_alpine-{re.escape(release)}\.\d+"
            rf"-{re.escape(arch)}-{firmware}-cloudinit-r0\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.sha512",
            algorithm="sha512",
        )
