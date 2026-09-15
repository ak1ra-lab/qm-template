import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError


class RockyLinux(Distro):
    name = "rocky"
    description = "Rocky Linux"
    options = {
        "release": Option("10", note="major version, e.g. 9, 10"),
        "variant": Option("GenericCloud", ("GenericCloud", "GenericCloud-LVM")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://dl.rockylinux.org/pub/rocky",
            note="upstream or mirror base URL",
        ),
    }

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
        base = f"{params['base_url']}/{release}/images/{arch}/"
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
    options = {
        "release": Option("10", note="major version, e.g. 9, 10"),
        "variant": Option("GenericCloud", ("GenericCloud", "GenericCloud-ext4")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://repo.almalinux.org/almalinux",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{params['base_url']}/{release}/cloud/{arch}/images/"
        filename = self.newest_in(
            base,
            rf"AlmaLinux-{re.escape(release)}-{re.escape(variant)}"
            rf"-\d[\d.]*-\d{{8}}(?:\.\d+)?\.{re.escape(arch)}\.qcow2",
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
    options = {
        "release": Option("44", note="release number, e.g. 43, 44"),
        "variant": Option("Generic", ("Generic", "UEFI-UKI")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "tag": Option(
            "", note="build number like 1.10; the newest is used when omitted"
        ),
        "base_url": Option(
            "https://download.fedoraproject.org/pub/fedora/linux/releases",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{params['base_url']}/{release}/Cloud/{arch}/images/"
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
    options = {
        "release": Option("10", note="major version, e.g. 9, 10"),
        "variant": Option("GenericCloud", ("GenericCloud",)),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://cloud.centos.org/centos",
            note="upstream or mirror base URL",
        ),
    }

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        variant = params["variant"]
        arch = params["arch"]
        base = f"{params['base_url']}/{release}-stream/{arch}/images/"
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
