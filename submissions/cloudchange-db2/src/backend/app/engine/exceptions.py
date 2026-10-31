"""Engine Exceptions.

Domain exceptions for plan validation, parsing, and normalization.
"""


class PlanEngineError(Exception):
    """Base exception for all CloudChange analysis engine errors."""
    pass


class PlanValidationError(PlanEngineError):
    """Raised when the input plan JSON is malformed, missing required fields, or invalid."""
    pass


class UnsupportedResourceError(PlanEngineError):
    """Raised when a plan contains resource types not supported in the active phase."""
    def __init__(self, resource_type: str, resource_address: str, supported_types: list[str]) -> None:
        self.resource_type = resource_type
        self.resource_address = resource_address
        self.supported_types = supported_types
        super().__init__(
            f"Resource '{resource_address}' has unsupported type '{resource_type}'. "
            f"Phase 1 strictly supports: {', '.join(sorted(supported_types))}."
        )


class InvalidActionError(PlanEngineError):
    """Raised when a resource change action combination is unrecognized or unhandled."""
    def __init__(self, actions: list[str], resource_address: str) -> None:
        self.actions = actions
        self.resource_address = resource_address
        super().__init__(
            f"Resource '{resource_address}' contains invalid or unhandled action array: {actions}."
        )
