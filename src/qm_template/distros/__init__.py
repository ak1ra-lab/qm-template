from qm_template.distros.alpine import Alpine
from qm_template.distros.archlinux import ArchLinux
from qm_template.distros.base import Distro, Option, RemoteImage
from qm_template.distros.debian import Debian
from qm_template.distros.opensuse import OpenSUSE
from qm_template.distros.redhat import AlmaLinux, CentOSStream, Fedora, RockyLinux
from qm_template.distros.ubuntu import Ubuntu

DISTROS: dict[str, Distro] = {
    distro.name: distro
    for distro in (
        Debian(),
        Ubuntu(),
        RockyLinux(),
        AlmaLinux(),
        Fedora(),
        CentOSStream(),
        Alpine(),
        OpenSUSE(),
        ArchLinux(),
    )
}

__all__ = ["DISTROS", "Distro", "Option", "RemoteImage"]
