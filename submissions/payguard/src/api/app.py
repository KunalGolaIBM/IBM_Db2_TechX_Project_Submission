"""Application lifecycle, HTTP middleware, and v1 route aliases."""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from api.routes import STATIC, router
from api.security import PerIPRateLimiter
from config import settings
from observability import configure_logging, request_id, runtime
from services.container import get_services

configure_logging()
log = logging.getLogger("payguard.http")


@asynccontextmanager
async def lifespan(app):
    # Only production composition opens Db2; tests supply their own services.
    services = None
    if get_services not in app.dependency_overrides:
        services = get_services()
        try:
            await run_in_threadpool(services.repo.pool.warm)
        except Exception:
            log.warning("db2_startup_unavailable")
    try:
        yield
    finally:
        if services is not None:
            await run_in_threadpool(services.repo.close)
            get_services.cache_clear()


app = FastAPI(title="PayGuard", version="1.1.0", lifespan=lifespan)
app.state.limiter = PerIPRateLimiter(settings.rate_limit_per_minute, settings.rate_limit_max_ips)


@app.middleware("http")
async def instrument(request, call_next):
    supplied = request.headers.get("x-request-id", "")
    rid = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid.uuid4().hex
    token = request_id.set(rid)
    started, status = time.perf_counter(), 500
    try:
        path = request.url.path
        normalized = path.replace("/api/v1/", "/api/", 1)
        protected = {"/api/screen", "/api/screen-image", "/api/report", "/api/checkout/verify",
                     "/api/demo/checkout/verify", "/api/agent/purchase", "/share"}
        retry = app.state.limiter.admit(request.client.host if request.client else "unknown") if (
            request.method == "POST" and normalized in protected) else 0
        if retry:
            response = JSONResponse({"detail": "Rate limit exceeded"}, status_code=429,
                                    headers={"Retry-After": str(retry)})
        else:
            response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    except Exception as exc:
        log.error("request_failed", extra={"error_type": type(exc).__name__})
        return JSONResponse({"detail": "Request could not be completed"}, status_code=500,
                            headers={"X-Request-ID": rid})
    finally:
        duration = time.perf_counter() - started
        runtime.observe(status, duration)
        log.info("request_completed", extra={"path": request.url.path, "status": status,
                                             "duration_ms": round(duration * 1000, 3)})
        request_id.reset(token)


# Both paths use the very same handler, dependency validation and limiter bucket.
for route in list(router.routes):
    if isinstance(route, APIRoute) and route.path.startswith("/api/") and not route.path.startswith("/api/v1/"):
        if route.path.startswith("/api/demo/") or route.path == "/api/checkout/verify":
            continue
        router.add_api_route(route.path.replace("/api/", "/api/v1/", 1), route.endpoint,
                             methods=sorted(route.methods or []), name=route.name + "_v1")
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
