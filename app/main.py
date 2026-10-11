"""
CLH Backend — FastAPI application entrypoint.

No Redis. Sessions are DB-backed via SessionService.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.workers import expiry_sweep

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("clh")

_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background expiry sweep worker
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(expiry_sweep.run_forever(stop_event))

    logger.info("CLH backend started (env=%s)", _settings.env)
    try:
        yield
    finally:
        stop_event.set()
        try:
            await asyncio.wait_for(worker_task, timeout=5)
        except asyncio.TimeoutError:
            worker_task.cancel()
        logger.info("CLH backend stopped")


app = FastAPI(
    title=_settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not _settings.is_production else None,
    redoc_url="/redoc" if not _settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,  # required for session cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # tighten in prod


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(api_router, prefix=_settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "env": _settings.env}