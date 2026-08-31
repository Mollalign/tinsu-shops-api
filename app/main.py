from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.categories.router import router as categories_router
from app.common.exceptions import AppException
from app.config import settings
from app.inventory.router import router as inventory_router
from app.owners.router import router as owners_router
from app.products.router import router as products_router
from app.public.router import router as public_router
from app.reports.router import router as reports_router
from app.sales.router import router as sales_router
from app.shops.router import router as shops_router
from app.workers.router import router as workers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production-ready REST API for Tinsu-Shops — a shop management and POS system "
            "designed for Ethiopian small retail businesses."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS — tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler for AppException subclasses
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # API v1 routers
    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(public_router, prefix=prefix)
    app.include_router(owners_router, prefix=prefix)
    app.include_router(shops_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)  # before workers — /me/today must match first
    app.include_router(workers_router, prefix=prefix)
    app.include_router(categories_router, prefix=prefix)
    app.include_router(products_router, prefix=prefix)
    app.include_router(inventory_router, prefix=prefix)
    app.include_router(sales_router, prefix=prefix)

    @app.get("/api/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()
