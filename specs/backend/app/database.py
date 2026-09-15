import os
from collections.abc import Generator
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    explicit = os.getenv("SPECS_DATABASE_URL")
    if explicit:
        return explicit
    password = os.getenv("SPECS_DB_PASSWORD")
    if password:
        return f"postgresql+psycopg://specs:{quote(password, safe='')}@specs-db:5432/specs"
    return "sqlite:///./specs-local.db"


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db
