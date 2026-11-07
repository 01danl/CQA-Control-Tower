class ServiceError(Exception):
    """Safe public error. Never construct messages from upstream response bodies."""

    def __init__(self, status: int, code: str, message: str, details: dict | list | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(resource: str) -> ServiceError:
    return ServiceError(404, "NOT_FOUND", f"{resource} not found")
