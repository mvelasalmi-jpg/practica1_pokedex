"""Grupo 1 del enunciado: búsqueda de Pokémon (nuestra API actúa de proxy a la PokeAPI).

Los tres endpoints exigen estar autenticado (CurrentUser) y llaman a un servicio
externo, por eso llevan el límite más estricto: 30 peticiones por minuto.
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.dependencies import CurrentUser, ServicioPokeAPI
from app.limits import limiter
from app.services.pdf_service import ficha_pokemon_pdf

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


# OJO con el orden: /search tiene que declararse ANTES que /{id_or_name}.
# Si no, FastAPI intentaría interpretar la palabra "search" como un nombre de Pokémon.
@router.get("/search")
@limiter.limit("30/minute")
async def buscar_pokemon(
    request: Request,  # slowapi necesita ver la petición para saber quién es (su IP)
    usuario: CurrentUser,
    poke: ServicioPokeAPI,
    name: str | None = Query(default=None, min_length=1, max_length=50),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Busca Pokémon por trozo de nombre. Devuelve [{id, name, sprite, types}]."""
    return await poke.buscar(name, limit, offset)


@router.get("/{id_or_name}")
@limiter.limit("30/minute")
async def consultar_pokemon(
    request: Request, id_or_name: str, usuario: CurrentUser, poke: ServicioPokeAPI
):
    """Detalle completo: stats, habilidades, tipos y sprites."""
    return await poke.get_pokemon(id_or_name)


@router.get("/{id_or_name}/card")
@limiter.limit("30/minute")
async def ficha_pokemon(
    request: Request, id_or_name: str, usuario: CurrentUser, poke: ServicioPokeAPI
):
    """Descarga una ficha en PDF del Pokémon."""
    info = await poke.get_pokemon(id_or_name)

    # La descripción de la especie es un «extra»: si la PokeAPI falla al pedirla,
    # generamos la ficha igualmente sin ella.
    try:
        especie = await poke.get_species(info["id"])
    except HTTPException:
        especie = None

    sprite = await poke.fetch_image(info.get("sprite"))
    contenido = ficha_pokemon_pdf(info, especie, sprite)

    return Response(
        content=contenido,
        media_type="application/pdf",
        # attachment = el navegador lo descarga en vez de mostrarlo.
        headers={"Content-Disposition": f'attachment; filename="{info["name"]}.pdf"'},
    )
