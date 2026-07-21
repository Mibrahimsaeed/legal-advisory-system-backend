from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.logging import configure_logging, get_logger
from config.settings import get_settings

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("app_starting", env=settings.app_env)
    yield
    # Shutdown
    logger.info("app_shutting_down")


def create_app() -> FastAPI:
    """
    Application factory. Keeping this as a function (rather than a bare
    module-level `app = FastAPI()`) makes it easy to spin up separate
    app instances for tests with different settings/overrides.
    """
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        # Hide interactive docs in production; keep them in development.
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url="/redoc" if settings.app_env == "development" else None,
    )

    # CORS origins now come from settings (.env) instead of a hardcoded "*",
    # so production can restrict to the real frontend domain only.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Phase 6 hardening middleware
    from app.common.security import SecurityHeadersMiddleware
    from app.common.request_logging import RequestLoggingMiddleware

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Global catch-all error handler: unexpected crashes return a clean,
    # generic 500 instead of leaking stack traces / internals to callers.
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred. Please try again later."},
        )

    register_routers(app)

    @app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok", "env": settings.app_env}

    return app


def register_routers(app: FastAPI) -> None:
    """
    Central place to register all feature routers.
    Keeping this separate from create_app() keeps main.py readable
    as more routers get added in later phases.
    """
    from app.auth.router import router as auth_router
    from app.users.router import router as users_router
    from app.conversations.router import router as conversations_router
    from app.documents.router import router as documents_router
    from app.chat.router import router as chat_router

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])


app = create_app()
