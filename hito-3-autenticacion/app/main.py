"""Punto de entrada. Punto de control 3: bcrypt, JWT, CurrentUser, registro y login (diap. 37–54)."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import create_db_and_tables
from app.limits import limiter
from app.routers import auth

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s"
)
logger = logging.getLogger("pokedex_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("base de datos lista")
    yield
    logger.info("apagando")


app = FastAPI(
    title="Pokédex API",
    version="1.0.0",
    description="API REST del Pokédex personal · Práctica 1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# @limiter.limit en los endpoints de auth necesita esto para funcionar.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def registrar_peticiones(request: Request, call_next):
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ms = (time.perf_counter() - inicio) * 1000
    logger.info(
        "%s %s → %s (%.1f ms)",
        request.method,
        request.url.path,
        respuesta.status_code,
        ms,
    )
    return respuesta


for modulo in (auth,):
    app.include_router(modulo.router, prefix="/api/v1")


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}
