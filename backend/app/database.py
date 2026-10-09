# --SQLAlchemy engine and base
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

_url = settings.database_url
_kwargs: dict = {"pool_pre_ping":True}
if _url.startswith("sqlite"):
    #SQLite is only used by the automated tests, so please be aware!
    _kwargs["poolclass"] = StaticPool
    
engine = create_engine(_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI: one session per request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()