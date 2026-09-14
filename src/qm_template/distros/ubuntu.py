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
        if variant == "minimal":
            base = f"{self.base_url}/minimal/releases/{release}/release/"
            filename = self.newest_in(
                base, rf"ubuntu-[\d.]+-minimal-cloudimg-{re.escape(arch)}\.img"
            )
        elif variant == "server":
            base = f"{self.base_url}/{release}/current/"
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
        )
