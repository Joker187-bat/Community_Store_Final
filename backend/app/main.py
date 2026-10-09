"""FastAPI app entry point

Run: uvicorn app.main:app --reload from within the backend folder
Docs: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models #Register tables on Base.metadata
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import admin, auth, bookings, bulletin, listings, messages, reviews
from .seed import ensure_admin, seed_demo_data, seed_reference_data

log = logging.getLogger("cput")

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    Base.metadata.create_all(bind=engine) #no-op when db/schema.sql is already created
    with SessionLocal() as db:
        seed_reference_data(db)
        ensure_admin(db)
        if settings.seed_demo:
            seed_demo_data(db)
        log.info("CPUT Community Store API already (env=%s)", settings.app_env)
        yield
        

app = FastAPI (
    title="CPUT Community Store API",
    version="1.0",
    description="Backend for the CPUT Community Store: Marketplace, bookings, "
    "messaging, reviews and bulletin board.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False #JWT travels in the Authorization header, not the cookies so keep it off
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api"
for r in (auth, listings, bookings, messages, reviews, bulletin, admin):
    app.include_router(r.router, prefix=API_PREFIX)
    
@app.get(f"{API_PREFIX}/health", tags=["System"])
def health():
    return {"status": "ok", "version": app.version}


# Serve the recoded frontend from the same origin
_frontend = Path(settings.frontend_dir)
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")