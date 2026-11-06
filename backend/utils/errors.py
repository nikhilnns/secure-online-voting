"""Domain error type shared by controllers and routes."""


class ServiceError(Exception):
    """A business-rule violation that maps to an HTTP error response."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
