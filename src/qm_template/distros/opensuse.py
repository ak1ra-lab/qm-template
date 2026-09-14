import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, RemoteImage


class OpenSUSE(Distro):
    name = "opensuse"
    description = "openSUSE Leap / Tumbleweed"
    defaults = {"release": "tumbleweed", "variant": "Minimal", "arch": "x86_64"}

    tumbleweed_url = "https://download.opensuse.org/tumbleweed/appliances/"
    leap_url = "https://download.opensuse.org/distribution/leap"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        if release == "tumbleweed":
            base = self.tumbleweed_url
            pattern = (
                rf"(?:openSUSE-)?Tumbleweed-{re.escape(variant)}"
                rf"-VM\.{re.escape(arch)}-\d[\d.]*-Cloud-Snapshot\d+\.qcow2"
            )
        else:
            base = f"{self.leap_url}/{release}/appliances/"
            pattern = (
                rf"(?:openSUSE-)?Leap-{re.escape(release)}-{re.escape(variant)}"
                rf"-VM\.{re.escape(arch)}-Cloud\.qcow2"
            )
        filename = self.newest_in(base, pattern)
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.sha256",
            algorithm="sha256",
        )
