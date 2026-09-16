import re
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

    default: str = ""
    choices: tuple[str, ...] = ()
    suffix: tuple[str, ...] = ()
    pattern: str = ""
    note: str = ""
    cli: bool = True

    def accepts(self, value: str) -> bool:
        if self.choices:
            if value in self.choices:
                return True
            if any(
                value.endswith(suffix) and value.removesuffix(suffix) in self.choices
                for suffix in self.suffix
            ):
                return True
            if not self.pattern:
                return False
        if self.pattern:
            return re.fullmatch(self.pattern, value) is not None
        return True

    def expectation(self) -> str:
        if self.choices:
            text = f"choose from: {', '.join(self.choices)}"
            if self.pattern:
                text += f" or match {self.pattern!r}"
            return text
        if self.pattern:
            return f"must match {self.pattern!r}"
        return "any value is accepted"

    def completions(self, prefix: str) -> list[str]:
        values = list(self.choices)
        values.extend(
            f"{choice}{suffix}" for choice in self.choices for suffix in self.suffix
        )
        return [value for value in values if value.startswith(prefix)]

    def describe(self) -> str:
        parts: list[str] = []
        if self.choices:
            text = ", ".join(self.choices)
            if self.suffix:
                text += f" (optionally with {' or '.join(self.suffix)})"
            parts.append(f"choices: {text}")
        if self.pattern:
            parts.append(f"pattern: {self.pattern}")
        if self.note:
            parts.append(self.note)
        if not self.cli:
            parts.append("config file only")
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
                    raise QmTemplateError(
                        f"invalid {key} {value!r} for distro {self.name!r} "
                        f"({option.expectation()})"
                    )
                params[key] = str(value)
        return params

    @staticmethod
    def newest_in(url: str, pattern: str) -> str:
        return latest_name(list_directory(url), pattern, source=url)

    @abstractmethod
    def resolve(self, params: Mapping[str, str]) -> RemoteImage:
        """Return the remote image described by the merged parameters."""
