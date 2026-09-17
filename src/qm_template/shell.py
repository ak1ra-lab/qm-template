import shlex
import subprocess
from collections.abc import Sequence

from qm_template.errors import QmTemplateError
from qm_template.log import log

CommandGroups = Sequence[Sequence[str]]
MASK = "********"


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
    argv: Sequence[str],
    *,
    capture: bool = False,
    secrets: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    """Run an external command, reporting failures to start it as QmTemplateError.

    Values listed in *secrets* are masked in the debug log.
    """
    display = [MASK if word in secrets else word for word in argv] if secrets else argv
    log.debug("Running: %s", shlex.join(display))
    try:
        return subprocess.run(argv, capture_output=capture, text=True)
    except OSError as exc:
        raise QmTemplateError(f"could not run {argv[0]}: {exc}") from exc
