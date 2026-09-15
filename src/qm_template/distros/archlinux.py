from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage


class ArchLinux(Distro):
    name = "archlinux"
    description = "Arch Linux"
    options = {
        "release": Option("latest", note="latest or a build, e.g. v20260901.583572"),
        "variant": Option("cloudimg", ("cloudimg", "basic")),
        "arch": Option("x86_64", ("x86_64",)),
        "base_url": Option(
            "https://geo.mirror.pkgbuild.com/images",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base_url = params["base_url"]
        if release == "latest":
            release = self.newest_in(f"{base_url}/", r"v\d{8}\.\d+")
        base = f"{base_url}/{release}/"
        filename = f"Arch-Linux-{arch}-{variant}.qcow2"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.SHA256",
            algorithm="sha256",
        )
