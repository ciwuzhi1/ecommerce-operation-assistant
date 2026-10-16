from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import (
    agent_platform,
    agent_runs,
    auth,
    health,
    model_settings,
    products,
    promotion_links,
    stores,
    users,
    workspace,
)
from app.core.config import API_DIR, get_settings
from app.core.errors import ApiError

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


@app.exception_handler(ApiError)
async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    """把带错误码的业务异常转为响应（DesignSpec §6 错误码体系 / ADR-07）。"""
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    """保留既有 HTTP 语义，仅在异常携带错误码时附加 code 字段（ADR-07 增量演进）。"""
    content: dict = {"detail": exc.detail}
    code = getattr(exc, "code", None)
    if code:
        content["code"] = code
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


app.include_router(health.router)
for route in [agent_platform, agent_runs, auth, model_settings, products, promotion_links, stores, users, workspace]:
    app.include_router(route.router, prefix='/api/v1')
uploads_dir = API_DIR / 'uploads'
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=uploads_dir), name='uploads')
