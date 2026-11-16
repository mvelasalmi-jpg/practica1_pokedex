"""Grupos 2 y 3 del enunciado: la Pokédex personal y sus estadísticas.

Regla de oro de todo este fichero: cada usuario sólo ve y toca LO SUYO.
Por eso todas las consultas filtran por owner_id == usuario.id.
"""

import csv
import io
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from app.dependencies import CurrentUser, ServicioPokeAPI, SessionDep
from app.limits import limiter
from app.models import (
    PokedexEntry,
    PokedexEntryCreate,
    PokedexEntryRead,
    PokedexEntryUpdate,
    TeamMember,
    ahora,
)
from app.services.pdf_service import pokedex_pdf

router = APIRouter(prefix="/pokedex", tags=["pokedex"])

# Límite de los endpoints autenticados: más permisivo que los públicos (ver README).
LIMITE = "100/minute"

CampoOrden = Literal["pokemon_id", "pokemon_name", "capture_date"]

# El texto que llega en ?sort= se traduce a columna aquí. Nunca se pega en el SQL.
ORDENABLE = {
    "pokemon_id": PokedexEntry.pokemon_id,
    "pokemon_name": PokedexEntry.pokemon_name,
    "capture_date": PokedexEntry.capture_date,
}


# ───────────────────── piezas reutilizables (también las usa la v2) ─────────────────────


def filtrar(usuario_id: int, captured: bool | None, favorite: bool | None):
    """Consulta base: entradas del usuario, con los filtros opcionales aplicados."""
    consulta = select(PokedexEntry).where(PokedexEntry.owner_id == usuario_id)
    if captured is not None:
        consulta = consulta.where(PokedexEntry.is_captured == captured)
    if favorite is not None:
        consulta = consulta.where(PokedexEntry.favorite == favorite)
    return consulta


def ordenar(consulta, sort: CampoOrden, order: Literal["asc", "desc"]):
    columna = ORDENABLE[sort]
    return consulta.order_by(columna.desc() if order == "desc" else columna.asc())


def calcular_racha(fechas: list[datetime], hoy: date | None = None) -> int:
    """Días SEGUIDOS (hasta hoy) en los que el usuario capturó al menos un Pokémon.

    Si hoy todavía no ha capturado nada pero ayer sí, la racha sigue viva: se
    cuenta desde ayer hacia atrás. Si ni hoy ni ayer, la racha es 0.
    """
    dias = {f.date() for f in fechas}  # set: cada día cuenta una sola vez
    dia = hoy or datetime.now(UTC).date()
    if dia not in dias:
        dia -= timedelta(days=1)
    racha = 0
    while dia in dias:
        racha += 1
        dia -= timedelta(days=1)
    return racha


# ───────────────────────────── CRUD ─────────────────────────────


