import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError
from qm_template.signature import Signature

UBUNTU_SIGNING_KEY = "D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81"
UBUNTU_KEY_URL = (
    "https://keyserver.ubuntu.com/pks/lookup"
    f"?op=get&search=0x{UBUNTU_SIGNING_KEY}&options=mr"
)


class Ubuntu(Distro):
    name = "ubuntu"
    description = "Ubuntu cloud images"
    options = {
        "release": Option(
            "resolute",
            pattern=r"[a-z]+",
            note="codename, e.g. resolute, noble, jammy",
        ),
        "variant": Option("server", ("server", "minimal")),
        "arch": Option("amd64", ("amd64", "arm64")),
        "base_url": Option(
            "https://cloud-images.ubuntu.com",
            note="upstream or mirror base URL",
            cli=False,
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
            signature=Signature(
                url=f"{base}SHA256SUMS.gpg",
                key_url=UBUNTU_KEY_URL,
                fingerprint=UBUNTU_SIGNING_KEY,
            ),
        )
