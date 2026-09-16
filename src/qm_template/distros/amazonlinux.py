import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage

VERSION = r"2023\.\d+\.\d{8}\.\d+"
ARCH_DIRS = {"x86_64": "kvm", "aarch64": "kvm-arm64"}
ARCH_TOKENS = {"x86_64": "x86_64", "aarch64": "arm64"}


class AmazonLinux(Distro):
    name = "amazonlinux"
    description = "Amazon Linux 2023"
    options = {
        "release": Option("latest", note="latest or a version like 2023.12.20260914.0"),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://cdn.amazonlinux.com/al2023/os-images",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        arch = params["arch"]
        arch_dir = ARCH_DIRS[arch]
        directory = (
            f"{params['base_url']}/latest/{arch_dir}/"
            if release == "latest"
            else f"{params['base_url']}/{release}/{arch_dir}/"
        )
        filename = self.newest_in(
            directory,
            rf"al2023-kvm-{VERSION}-kernel-[\d.]+"
            rf"-{re.escape(ARCH_TOKENS[arch])}\.xfs\.gpt\.qcow2",
        )
        match = re.fullmatch(rf"al2023-kvm-({VERSION})-kernel-.*", filename)
        assert match is not None
        release = match.group(1)
        base = f"{params['base_url']}/{release}/{arch_dir}/"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}SHA256SUMS",
            algorithm="sha256",
        )