@router.post("", response_model=PokedexEntryRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMITE)
async def anadir(
    request: Request,
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

    # Esta llamada también sirve para validar que el pokemon_id existe de verdad:
    # si no existe, la PokeAPI responde 404 y el servicio lo convierte en 404 nuestro.
    info = await poke.get_pokemon(datos.pokemon_id)
    entrada = PokedexEntry(
        **datos.model_dump(),
        owner_id=usuario.id,
        pokemon_name=info["name"],
        pokemon_sprite=info["sprite"],
        pokemon_types=",".join(info["types"]),  # lista → "grass,poison"
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
@limiter.limit(LIMITE)
def listar(
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
    consulta = ordenar(filtrar(usuario.id, captured, favorite), sort, order)
    return session.exec(consulta.offset(offset).limit(limit)).all()


def _contar(session, *condiciones) -> int:
    consulta = select(func.count()).select_from(PokedexEntry)
    for condicion in condiciones:
        consulta = consulta.where(condicion)
    return session.exec(consulta).one()


# /stats y /export van ANTES que /{entry_id}: si no, FastAPI intentaría leer
# "stats" o "export" como si fueran el número de una entrada.
@router.get("/stats")
@limiter.limit(LIMITE)
def estadisticas(request: Request, usuario: CurrentUser, session: SessionDep):
    mias = PokedexEntry.owner_id == usuario.id
    total = _contar(session, mias)
    capturados = _contar(session, mias, PokedexEntry.is_captured)
    favoritos = _contar(session, mias, PokedexEntry.favorite)
    porcentaje = round(100 * capturados / total, 1) if total else 0.0

    # Tipo más común: contamos cada tipo de todas las entradas del usuario.
    cuenta_tipos: Counter[str] = Counter()
    for tipos in session.exec(select(PokedexEntry.pokemon_types).where(mias)):
        if tipos:
            cuenta_tipos.update(tipos.split(","))
    # Orden: más repetido primero y, en caso de empate, por orden alfabético
    # (así el resultado es siempre el mismo y se puede probar).
    ordenados = sorted(cuenta_tipos.items(), key=lambda par: (-par[1], par[0]))
    tipo_comun = ordenados[0][0] if ordenados else None

    fechas = session.exec(
        select(PokedexEntry.capture_date).where(
            mias, PokedexEntry.is_captured, PokedexEntry.capture_date.is_not(None)
        )
    ).all()

    return {
        "total_pokemon": total,
        "captured": capturados,
        "favorites": favoritos,
        "completion_percentage": porcentaje,
        "most_common_type": tipo_comun,
        "capture_streak_days": calcular_racha(list(fechas)),
    }


def _seguro_csv(valor: object) -> str:
    """Evita la «inyección de fórmulas» en Excel.

    Si un apodo empieza por = + - @ , Excel lo ejecuta como fórmula al abrir el CSV.
    Poniendo una comilla delante, Excel lo trata como texto normal.
    """
    texto = "" if valor is None else str(valor)
    if texto[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + texto
    return texto


@router.get("/export")
@limiter.limit(LIMITE)
def exportar(
    request: Request,
    usuario: CurrentUser,
    session: SessionDep,
    # El parámetro se llama «format» en la URL (?format=pdf), pero en Python no
    # podemos llamar así a una variable sin pisar la función format(); de ahí el alias.
    formato: Literal["pdf", "csv"] = Query(default="csv", alias="format"),
    captured: bool | None = None,
    favorite: bool | None = None,
):
    """Descarga la Pokédex completa del usuario como CSV o PDF."""
    consulta = ordenar(filtrar(usuario.id, captured, favorite), "pokemon_id", "asc")
    entradas = session.exec(consulta).all()

    if formato == "pdf":
        filas = [
            {
                "pokemon_id": e.pokemon_id,
                "pokemon_name": e.pokemon_name,
                "nickname": e.nickname,
                "is_captured": e.is_captured,
                "favorite": e.favorite,
                "capture_date": e.capture_date.isoformat() if e.capture_date else None,
            }
            for e in entradas
        ]
        contenido: bytes | str = pokedex_pdf(filas, f"Pokédex de {usuario.username}")
        tipo, nombre = "application/pdf", "pokedex.pdf"
    else:
        salida = io.StringIO()
        escritor = csv.writer(salida)
        escritor.writerow(
            [
                "pokemon_id",
                "pokemon_name",
                "types",
                "nickname",
                "is_captured",
                "capture_date",
                "favorite",
                "notes",
            ]
        )
        for e in entradas:
            escritor.writerow(
                [
                    e.pokemon_id,
                    e.pokemon_name,
                    _seguro_csv(e.pokemon_types),
                    _seguro_csv(e.nickname),
                    e.is_captured,
                    e.capture_date.isoformat() if e.capture_date else "",
                    e.favorite,
                    _seguro_csv(e.notes),
                ]
            )
        # \ufeff (BOM) hace que Excel abra el CSV en UTF-8 y se vean bien las tildes.
        contenido = "\ufeff" + salida.getvalue()
        tipo, nombre = "text/csv; charset=utf-8", "pokedex.csv"

    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


def _entrada_propia(session, entry_id: int, usuario) -> PokedexEntry:
    entrada = session.get(PokedexEntry, entry_id)
    # 404 también si es de otro: no confirmamos que exista.
    if entrada is None or entrada.owner_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No está en tu Pokédex")
    return entrada


@router.get("/{entry_id}", response_model=PokedexEntryRead)
@limiter.limit(LIMITE)
def detalle(request: Request, entry_id: int, usuario: CurrentUser, session: SessionDep):
    return _entrada_propia(session, entry_id, usuario)


@router.patch("/{entry_id}", response_model=PokedexEntryRead)
@limiter.limit(LIMITE)
def actualizar(
    request: Request,
    entry_id: int,
    datos: PokedexEntryUpdate,
    usuario: CurrentUser,
    session: SessionDep,
):
    entrada = _entrada_propia(session, entry_id, usuario)
    # exclude_unset: sólo los campos que el cliente ha enviado de verdad.
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
@limiter.limit(LIMITE)
def borrar(request: Request, entry_id: int, usuario: CurrentUser, session: SessionDep):
    entrada = _entrada_propia(session, entry_id, usuario)
    # Si estaba en algún equipo, sale también de él: no dejamos miembros huérfanos.
    for miembro in session.exec(
        select(TeamMember).where(TeamMember.pokedex_entry_id == entrada.id)
    ):
        session.delete(miembro)
    session.delete(entrada)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
