import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError


class Ubuntu(Distro):
    name = "ubuntu"
    description = "Ubuntu cloud images"
    options = {
        "release": Option("resolute", note="codename, e.g. resolute, noble, jammy"),
        "variant": Option("server", ("server", "minimal")),
        "arch": Option("amd64", ("amd64", "arm64")),
        "base_url": Option(
            "https://cloud-images.ubuntu.com",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base_url = params["base_url"]
        tag = None
        if variant == "minimal":
            base = f"{base_url}/minimal/releases/{release}/release/"
            filename = self.newest_in(
                base, rf"ubuntu-[\d.]+-minimal-cloudimg-{re.escape(arch)}\.img"
            )
        elif variant == "server":
            builds = f"{base_url}/{release}/"
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
