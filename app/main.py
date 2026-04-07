import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.exceptions import HTTPException

from app.config import settings
from app.openapi_i18n import (
    API_DESCRIPTION_RU,
    build_redoc_html,
    get_localized_openapi_schema,
)
from app.routers import auth, admin, analytics, passport, dashboard_legacy
from app.schemas import HealthResponse
from app.utils.logging import setup_logging
from app.utils.metrics import ocr_requests_total

setup_logging(level=settings.LOG_LEVEL, json_format=(settings.LOG_FORMAT == "json"))

from app.limiter import limiter

OPENAPI_TAGS = [
    {"name": "auth", "description": "Получение JWT токена"},
    {"name": "admin", "description": "Управление пользователями и ролями"},
    {"name": "analytics", "description": "Сводка и аналитические отчеты"},
    {
        "name": "passport",
        "description": "OCR загрузка, статус и результаты распознавания",
    },
    {"name": "system", "description": "Служебные маршруты API"},
]

DOCS_PATHS = {
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/openapi-localized.json",
}


def _verify_token_from_request(request: Request) -> bool:
    """Проверяет JWT токен из заголовка, query или cookie."""
    import jwt as pyjwt

    token = None

    # 1. Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Query parameter
    if not token:
        token = request.query_params.get("token")

    # 3. Cookie
    if not token:
        token = request.cookies.get("ocr_api_token")

    if not token:
        return False

    try:
        pyjwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import models as app_models
    from app.database import Base, SessionLocal, engine
    from app.auth import create_initial_dashboard_user

    _ = app_models
    app.state.db_engine = engine
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        create_initial_dashboard_user(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=API_DESCRIPTION_RU.strip(),
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
    lifespan=lifespan,
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("app.access")
    logger.info(
        f"{request.method} {request.url.path}",
        extra={
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    response = await call_next(request)
    ocr_requests_total.labels(
        endpoint=request.url.path,
        status=str(response.status_code),
    ).inc()
    return response


@app.middleware("http")
async def protect_docs(request: Request, call_next):
    """Защищает /api/docs, /api/redoc, /api/openapi*.json авторизацией."""
    path = request.url.path

    if path in DOCS_PATHS:
        if not _verify_token_from_request(request):
            if path == "/api/redoc":
                from app.openapi_i18n import build_login_page

                lang = request.query_params.get("lang", "ru")
                return build_login_page(lang)
            return Response(
                content='{"detail": "Authentication required"}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)


# Маршруты для дашборда
@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard.html", include_in_schema=False)
@app.get("/dashboard_v2.html", include_in_schema=False)
async def serve_dashboard():
    from pathlib import Path

    cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    for candidate in ("dashboard.html", "dashboard_v2.html"):
        dashboard_path = Path(candidate)
        if dashboard_path.exists():
            return FileResponse(dashboard_path, headers=cache_headers)

    return {
        "error": "Dashboard file not found",
        "searched": [
            str(Path("dashboard.html").absolute()),
            str(Path("dashboard_v2.html").absolute()),
        ],
    }


# API маршруты
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(
    dashboard_legacy.router,
    prefix="/api/dashboard",
    tags=["dashboard-legacy"],
    include_in_schema=False,
)
app.include_router(passport.router, prefix="/api/passport", tags=["passport"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Проверить состояние API",
)
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/redoc", include_in_schema=False)
async def redoc_html(lang: str = Query("ru")):
    return build_redoc_html(app, lang)


@app.get("/api/openapi-localized.json", include_in_schema=False)
async def localized_openapi(lang: str = Query("ru")):
    return get_localized_openapi_schema(app, lang)


@app.get("/api/metrics", include_in_schema=False)
async def metrics():
    from app.utils.metrics import metrics_endpoint

    content, status_code, headers = metrics_endpoint()
    return Response(content=content, media_type=headers["Content-Type"])
