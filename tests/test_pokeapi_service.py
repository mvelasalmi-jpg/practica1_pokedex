"""Tests del cliente de la PokeAPI.

Usamos httpx.MockTransport: en lugar de salir a internet, httpx le pregunta a una
función nuestra qué contestar. Así probamos 404, caídas y timeouts a voluntad.
"""

import httpx
import pytest
from fastapi import HTTPException

from app.services.pokeapi_service import PokeAPIService

BASE = "https://pokeapi.test/api/v2"

PIKACHU = {
    "id": 25,
    "name": "pikachu",
    "height": 4,
    "weight": 60,
    "sprites": {"front_default": "https://img.test/25.png", "front_shiny": None},
    "types": [{"type": {"name": "electric"}}],
    "abilities": [{"ability": {"name": "static"}}],
    "stats": [
        {"stat": {"name": "hp"}, "base_stat": 35},
        {"stat": {"name": "attack"}, "base_stat": 55},
        {"stat": {"name": "defense"}, "base_stat": 40},
        {"stat": {"name": "speed"}, "base_stat": 90},
        {"stat": {"name": "special-attack"}, "base_stat": 50},  # esta se descarta
    ],
}


def servicio(manejador) -> PokeAPIService:
    """Crea un servicio cuya «red» es la función `manejador`."""
    return PokeAPIService(BASE, transport=httpx.MockTransport(manejador))


@pytest.mark.asyncio
async def test_pokeapi_service_get_pokemon():
    """Obtiene un Pokémon y lo simplifica (sólo los campos útiles)."""
    peticiones = []

    def manejador(request):
        peticiones.append(str(request.url))
        return httpx.Response(200, json=PIKACHU)

    info = await servicio(manejador).get_pokemon("Pikachu")  # mayúscula: se normaliza
    assert peticiones == [f"{BASE}/pokemon/pikachu"]
    assert info["id"] == 25 and info["types"] == ["electric"]
    assert info["abilities"] == ["static"]
    assert info["stats"] == {"hp": 35, "attack": 55, "defense": 40, "speed": 90}


@pytest.mark.asyncio
async def test_pokeapi_service_handles_404():
    """Un Pokémon que no existe se convierte en HTTP 404 nuestro."""
    svc = servicio(lambda request: httpx.Response(404))
    with pytest.raises(HTTPException) as error:
        await svc.get_pokemon("missingno")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_pokeapi_service_handles_timeout():
    def manejador(request):
        raise httpx.ReadTimeout("muy lento", request=request)

    with pytest.raises(HTTPException) as error:
        await servicio(manejador).get_pokemon(25)
    assert error.value.status_code == 504


@pytest.mark.asyncio
async def test_pokeapi_service_handles_connection_error():
    def manejador(request):
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(HTTPException) as error:
        await servicio(manejador).get_pokemon(25)
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_pokeapi_service_handles_server_error():
    """Si la PokeAPI da un 500, nosotros respondemos 502 (el fallo es de un tercero)."""
    with pytest.raises(HTTPException) as error:
        await servicio(lambda request: httpx.Response(500)).get_pokemon(25)
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_pokeapi_service_handles_invalid_json():
    with pytest.raises(HTTPException) as error:
        await servicio(lambda r: httpx.Response(200, text="no soy json")).get_pokemon(
            25
        )
    assert error.value.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize("identificador", ["../etc/passwd", "con espacio", "", 0, -3])
async def test_pokeapi_service_rejects_invalid_identifiers(identificador):
    """Los identificadores raros ni siquiera llegan a la red."""

    def manejador(request):
        raise AssertionError("no debería haberse hecho ninguna petición")

    with pytest.raises(HTTPException) as error:
        await servicio(manejador).get_pokemon(identificador)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_pokeapi_service_uses_cache():
    """La segunda consulta del mismo Pokémon no vuelve a llamar a la PokeAPI."""
    llamadas = []

    def manejador(request):
        llamadas.append(1)
        return httpx.Response(200, json=PIKACHU)

    svc = servicio(manejador)
    await svc.get_pokemon(25)
    await svc.get_pokemon(25)
    assert len(llamadas) == 1


