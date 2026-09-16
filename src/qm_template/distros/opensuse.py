import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.signature import Signature

OPENSUSE_SIGNING_KEY = "AD485664E901B867051AB15F35A2F86E29B700A4"
OPENSUSE_KEY_URL = (
    "https://build.opensuse.org/projects/openSUSE:Factory/signing_keys/download"
    "?kind=gpg"
)


class OpenSUSE(Distro):
    name = "opensuse"
    description = "openSUSE Leap / Tumbleweed"
    options = {
        "release": Option(
            "tumbleweed",
            pattern=r"tumbleweed|\d+\.\d+",
            note="tumbleweed or a Leap version, e.g. 15.6",
        ),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://download.opensuse.org",
            note="upstream or mirror base URL",
            cli=False,
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        arch = params["arch"]
        base_url = params["base_url"]
        if release == "tumbleweed":
            base = f"{base_url}/tumbleweed/appliances/"
            pattern = (
                rf"(?:openSUSE-)?Tumbleweed-Minimal"
                rf"-VM\.{re.escape(arch)}-\d[\d.]*-Cloud-Snapshot\d+\.qcow2"
            )
        else:
            base = f"{base_url}/distribution/leap/{release}/appliances/"
            pattern = (
                rf"(?:openSUSE-)?Leap-{re.escape(release)}-Minimal"
                rf"-VM\.{re.escape(arch)}-Cloud\.qcow2"
            )
        filename = self.newest_in(base, pattern)
        checksum_url = f"{base}{filename}.sha256"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=checksum_url,
            algorithm="sha256",
            signature=Signature(
                url=f"{checksum_url}.asc",
                key_url=OPENSUSE_KEY_URL,
                fingerprint=OPENSUSE_SIGNING_KEY,
            ),
        )
