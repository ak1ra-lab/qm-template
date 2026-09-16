from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from qm_template.errors import QmTemplateError
from qm_template.http import latest_name, list_directory
from qm_template.signature import Signature


@dataclass(frozen=True)
class Option:
    """A distro parameter with its default and the values it accepts."""

    default: str
    choices: tuple[str, ...] | None = None
    suffix: tuple[str, ...] = ()
    note: str = ""

    def accepts(self, value: str) -> bool:
        if self.choices is None:
            return True
        if value in self.choices:
            return True
        return any(
            value.endswith(suffix) and value.removesuffix(suffix) in self.choices
            for suffix in self.suffix
        )

    def completions(self, prefix: str) -> list[str]:
        values = list(self.choices or ())
        values.extend(
            f"{choice}{suffix}"
            for choice in self.choices or ()
            for suffix in self.suffix
        )
        return [value for value in values if value.startswith(prefix)]

    def describe(self) -> str:
        parts: list[str] = []
        if self.choices:
            text = ", ".join(self.choices)
            if self.suffix:
                text += f" (optionally with {' or '.join(self.suffix)})"
            parts.append(f"choices: {text}")
        if self.note:
            parts.append(self.note)
        return "; ".join(parts)


@dataclass(frozen=True)
class RemoteImage:
    distro: str
    release: str
    filename: str
    url: str
    checksum_url: str
    algorithm: str
    tag: str | None = None
    signature: Signature | None = None
    compression: Literal["xz"] | None = None

    @property
    def extracted_name(self) -> str:
        """Filename of the usable image after decompression."""
        if self.compression is None:
            return self.filename
        if self.compression == "xz" and self.filename.endswith(".xz"):
            return self.filename.removesuffix(".xz")
        raise QmTemplateError(
            f"cannot extract {self.filename!r} with compression {self.compression!r}"
        )

    @property
    def local_path(self) -> Path:
        """Path relative to the images directory, mirroring upstream."""
        parts = [self.distro, self.release]
        if self.tag:
            parts.append(self.tag)
        parts.append(self.filename)
        for part in parts:
            if part in {"", ".", ".."} or "/" in part or "\\" in part:
                raise QmTemplateError(f"unsafe image path component: {part!r}")
        return Path(*parts)


class Distro(ABC):
    """A cloud image provider that resolves download URLs and checksums."""

    name: ClassVar[str]
    description: ClassVar[str]
    options: ClassVar[Mapping[str, Option]] = {}

    @property
    def defaults(self) -> dict[str, str]:
        return {
            key: option.default
            for key, option in self.options.items()
            if option.default
        }

    @property
    def supports_tag(self) -> bool:
        return "tag" in self.options

    def merge(
        self,
        config_defaults: Mapping[str, str],
        overrides: Mapping[str, str | None],
    ) -> dict[str, str]:
        params = self.defaults
        for source in (config_defaults, overrides):
            for key, value in source.items():
                if value is None:
                    continue
                option = self.options.get(key)
                if option is None:
                    supported = ", ".join(sorted(self.options)) or "none"
                    raise QmTemplateError(
                        f"unknown parameter {key!r} for distro {self.name!r} "
                        f"(supported: {supported})"
                    )
                if not option.accepts(str(value)):
                    choices = ", ".join(option.choices or ())
                    raise QmTemplateError(
                        f"invalid {key} {value!r} for distro {self.name!r} "
                        f"(choose from: {choices})"
                    )
                params[key] = str(value)
        return params

    @staticmethod
    def newest_in(url: str, pattern: str) -> str:
        return latest_name(list_directory(url), pattern, source=url)

    @abstractmethod
    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        """Return the remote image described by the merged parameters."""
