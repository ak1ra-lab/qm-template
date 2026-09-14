import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, RemoteImage
from qm_template.errors import QmTemplateError


class Ubuntu(Distro):
    name = "ubuntu"
    description = "Ubuntu cloud images"
    defaults = {"release": "resolute", "variant": "server", "arch": "amd64"}

    base_url = "https://cloud-images.ubuntu.com"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        tag = None
        if variant == "minimal":
            base = f"{self.base_url}/minimal/releases/{release}/release/"
            filename = self.newest_in(
                base, rf"ubuntu-[\d.]+-minimal-cloudimg-{re.escape(arch)}\.img"
            )
        elif variant == "server":
            builds = f"{self.base_url}/{release}/"
            tag = self.newest_in(builds, r"\d{8}")
            base = f"{builds}{tag}/"
            filename = f"{release}-server-cloudimg-{arch}.img"
        else:
            raise QmTemplateError(
                f"unknown Ubuntu variant {variant!r} (use 'server' or 'minimal')"
            )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}SHA256SUMS",
            algorithm="sha256",
            tag=tag,
        )
