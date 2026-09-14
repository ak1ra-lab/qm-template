import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, RemoteImage
from qm_template.errors import QmTemplateError


class RockyLinux(Distro):
    name = "rocky"
    description = "Rocky Linux"
    defaults = {"release": "9", "variant": "GenericCloud", "arch": "x86_64"}

    base_url = "https://dl.rockylinux.org/pub/rocky"
    variants = {
        "GenericCloud": "GenericCloud-Base",
        "GenericCloud-LVM": "GenericCloud-LVM",
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        try:
            name_part = self.variants[variant]
        except KeyError:
            supported = ", ".join(sorted(self.variants))
            raise QmTemplateError(
                f"unknown Rocky Linux variant {variant!r} (supported: {supported})"
            ) from None
        base = f"{self.base_url}/{release}/images/{arch}/"
        filename = self.newest_in(
            base,
            rf"Rocky-{re.escape(release)}-{re.escape(name_part)}"
            rf"-\d[\d.]*-\d{{8}}\.\d+\.{re.escape(arch)}\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.CHECKSUM",
            algorithm="sha256",
        )


class AlmaLinux(Distro):
    name = "almalinux"
    description = "AlmaLinux OS"
    defaults = {"release": "9", "variant": "GenericCloud", "arch": "x86_64"}

    base_url = "https://repo.almalinux.org/almalinux"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{self.base_url}/{release}/cloud/{arch}/images/"
        filename = self.newest_in(
            base,
            rf"AlmaLinux-{re.escape(release)}-{re.escape(variant)}"
            rf"-\d[\d.]*-\d{{8}}\.{re.escape(arch)}\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}CHECKSUM",
            algorithm="sha256",
        )


class Fedora(Distro):
    name = "fedora"
    description = "Fedora Cloud"
    defaults = {"release": "44", "variant": "Generic", "arch": "x86_64"}
    supports_tag = True

    base_url = "https://download.fedoraproject.org/pub/fedora/linux/releases"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{self.base_url}/{release}/Cloud/{arch}/images/"
        pattern = (
            rf"Fedora-Cloud-Base-{re.escape(variant)}-{re.escape(release)}"
            rf"-(\d[\d.]*)\.{re.escape(arch)}\.qcow2"
        )
        tag = params.get("tag")
        if tag:
            filename = f"Fedora-Cloud-Base-{variant}-{release}-{tag}.{arch}.qcow2"
        else:
            filename = self.newest_in(base, pattern)
            match = re.fullmatch(pattern, filename)
            assert match is not None
            tag = match.group(1)
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}Fedora-Cloud-{release}-{tag}-{arch}-CHECKSUM",
            algorithm="sha256",
        )


class CentOSStream(Distro):
    name = "centos"
    description = "CentOS Stream"
    defaults = {"release": "9", "variant": "GenericCloud", "arch": "x86_64"}

    base_url = "https://cloud.centos.org/centos"

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{self.base_url}/{release}-stream/{arch}/images/"
        filename = self.newest_in(
            base,
            rf"CentOS-Stream-{re.escape(variant)}-{re.escape(arch)}"
            rf"-{re.escape(release)}-\d{{8}}\.\d+\.{re.escape(arch)}\.qcow2",
        )
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=f"{base}{filename}.SHA256SUM",
            algorithm="sha256",
        )
