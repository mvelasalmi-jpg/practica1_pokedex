"""Versión 2 de la API (apartado 2.7 del enunciado: ejemplo de evolución).

¿Por qué existe una v2 si la v1 ya funciona?
La v1 devuelve la lista de la Pokédex como un array JSON «a pelo»:  [ {...}, {...} ]
La v2 devuelve un objeto con el total y los datos de paginación:
    {"total": 42, "limit": 20, "offset": 0, "items": [ {...}, {...} ]}
y además cada elemento trae `types` como lista de verdad (["grass", "poison"]).

Cambiar la FORMA de la respuesta rompería a los clientes que ya usan la v1. Por eso
no se modifica la v1: se publica una v2 al lado y las dos conviven mientras los
clientes se pasan a la nueva (ver «Versionado» en el README).
"""

from typing import Literal

from fastapi import APIRouter, Query, Request
from sqlmodel import func, select

from app.dependencies import CurrentUser, SessionDep
from app.limits import limiter
from app.models import PokedexEntryRead
from app.routers.pokedex import CampoOrden, filtrar, ordenar

router = APIRouter(prefix="/pokedex", tags=["pokedex (v2)"])


@router.get("")
@limiter.limit("100/minute")
def listar_v2(
    request: Request,
    usuario: CurrentUser,
    session: SessionDep,
    captured: bool | None = None,
    favorite: bool | None = None,
    sort: CampoOrden = "pokemon_id",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base = filtrar(usuario.id, captured, favorite)

    # Total SIN paginar: cuenta cuántas filas cumplen los filtros en total.
    total = session.exec(select(func.count()).select_from(base.subquery())).one()

    entradas = session.exec(
        ordenar(base, sort, order).offset(offset).limit(limit)
    ).all()

    items = []
    for entrada in entradas:
        # Reutilizamos el esquema de lectura de la v1 y le añadimos `types`.
        item = PokedexEntryRead.model_validate(entrada).model_dump(mode="json")
        item["types"] = (
            entrada.pokemon_types.split(",") if entrada.pokemon_types else []
        )
        items.append(item)

    return {"total": total, "limit": limit, "offset": offset, "items": items}
