import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage


class OpenSUSE(Distro):
    name = "opensuse"
    description = "openSUSE Leap / Tumbleweed"
    options = {
        "release": Option("tumbleweed", note="tumbleweed or a Leap version, e.g. 15.6"),
        "variant": Option("Minimal", ("Minimal",)),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://download.opensuse.org",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base_url = params["base_url"]
        if release == "tumbleweed":
            base = f"{base_url}/tumbleweed/appliances/"
            pattern = (
                rf"(?:openSUSE-)?Tumbleweed-{re.escape(variant)}"
                rf"-VM\.{re.escape(arch)}-\d[\d.]*-Cloud-Snapshot\d+\.qcow2"
            )
        else:
            base = f"{base_url}/distribution/leap/{release}/appliances/"
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
