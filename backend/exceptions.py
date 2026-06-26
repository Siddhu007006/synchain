"""
Structured error hierarchy for SynChain.

All custom exceptions inherit from SynChainError, which carries:
  - message: human-readable description
  - status_code: HTTP status code for the response
  - error_type: machine-readable error category

The exception handler in main.py converts these to:
  { "detail": "...", "error_type": "..." }
"""


class SynChainError(Exception):
    """Base exception for all SynChain errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = 500,
        error_type: str = "INTERNAL_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(self.message)


class NotFoundError(SynChainError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, status_code=404, error_type="NOT_FOUND")


class ValidationError(SynChainError):
    """Raised when input data fails business-rule validation."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(
            message=message, status_code=422, error_type="VALIDATION_ERROR"
        )


class SimulationError(SynChainError):
    """Raised when the agent pipeline fails during simulation."""

    def __init__(self, message: str = "Simulation failed"):
        super().__init__(
            message=message, status_code=500, error_type="SIMULATION_ERROR"
        )
