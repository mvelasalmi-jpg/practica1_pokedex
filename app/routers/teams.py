"""Grupo 4 del enunciado: equipos de batalla (máximo 6 Pokémon).

Un equipo se guarda en dos tablas:
  - Team:       los datos del equipo (nombre, descripción, entrenador).
  - TeamMember: una fila por cada Pokémon del equipo, con su posición (1 a 6).
Cada TeamMember apunta a una entrada de la Pokédex del usuario, no a un Pokémon
suelto: por eso sólo se pueden meter Pokémon que ya están en TU Pokédex.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlmodel import select

from app.dependencies import CurrentUser, ServicioPokeAPI, SessionDep
from app.limits import limiter
from app.models import (
    PokedexEntry,
    Team,
    TeamCreate,
    TeamMember,
    TeamMemberRead,
    TeamRead,
    TeamUpdate,
)
from app.services.pdf_service import equipo_pdf

router = APIRouter(prefix="/teams", tags=["teams"])

LIMITE = "100/minute"


# ───────────────────────────── ayudas internas ─────────────────────────────


def _resolver_miembros(session, usuario, pokemon_ids: list[int]) -> list[PokedexEntry]:
    """Convierte la lista de pokemon_id en entradas de la Pokédex DEL USUARIO.

    Devuelve las entradas en el mismo orden en que llegaron los ids (ese orden
    será la posición dentro del equipo). Si alguno no está en su Pokédex → 422.
    """
    entradas = session.exec(
        select(PokedexEntry).where(
            PokedexEntry.owner_id == usuario.id,
            PokedexEntry.pokemon_id.in_(pokemon_ids),
        )
    ).all()
    por_id = {e.pokemon_id: e for e in entradas}
    faltan = [i for i in pokemon_ids if i not in por_id]
    if faltan:
        raise HTTPException(
            422,
            f"Estos Pokémon no están en tu Pokédex: {faltan}",
        )
    return [por_id[i] for i in pokemon_ids]


def _equipo_propio(session, team_id: int, usuario) -> Team:
    equipo = session.get(Team, team_id)
    # 404 también si es de otro entrenador: no revelamos que exista.
    if equipo is None or equipo.trainer_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return equipo


def _guardar_miembros(session, equipo: Team, entradas: list[PokedexEntry]) -> None:
    for posicion, entrada in enumerate(entradas, start=1):
        session.add(
            TeamMember(
                team_id=equipo.id, pokedex_entry_id=entrada.id, position=posicion
            )
        )


def _a_lectura(session, equipo: Team) -> TeamRead:
    """Monta la respuesta: el equipo con sus miembros ordenados por posición."""
    miembros = []
    for miembro in sorted(equipo.members, key=lambda m: m.position):
        entrada = session.get(PokedexEntry, miembro.pokedex_entry_id)
        miembros.append(
            TeamMemberRead(
                position=miembro.position,
                pokemon_id=entrada.pokemon_id,
                pokemon_name=entrada.pokemon_name,
                pokemon_sprite=entrada.pokemon_sprite,
                nickname=entrada.nickname,
            )
        )
    return TeamRead(
        id=equipo.id,
        name=equipo.name,
        description=equipo.description,
        created_at=equipo.created_at,
        members=miembros,
    )


# ───────────────────────────── endpoints ─────────────────────────────


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMITE)
def crear_equipo(
    request: Request, datos: TeamCreate, usuario: CurrentUser, session: SessionDep
):
    # El máximo de 6 y la ausencia de repetidos ya los ha comprobado el esquema
    # TeamCreate (si no se cumplen, FastAPI responde 422 antes de llegar aquí).
    entradas = _resolver_miembros(session, usuario, datos.pokemon_ids)

    equipo = Team(trainer_id=usuario.id, name=datos.name, description=datos.description)
    session.add(equipo)
    session.flush()  # flush = «mándalo ya a la BD» para que equipo.id exista, sin cerrar la transacción
    _guardar_miembros(session, equipo, entradas)
    session.commit()
    session.refresh(equipo)
    return _a_lectura(session, equipo)


@router.get("", response_model=list[TeamRead])
@limiter.limit(LIMITE)
def listar_equipos(request: Request, usuario: CurrentUser, session: SessionDep):
    equipos = session.exec(
        select(Team).where(Team.trainer_id == usuario.id).order_by(Team.id)
    ).all()
    return [_a_lectura(session, e) for e in equipos]


@router.put("/{team_id}", response_model=TeamRead)
@limiter.limit(LIMITE)
def actualizar_equipo(
    request: Request,
    team_id: int,
    datos: TeamUpdate,
    usuario: CurrentUser,
    session: SessionDep,
):
    equipo = _equipo_propio(session, team_id, usuario)
    cambios = datos.model_dump(exclude_unset=True)

    if "name" in cambios and cambios["name"] is not None:
        equipo.name = cambios["name"]
    if "description" in cambios:
        equipo.description = cambios["description"]

    # Si llegan pokemon_ids, la plantilla se SUSTITUYE entera por la nueva.
    if cambios.get("pokemon_ids") is not None:
        entradas = _resolver_miembros(session, usuario, cambios["pokemon_ids"])
        # clear() saca a los miembros viejos de la lista y, gracias al cascade
        # «delete-orphan» del modelo Team, SQLAlchemy los borra de la base de datos.
        equipo.members.clear()
        session.flush()
        _guardar_miembros(session, equipo, entradas)

    session.add(equipo)
    session.commit()
    session.refresh(equipo)
    return _a_lectura(session, equipo)


@router.get("/{team_id}/export")
@limiter.limit("30/minute")  # llama a la PokeAPI por cada miembro → límite más estricto
async def exportar_equipo(
    request: Request,
    team_id: int,
    usuario: CurrentUser,
    session: SessionDep,
    poke: ServicioPokeAPI,
):
    """PDF del equipo: fichas de sus Pokémon y estadísticas combinadas."""
    equipo = _equipo_propio(session, team_id, usuario)
    miembros = sorted(equipo.members, key=lambda m: m.position)
    ids = [session.get(PokedexEntry, m.pokedex_entry_id).pokemon_id for m in miembros]

    # Pedimos todos los Pokémon (y sus sprites) a la vez en lugar de uno tras otro.
    infos = await asyncio.gather(*(poke.get_pokemon(i) for i in ids))
    sprites = await asyncio.gather(*(poke.fetch_image(i.get("sprite")) for i in infos))

    contenido = equipo_pdf(equipo.name, equipo.description, list(zip(infos, sprites)))
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="equipo-{equipo.id}.pdf"'
        },
    )
