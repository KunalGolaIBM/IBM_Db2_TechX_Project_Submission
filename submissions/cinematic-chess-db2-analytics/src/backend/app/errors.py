class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidGameError(AppError):
    status_code = 422
    code = "invalid_game"


class GameNotFoundError(AppError):
    status_code = 404
    code = "game_not_found"


class GameConflictError(AppError):
    status_code = 409
    code = "game_conflict"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"


class CoachingUnavailableError(AppError):
    status_code = 503
    code = "coaching_unavailable"


class CoachingDisabledError(CoachingUnavailableError):
    code = "coaching_disabled"


class LlmNotConfiguredError(CoachingUnavailableError):
    code = "llm_not_configured"

