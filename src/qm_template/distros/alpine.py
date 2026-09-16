import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError
from qm_template.signature import Signature

ALPINE_SIGNING_KEY = "F26ADFADBAE702EF7AF637459DA7EF23BFFCDF22"
ALPINE_KEY_URL = "https://alpinelinux.org/keys/tomalok.asc"

FIRMWARE_BY_ARCH = {"x86_64": ("bios", "uefi"), "aarch64": ("uefi",)}
DEFAULT_FIRMWARE = {"x86_64": "bios", "aarch64": "uefi"}


class Alpine(Distro):
    name = "alpine"
    description = "Alpine Linux"
    options = {
        "release": Option(
            "3.24",
            pattern=r"\d+\.\d+",
            note="version series, e.g. 3.23, 3.24",
        ),
        "variant": Option("generic", ("generic", "nocloud")),
        "firmware": Option(
            "auto",
            ("auto", "bios", "uefi"),
            note="auto: bios on x86_64, uefi on aarch64",
        ),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://dl-cdn.alpinelinux.org/alpine",
            note="upstream or mirror base URL",
            cli=False,
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        arch = params["arch"]
        firmware = params["firmware"]
        if firmware == "auto":
            firmware = DEFAULT_FIRMWARE[arch]
        if firmware not in FIRMWARE_BY_ARCH[arch]:
            raise QmTemplateError(
                f"Alpine {arch} images only come with "
                f"{', '.join(FIRMWARE_BY_ARCH[arch])} firmware"
            )
        base = f"{params['base_url']}/v{release}/releases/cloud/"
        filename = self.newest_in(
            base,
            rf"{re.escape(params['variant'])}_alpine-{re.escape(release)}\.\d+"
            rf"-{re.escape(arch)}-{re.escape(firmware)}-cloudinit-r\d+\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.sha512",
            algorithm="sha512",
            signature=Signature(
                url=f"{base}{filename}.asc",
                key_url=ALPINE_KEY_URL,
                target="image",
                fingerprint=ALPINE_SIGNING_KEY,
            ),
        )
