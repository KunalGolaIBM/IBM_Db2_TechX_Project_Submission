from __future__ import annotations

from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .coaching import LangChainCoach
from .config import Settings
from .errors import AppError, DatabaseUnavailableError
from .models import (
    AnalyticsSummary,
    CoachingRequest,
    CoachingResponse,
    ErrorResponse,
    GameDetail,
    HealthResponse,
    PaginatedGames,
    SaveGameRequest,
    SaveGameResponse,
)
from .repository import Db2GameRepository
from .service import ChessService, Coach, GameRepository


def error_response(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "detail": detail}})


def create_app(
    settings: Settings | None = None,
    repository: GameRepository | None = None,
    coach: Coach | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or Db2GameRepository(settings.db2)
    coach = coach or LangChainCoach(settings)
    service = ChessService(repository, coach)

    app = FastAPI(
        title="Cinematic Chess IBM Db2 API",
        version="1.0.0",
        description="Single-user TechX demo API. No accounts or multi-user authorization.",
    )
    app.state.chess_service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "validation_error", "Request validation failed")

    @app.exception_handler(Exception)
    def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return error_response(500, "internal_error", "Unexpected server error")

    def get_service(request: Request) -> ChessService:
        return request.app.state.chess_service

    errors = {
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    }

    @app.get("/api/v1/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
    def health(service: ChessService = Depends(get_service)) -> HealthResponse | JSONResponse:
        try:
            service.health()
            enabled = settings.coach_provider != "disabled"
            return HealthResponse(
                status="ok",
                database="ok",
                coaching_enabled=enabled,
                llm_provider=settings.coach_provider if enabled else None,
            )
        except DatabaseUnavailableError:
            return error_response(503, "database_unavailable", "Db2 is unavailable")

    @app.post("/api/v1/games", response_model=SaveGameResponse, status_code=201, responses=errors)
    def save_game(payload: SaveGameRequest, response: Response, service: ChessService = Depends(get_service)) -> SaveGameResponse:
        result = service.save_game(payload)
        if not result.created:
            response.status_code = 200
        return result

    @app.get("/api/v1/games", response_model=PaginatedGames, responses=errors)
    def list_games(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        service: ChessService = Depends(get_service),
    ) -> PaginatedGames:
        return service.list_games(limit, offset)

    @app.get("/api/v1/games/{game_id}", response_model=GameDetail, responses=errors)
    def get_game(game_id: UUID, service: ChessService = Depends(get_service)) -> GameDetail:
        return service.get_game(game_id)

    @app.get("/api/v1/analytics/summary", response_model=AnalyticsSummary, responses=errors)
    def analytics_summary(service: ChessService = Depends(get_service)) -> AnalyticsSummary:
        return service.analytics_summary()

    @app.post("/api/v1/coaching", response_model=CoachingResponse, responses=errors)
    def coaching(payload: CoachingRequest, service: ChessService = Depends(get_service)) -> CoachingResponse:
        return service.coaching(payload.game_id)

    return app


app = create_app()
