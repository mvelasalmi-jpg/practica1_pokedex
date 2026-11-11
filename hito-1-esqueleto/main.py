"""Punto de entrada. Punto de control 1: entorno, configuración, base de datos y /health (diap. 9–20)."""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import create_db_and_tables

#se importa el resultado al que hemos llegado en routers 
from app.routers import pokedex

#configura los mensajes en la consola 
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s"
)
logger = logging.getLogger("pokedex_api")

#gestiona el ciclo de vida de la app: antes de encenderse, crea la base de datos
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("base de datos lista")
    yield
    logger.info("apagando")


#son los datos del servidor, inicializacion de la API
app = FastAPI(
    title="Pokédex API",
    version="1.0.0",
    description="API REST del Pokédex personal · Práctica 1",
    lifespan=lifespan,
)

#comprueba la ruta y el estado de la ruta 
@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}

#se conecta con la pokedex
app.include_router(pokedex.router, prefix="/api/v1")
