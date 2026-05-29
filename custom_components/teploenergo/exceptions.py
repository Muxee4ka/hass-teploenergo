class TeploenergoError(Exception):
    """Base exception."""


class TeploenergoAuthError(TeploenergoError):
    """Authentication failed or session expired."""


class TeploenergoConnectionError(TeploenergoError):
    """Network or API error."""