@pytest.mark.asyncio
async def test_pokeapi_service_search_filters_and_paginates():
    listado = {
        "count": 3,
        "results": [
            {"name": "pikachu", "url": f"{BASE}/pokemon/25/"},
            {"name": "pichu", "url": f"{BASE}/pokemon/172/"},
            {
                "name": "pikachu-cosplay",
                "url": f"{BASE}/pokemon/10080/",
            },  # forma > 1025
        ],
    }

    def manejador(request):
        if request.url.path.endswith("/pokemon"):
            return httpx.Response(200, json=listado)
        return httpx.Response(200, json=PIKACHU)

    svc = servicio(manejador)
    resultado = await svc.buscar("pi", limit=1, offset=0)
    assert resultado["total"] == 2  # la forma alternativa se descarta
    assert len(resultado["results"]) == 1
    assert set(resultado["results"][0]) == {"id", "name", "sprite", "types"}

    assert (await svc.buscar("zzz"))["results"] == []


@pytest.mark.asyncio
async def test_pokeapi_service_search_validates_params():
    with pytest.raises(HTTPException):
        await servicio(lambda r: httpx.Response(200, json={})).buscar(limit=0)
    with pytest.raises(HTTPException):
        await servicio(lambda r: httpx.Response(200, json={})).search_pokemon(offset=-1)


@pytest.mark.asyncio
async def test_pokeapi_service_by_type():
    cuerpo = {
        "pokemon": [{"pokemon": {"name": "charmander", "url": f"{BASE}/pokemon/4/"}}]
    }
    svc = servicio(lambda request: httpx.Response(200, json=cuerpo))
    assert await svc.get_pokemon_by_type("fire") == [{"id": 4, "name": "charmander"}]


@pytest.mark.asyncio
async def test_pokeapi_service_by_unknown_type():
    with pytest.raises(HTTPException) as error:
        await servicio(lambda request: httpx.Response(404)).get_pokemon_by_type("fuego")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_pokeapi_service_species_prefers_spanish():
    cuerpo = {
        "id": 25,
        "flavor_text_entries": [
            {
                "flavor_text": "When several of\nthese gather",
                "language": {"name": "en"},
            },
            {"flavor_text": "Almacena\felectricidad.", "language": {"name": "es"}},
        ],
        "genera": [{"genus": "Mouse Pokémon", "language": {"name": "en"}}],
    }
    svc = servicio(lambda request: httpx.Response(200, json=cuerpo))
    especie = await svc.get_species(25)
    assert especie["description"] == "Almacena electricidad."  # sin \f ni \n
    assert especie["genus"] == "Mouse Pokémon"  # no hay español: cae al inglés


@pytest.mark.asyncio
async def test_pokeapi_service_fetch_image():
    png = b"\x89PNG-falso"
    svc = servicio(
        lambda request: httpx.Response(
            200, content=png, headers={"content-type": "image/png"}
        )
    )
    assert await svc.fetch_image("https://img.test/25.png") == png
    # No se descargan URLs que no sean https, ni respuestas que no sean imágenes.
    assert await svc.fetch_image("http://img.test/25.png") is None
    assert await svc.fetch_image(None) is None
    html = servicio(
        lambda r: httpx.Response(
            200, text="<html>", headers={"content-type": "text/html"}
        )
    )
    assert await html.fetch_image("https://img.test/x") is None


@pytest.mark.asyncio
async def test_pokeapi_service_fetch_image_failure_returns_none():
    def manejador(request):
        raise httpx.ConnectError("sin red", request=request)

    assert await servicio(manejador).fetch_image("https://img.test/25.png") is None
