class AppError(Exception):
    """Base class for application errors that map to a specific HTTP status."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmailAlreadyRegisteredError(AppError):
    status_code = 409


class InvalidCredentialsError(AppError):
    status_code = 401


class NotFoundError(AppError):
    status_code = 404


class ForbiddenError(AppError):
    status_code = 403


class ToolNotFoundError(AppError):
    status_code = 400


class ToolValidationError(AppError):
    status_code = 400


class ToolAuthorizationError(AppError):
    status_code = 403


class ToolExecutionFailedError(AppError):
    """Raised when a tool's underlying operation fails (DB error, timeout, etc.).

    Caught by the agent executor - never allowed to surface as a false
    success to the user.
    """

    status_code = 502


class LLMProviderError(AppError):
    """Raised when the LLM backend itself is unreachable or errors out."""

    status_code = 502
