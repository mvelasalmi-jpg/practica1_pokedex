"""Punto de entrada de la aplicación: aquí se monta todo.

Orden de lo que ocurre en este fichero:
  1. Se configura el logging (consola + fichero pokedex_api.log).
  2. Se crea la app FastAPI y se le añaden CORS, rate limiting y logging de peticiones.
  3. Se registran los manejadores de errores (validación, autenticación, rate limit).
  4. Se montan los routers bajo /api/v1 (y el ejemplo de v2 bajo /api/v2).
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import create_db_and_tables
from app.limits import limiter
from app.routers import auth, pokedex, pokedex_v2, pokemon, teams

# ───────────────────────────── 1. Logging ─────────────────────────────
# Dos destinos: la consola (para verlo mientras desarrollas) y un fichero
# (para revisarlo después). El fichero está en .gitignore: nunca se sube.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pokedex_api.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pokedex_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta al arrancar (antes del yield) y al apagar (después).
    create_db_and_tables()
    logger.info("base de datos lista")
    yield
    logger.info("apagando")


# ───────────────────────────── 2. La app y sus middlewares ─────────────────────────────
app = FastAPI(
    title="Pokédex API",
    version="1.0.0",
    description="API REST del Pokédex personal · Práctica 1",
    lifespan=lifespan,
)

# CORS: le dice al NAVEGADOR qué páginas web pueden llamar a esta API.
# Sólo los orígenes de la lista (config.py / .env); cualquier otra web queda bloqueada.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,  # el navegador recuerda la respuesta de CORS durante 1 hora
)

# Rate limiting: @limiter.limit(...) en los endpoints necesita estas dos líneas.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def registrar_peticiones(request: Request, call_next):
    """Anota en el log TODAS las peticiones: método, ruta, código y duración."""
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


# ───────────────────────────── 3. Manejadores de errores ─────────────────────────────


@app.exception_handler(RequestValidationError)
async def error_de_validacion(request: Request, exc: RequestValidationError):
    """Formato único para los 422: el cliente recibe SIEMPRE esta misma forma.

    {"detail": "Datos de entrada no válidos",
     "errors": [{"campo": "body.password", "mensaje": "..."}]}
    """
    errores = [
        {
            "campo": ".".join(str(parte) for parte in error["loc"]),
            "mensaje": error["msg"],
        }
        for error in exc.errors()
    ]
    # Se registran los campos y mensajes, NUNCA los valores recibidos: podrían ser
    # contraseñas y no deben acabar escritas en un fichero de log.
    logger.warning(
        "Validación fallida en %s %s: %s", request.method, request.url.path, errores
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Datos de entrada no válidos", "errors": errores},
    )


@app.exception_handler(StarletteHTTPException)
async def error_http(request: Request, exc: StarletteHTTPException):
    """Deja las respuestas de error como FastAPI las da, pero anota los fallos de auth."""
    if exc.status_code in (401, 403):
        logger.warning(
            "Error de autenticación: %s %s → %s",
            request.method,
            request.url.path,
            exc.status_code,
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(RateLimitExceeded)
async def limite_excedido(request: Request, exc: RateLimitExceeded):
    """Anota el exceso de peticiones y responde 429 como siempre."""
    ip = request.client.host if request.client else "desconocida"
    logger.warning(
        "Rate limit excedido: %s %s desde %s (%s)",
        request.method,
        request.url.path,
        ip,
        exc.detail,
    )
    return _rate_limit_exceeded_handler(request, exc)


# ───────────────────────────── 4. Rutas y versionado ─────────────────────────────
# v1: la versión estable. Cada router lleva su propio prefijo (/pokedex, /teams...).
for modulo in (auth, pokemon, pokedex, teams):
    app.include_router(modulo.router, prefix="/api/v1")

# v2: ejemplo de evolución de la API. Convive con la v1 sin romperla.
app.include_router(pokedex_v2.router, prefix="/api/v2")


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}
