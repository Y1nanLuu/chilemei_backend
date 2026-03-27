from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

settings.food_record_media_root.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.project_name,
    version='0.1.0',
    lifespan=lifespan,
)

app.mount(settings.media_url_prefix, StaticFiles(directory=settings.media_root), name='media')
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get('/health', tags=['health'])
def health_check() -> dict[str, str]:
    return {'status': 'ok'}
