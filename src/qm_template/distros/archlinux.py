from collections.abc import Mapping

from qm_template.distros.base import Distro, RemoteImage


class ArchLinux(Distro):
    name = "archlinux"
    description = "Arch Linux"
    defaults = {"release": "latest", "variant": "cloudimg", "arch": "x86_64"}

    base_url = "https://geo.mirror.pkgbuild.com/images"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        if release == "latest":
            release = self.newest_in(f"{self.base_url}/", r"v\d{8}\.\d+")
        base = f"{self.base_url}/{release}/"
        filename = f"Arch-Linux-{arch}-{variant}.qcow2"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.SHA256",
            algorithm="sha256",
        )
