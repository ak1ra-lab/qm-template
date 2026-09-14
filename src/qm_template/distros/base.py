from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from qm_template.errors import QmTemplateError
from qm_template.http import latest_name, list_directory


@dataclass(frozen=True)
class RemoteImage:
    distro: str
    release: str
    filename: str
    url: str
    checksum_url: str
    algorithm: str


class Distro(ABC):
    """A cloud image provider that resolves download URLs and checksums."""

    name: ClassVar[str]
    description: ClassVar[str]
    defaults: ClassVar[dict[str, str]] = {}
    supports_tag: ClassVar[bool] = False

    def merge(
        self,
        config_defaults: Mapping[str, str],
        overrides: Mapping[str, str | None],
    ) -> dict[str, str]:
        params = dict(self.defaults)
        for source in (config_defaults, overrides):
            for key, value in source.items():
                if value is None:
                    continue
                if key not in self.defaults and key != "tag":
                    raise QmTemplateError(
                        f"unknown parameter {key!r} for distro {self.name!r}"
                    )
                params[key] = str(value)
        return params

    @staticmethod
    def newest_in(url: str, pattern: str) -> str:
        return latest_name(list_directory(url), pattern, source=url)

    @abstractmethod
    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        """Return the remote image described by the merged parameters."""
