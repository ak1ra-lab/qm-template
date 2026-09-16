from collections.abc import Mapping

from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.errors import QmTemplateError


class Debian(Distro):
    name = "debian"
    description = "Debian GNU/Linux"
    options = {
        "release": Option(
            "trixie",
            ("buster", "bullseye", "bookworm", "trixie", "forky"),
            suffix=("-backports",),
        ),
        "variant": Option("genericcloud", ("generic", "genericcloud")),
        "arch": Option("amd64", ("amd64", "arm64")),
        "tag": Option("", note="dated build; the newest is used when omitted"),
        "base_url": Option(
            "https://cdimage.debian.org/images/cloud",
            note="upstream or mirror base URL",
            cli=False,
        ),
    }

    versions = {
        "buster": "10",
        "bullseye": "11",
        "bookworm": "12",
        "trixie": "13",
        "forky": "14",
    }

    def version(self, release: str) -> str:
        codename = release.removesuffix("-backports")
        try:
            version = self.versions[codename]
        except KeyError:
            supported = ", ".join(sorted(self.versions))
            raise QmTemplateError(
                f"unknown Debian codename {release!r} (supported: {supported})"
            ) from None
        return f"{version}-backports" if release.endswith("-backports") else version

    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        release = params["release"]
        version = self.version(release)
        base = f"{params['base_url']}/{release}/"
        tag = params.get("tag") or self.newest_in(base, r"\d{8}-\d+")
        filename = f"debian-{version}-{params['variant']}-{params['arch']}-{tag}.qcow2"
        return RemoteImage(
            distro=self.name,
            release=release,
            filename=filename,
            url=f"{base}{tag}/{filename}",
            checksum_url=f"{base}{tag}/SHA512SUMS",
            algorithm="sha512",
            tag=tag,
        )
