"""Proxy de consulta a la PokeAPI."""

from fastapi import APIRouter

from app.dependencies import CurrentUser, ServicioPokeAPI

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


@router.get("/{id_or_name}")
async def consultar_pokemon(
    id_or_name: str, usuario: CurrentUser, poke: ServicioPokeAPI
):
    return await poke.get_pokemon(id_or_name)
