import shlex
import subprocess
from collections.abc import Sequence

from qm_template.errors import QmTemplateError
from qm_template.log import log

CommandGroups = Sequence[Sequence[str]]


def flatten(groups: CommandGroups) -> list[str]:
    """Join grouped words into a flat argument vector."""
    return [word for group in groups for word in group]


def pretty(groups: CommandGroups) -> str:
    """Render grouped words as a multi-line shell command."""
    lines = [shlex.join(group) for group in groups]
    return " \\\n".join(
        line if index == 0 else f"    {line}" for index, line in enumerate(lines)
    )


def run(
    argv: Sequence[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run an external command, reporting failures to start it as QmTemplateError."""
    log.debug("Running: %s", shlex.join(argv))
    try:
        return subprocess.run(argv, capture_output=capture, text=True)
    except OSError as exc:
        raise QmTemplateError(f"could not run {argv[0]}: {exc}") from exc
