"""Punto de entrada. Punto de control 2: las cuatro tablas y sus contratos (diap. 21–36)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registra las tablas en SQLModel.metadata)
from app.database import create_db_and_tables

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


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}
