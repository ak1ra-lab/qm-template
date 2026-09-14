"""Download cloud images and create Proxmox VE VM templates."""

from importlib.metadata import PackageNotFoundError, version

PROGRAM = "qm-template"

try:
    __version__ = version(PROGRAM)
except PackageNotFoundError:
    __version__ = "0.0.0"
