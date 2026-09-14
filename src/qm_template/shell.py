import shlex
from collections.abc import Sequence

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
