import re
from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError
from qm_template.signature import Signature

ROCKY_KEY_URL = "https://dl.rockylinux.org/pub/rocky/RPM-GPG-KEY-Rocky-{major}"
ROCKY_SIGNING_KEYS = {
    "9": "21CB256AE16FC54C6E652949702D426D350D275D",
    "10": "FC226859C0860BF0DDB95B085B106C736FEDFC85",
}

ALMA_KEY_URL = "https://repo.almalinux.org/almalinux/RPM-GPG-KEY-AlmaLinux-{major}"
ALMA_SIGNING_KEYS = {
    "9": "BF18AC2876178908D6E71267D36CB86CB86B3716",
    "10": "EE6DB7B98F5BF5EDD9DA0DE5DEE5C11CC2A1E572",
}

FEDORA_KEY_URL = "https://fedoraproject.org/fedora.gpg"
FEDORA_SIGNING_KEYS = {
    "44": "36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6",
}


class RockyLinux(Distro):
    name = "rocky"
    description = "Rocky Linux"
    options = {
        "release": Option(
            "10",
            pattern=r"\d+(?:\.\d+)?",
            note="major version, e.g. 9, 10",
        ),
        "variant": Option("GenericCloud", ("GenericCloud", "GenericCloud-LVM")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://dl.rockylinux.org/pub/rocky",
            note="upstream or mirror base URL",
            cli=False,
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
        major = release.split(".")[0]
        checksum_url = f"{base}{filename}.CHECKSUM"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=checksum_url,
            algorithm="sha256",
            signature=Signature(
                url=f"{checksum_url}.asc",
                key_url=ROCKY_KEY_URL.format(major=major),
                fingerprint=ROCKY_SIGNING_KEYS.get(major),
            ),
        )


class AlmaLinux(Distro):
    name = "almalinux"
    description = "AlmaLinux OS"
    options = {
        "release": Option(
            "10",
            pattern=r"\d+(?:\.\d+)?",
            note="major version, e.g. 9, 10",
        ),
        "variant": Option("GenericCloud", ("GenericCloud", "GenericCloud-ext4")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://repo.almalinux.org/almalinux",
            note="upstream or mirror base URL",
            cli=False,
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
        major = release.split(".")[0]
        checksum_url = f"{base}CHECKSUM"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=checksum_url,
            algorithm="sha256",
            signature=Signature(
                url=f"{checksum_url}.asc",
                key_url=ALMA_KEY_URL.format(major=major),
                fingerprint=ALMA_SIGNING_KEYS.get(major),
            ),
        )


class Fedora(Distro):
    name = "fedora"
    description = "Fedora Cloud"
    options = {
        "release": Option("44", pattern=r"\d+", note="release number, e.g. 43, 44"),
        "variant": Option("Generic", ("Generic", "UEFI-UKI")),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "tag": Option(
            "", note="build number like 1.10; the newest is used when omitted"
        ),
        "base_url": Option(
            "https://download.fedoraproject.org/pub/fedora/linux/releases",
            note="upstream or mirror base URL",
            cli=False,
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
        checksum_url = f"{base}Fedora-Cloud-{release}-{tag}-{arch}-CHECKSUM"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{filename}",
            checksum_url=checksum_url,
            algorithm="sha256",
            signature=Signature(
                url=checksum_url,
                key_url=FEDORA_KEY_URL,
                kind="clearsigned",
                fingerprint=FEDORA_SIGNING_KEYS.get(release),
            ),
        )


class CentOSStream(Distro):
    name = "centos"
    description = "CentOS Stream"
    options = {
        "release": Option("10", pattern=r"\d+", note="major version, e.g. 9, 10"),
        "variant": Option("GenericCloud", ("GenericCloud",)),
        "arch": Option("x86_64", ("x86_64", "aarch64")),
        "base_url": Option(
            "https://cloud.centos.org/centos",
            note="upstream or mirror base URL",
            cli=False,
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
