from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import auth, health, products, promotion_links, stores, users, workspace
from app.core.config import API_DIR, get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(health.router)
for route in [auth, products, promotion_links, stores, users, workspace]:
    app.include_router(route.router, prefix='/api/v1')
uploads_dir = API_DIR / 'uploads'
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=uploads_dir), name='uploads')
