from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            LIMIT 1
            """
        ),
        {
            'schema': settings.mysql_db,
            'table_name': table_name,
            'column_name': column_name,
        },
    ).scalar()
    return bool(result)


def ensure_user_preference_columns() -> None:
    statements = [
        ('taste_preferences', "ALTER TABLE users ADD COLUMN taste_preferences JSON NULL"),
        ('taboo_list', "ALTER TABLE users ADD COLUMN taboo_list JSON NULL"),
        ('spicy_level', "ALTER TABLE users ADD COLUMN spicy_level TINYINT NOT NULL DEFAULT 0"),
    ]
    with engine.begin() as connection:
        for column_name, statement in statements:
            if _column_exists(connection, 'users', column_name):
                continue
            connection.execute(text(statement))


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    ensure_user_preference_columns()
    yield


app = FastAPI(
    title=settings.project_name,
    version='0.1.0',
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get('/health', tags=['health'])
def health_check() -> dict[str, str]:
    return {'status': 'ok'}
