import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

BASE_DIR = Path(__file__).resolve().parent

# Support DATABASE_URL or DB_PATH env var, defaulting to ./app.db relative to backend
DEFAULT_DB_FILE = BASE_DIR / "app.db"
ENV_DATABASE_URL = os.getenv("DATABASE_URL")
ENV_DB_PATH = os.getenv("DB_PATH")

if ENV_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = ENV_DATABASE_URL
elif ENV_DB_PATH:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{Path(ENV_DB_PATH).resolve()}"
else:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"

# check_same_thread=False is required for SQLite with FastAPI multi-threaded requests
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Enforce foreign key constraints in SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session.
    Automatically handles session closing and rollbacks on unhandled errors.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initializes database tables defined in Base metadata.
    """
    import models  # Ensure all models are imported before creating tables
    Base.metadata.create_all(bind=engine)
