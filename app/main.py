from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten this before production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    # Phase 1: no feature routers yet.
    # Phase 2+ will add, e.g.:
    #   from app.auth.router import router as auth_router
    #   app.include_router(auth_router, prefix="/auth", tags=["auth"])
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

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])


app = create_app()
