"""CRUD de la Pokédex personal: cada usuario sólo ve y toca lo suyo."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from app.dependencies import CurrentUser, ServicioPokeAPI, SessionDep
from app.models import (
    PokedexEntry,
    PokedexEntryCreate,
    PokedexEntryRead,
    PokedexEntryUpdate,
    TeamMember,
    ahora,
)

router = APIRouter(prefix="/pokedex", tags=["pokedex"])

# El texto que llega en ?sort= se traduce a columna aquí. Nunca se pega en el SQL.
ORDENABLE = {
    "pokemon_id": PokedexEntry.pokemon_id,
    "pokemon_name": PokedexEntry.pokemon_name,
    "capture_date": PokedexEntry.capture_date,
}


@router.post("", response_model=PokedexEntryRead, status_code=status.HTTP_201_CREATED)
async def anadir(
    datos: PokedexEntryCreate,
    usuario: CurrentUser,
    session: SessionDep,
    poke: ServicioPokeAPI,
):
    ya_esta = session.exec(
        select(PokedexEntry).where(
            PokedexEntry.owner_id == usuario.id,
            PokedexEntry.pokemon_id == datos.pokemon_id,
        )
    ).first()
    if ya_esta:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya está en tu Pokédex")

    info = await poke.get_pokemon(datos.pokemon_id)
    entrada = PokedexEntry(
        **datos.model_dump(),
        owner_id=usuario.id,
        pokemon_name=info["name"],
        pokemon_sprite=info["sprite"],
        capture_date=ahora() if datos.is_captured else None,
    )
    session.add(entrada)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya está en tu Pokédex")
    session.refresh(entrada)
    return entrada


@router.get("", response_model=list[PokedexEntryRead])
def listar(
    usuario: CurrentUser,
    session: SessionDep,
    captured: bool | None = None,
    favorite: bool | None = None,
    sort: Literal["pokemon_id", "pokemon_name", "capture_date"] = "pokemon_id",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    consulta = select(PokedexEntry).where(PokedexEntry.owner_id == usuario.id)
    if captured is not None:
        consulta = consulta.where(PokedexEntry.is_captured == captured)
    if favorite is not None:
        consulta = consulta.where(PokedexEntry.favorite == favorite)
    columna = ORDENABLE[sort]
    consulta = consulta.order_by(columna.desc() if order == "desc" else columna.asc())
    return session.exec(consulta.offset(offset).limit(limit)).all()


def _contar(session, *condiciones) -> int:
    consulta = select(func.count()).select_from(PokedexEntry)
    for condicion in condiciones:
        consulta = consulta.where(condicion)
    return session.exec(consulta).one()


# /stats va ANTES que /{entry_id}: si no, FastAPI intentaría leer "stats" como un id.
@router.get("/stats")
def estadisticas(usuario: CurrentUser, session: SessionDep):
    mias = PokedexEntry.owner_id == usuario.id
    total = _contar(session, mias)
    capturados = _contar(session, mias, PokedexEntry.is_captured)
    favoritos = _contar(session, mias, PokedexEntry.favorite)
    porcentaje = round(100 * capturados / total, 1) if total else 0.0
    return {
        "total_pokemon": total,
        "captured": capturados,
        "favorites": favoritos,
        "completion_percentage": porcentaje,
    }


def _entrada_propia(session, entry_id: int, usuario) -> PokedexEntry:
    entrada = session.get(PokedexEntry, entry_id)
    # 404 también si es de otro: no confirmamos que exista.
    if entrada is None or entrada.owner_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No está en tu Pokédex")
    return entrada


@router.get("/{entry_id}", response_model=PokedexEntryRead)
def detalle(entry_id: int, usuario: CurrentUser, session: SessionDep):
    return _entrada_propia(session, entry_id, usuario)


@router.patch("/{entry_id}", response_model=PokedexEntryRead)
def actualizar(
    entry_id: int, datos: PokedexEntryUpdate, usuario: CurrentUser, session: SessionDep
):
    entrada = _entrada_propia(session, entry_id, usuario)
    cambios = datos.model_dump(exclude_unset=True)
    # Regla de negocio: capturar pone fecha (si no la mandan); soltar la quita.
    if cambios.get("is_captured") is True and "capture_date" not in cambios:
        if entrada.capture_date is None:
            cambios["capture_date"] = ahora()
    elif cambios.get("is_captured") is False:
        cambios["capture_date"] = None
    entrada.sqlmodel_update(cambios)
    session.add(entrada)
    session.commit()
    session.refresh(entrada)
    return entrada


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(entry_id: int, usuario: CurrentUser, session: SessionDep):
    entrada = _entrada_propia(session, entry_id, usuario)
    # Si estaba en algún equipo, sale también de él: no dejamos miembros huérfanos.
    for miembro in session.exec(
        select(TeamMember).where(TeamMember.pokedex_entry_id == entrada.id)
    ):
        session.delete(miembro)
    session.delete(entrada)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
