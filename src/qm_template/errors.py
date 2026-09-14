class QmTemplateError(Exception):
    """An expected failure that should be reported without a traceback."""


class UserCancelled(Exception):
    """Raised when the user aborts an interactive prompt."""
