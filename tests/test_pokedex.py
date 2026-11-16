"""Tests de la Pokédex: CRUD, filtros, estadísticas, exportación y versión 2."""

from datetime import UTC, date, datetime

from app.routers.pokedex import calcular_racha

URL = "/api/v1/pokedex"


def anadir(client, headers, pokemon_id, **extra):
    return client.post(URL, json={"pokemon_id": pokemon_id, **extra}, headers=headers)


def test_add_pokemon_to_pokedex(client, auth_headers):
    """Añadir un Pokémon completa nombre, sprite y tipos desde la PokeAPI."""
    r = anadir(client, auth_headers, 25, nickname="Sparky", is_captured=True)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["pokemon_name"] == "pikachu"
    assert cuerpo["pokemon_types"] == "electric"
    assert cuerpo["capture_date"] is not None  # al capturar se pone la fecha sola


def test_add_duplicate_pokemon(client, auth_headers):
    """No se permiten duplicados del mismo usuario."""
    assert anadir(client, auth_headers, 25).status_code == 201
    assert anadir(client, auth_headers, 25).status_code == 409


def test_add_unknown_pokemon_returns_404(client, auth_headers):
    """Un id que no existe en la PokeAPI da 404."""
    assert anadir(client, auth_headers, 999).status_code == 404


def test_add_invalid_id_returns_422(client, auth_headers):
    assert anadir(client, auth_headers, 2000).status_code == 422


def test_get_pokedex_with_filters(client, auth_headers):
    """Filtros, orden y paginación funcionan."""
    anadir(client, auth_headers, 25, is_captured=True)
    anadir(client, auth_headers, 4, favorite=True)
    anadir(client, auth_headers, 1)

    capturados = client.get(f"{URL}?captured=true", headers=auth_headers).json()
    assert [e["pokemon_id"] for e in capturados] == [25]

    favoritos = client.get(f"{URL}?favorite=true", headers=auth_headers).json()
    assert [e["pokemon_id"] for e in favoritos] == [4]

    por_nombre = client.get(
        f"{URL}?sort=pokemon_name&order=desc", headers=auth_headers
    ).json()
    assert [e["pokemon_name"] for e in por_nombre] == [
        "pikachu",
        "charmander",
        "bulbasaur",
    ]

    pagina = client.get(f"{URL}?limit=1&offset=1", headers=auth_headers).json()
    assert len(pagina) == 1


def test_limit_above_maximum_returns_422(client, auth_headers):
    assert client.get(f"{URL}?limit=500", headers=auth_headers).status_code == 422


def test_update_pokedex_entry(client, auth_headers):
    """PATCH sólo cambia lo que se envía; capturar pone fecha y soltar la quita."""
    entrada = anadir(client, auth_headers, 25).json()
    r = client.patch(
        f"{URL}/{entrada['id']}",
        json={"is_captured": True, "nickname": "Rayo"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["nickname"] == "Rayo"
    assert r.json()["capture_date"] is not None

    r = client.patch(
        f"{URL}/{entrada['id']}", json={"is_captured": False}, headers=auth_headers
    )
    assert r.json()["capture_date"] is None
    assert r.json()["nickname"] == "Rayo"  # lo que no se envió no se toca


def test_get_entry_detail(client, auth_headers):
    entrada = anadir(client, auth_headers, 25).json()
    r = client.get(f"{URL}/{entrada['id']}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["id"] == entrada["id"]


def test_delete_pokedex_entry(client, auth_headers):
    """Borrar devuelve 204 y la segunda vez 404."""
    entrada = anadir(client, auth_headers, 25).json()
    assert (
        client.delete(f"{URL}/{entrada['id']}", headers=auth_headers).status_code == 204
    )
    assert (
        client.delete(f"{URL}/{entrada['id']}", headers=auth_headers).status_code == 404
    )


def test_cannot_modify_other_user_pokedex(client, auth_headers, other_user_entry):
    """No se puede ver, modificar ni borrar la Pokédex de otro usuario."""
    ruta = f"{URL}/{other_user_entry.id}"
    assert client.get(ruta, headers=auth_headers).status_code == 404
    assert (
        client.patch(ruta, json={"favorite": True}, headers=auth_headers).status_code
        == 404
    )
    assert client.delete(ruta, headers=auth_headers).status_code == 404
    # y tampoco aparece en nuestro listado
    assert client.get(URL, headers=auth_headers).json() == []


def test_stats(client, auth_headers):
    """Estadísticas: totales, porcentaje, tipo más común y racha."""
    anadir(client, auth_headers, 25, is_captured=True, favorite=True)
    anadir(client, auth_headers, 133)
    anadir(client, auth_headers, 143)
    r = client.get(f"{URL}/stats", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {
        "total_pokemon": 3,
        "captured": 1,
        "favorites": 1,
        "completion_percentage": 33.3,
        "most_common_type": "normal",  # eevee y snorlax son de tipo normal
        "capture_streak_days": 1,  # capturó uno hoy
    }


def test_stats_empty_pokedex(client, auth_headers):
    r = client.get(f"{URL}/stats", headers=auth_headers).json()
    assert r["total_pokemon"] == 0
    assert r["most_common_type"] is None
    assert r["capture_streak_days"] == 0


def test_streak_calculation():
    """La racha cuenta días seguidos hasta hoy (o hasta ayer)."""
    hoy = date(2026, 11, 15)

    def dia(d):
        return datetime(2026, 11, d, 12, tzinfo=UTC)

    assert calcular_racha([], hoy) == 0
    assert calcular_racha([dia(15), dia(14), dia(13)], hoy) == 3
    assert (
        calcular_racha([dia(14), dia(13)], hoy) == 2
    )  # hoy aún sin captura: sigue viva
    assert calcular_racha([dia(15), dia(13)], hoy) == 1  # hueco el día 14: se corta
    assert calcular_racha([dia(10)], hoy) == 0  # demasiado antigua


def test_export_csv(client, auth_headers):
    anadir(client, auth_headers, 25, is_captured=True, nickname="Rayo")
    anadir(client, auth_headers, 4)
    r = client.get(f"{URL}/export?format=csv", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "pikachu" in r.text and "charmander" in r.text


def test_export_csv_filters_captured(client, auth_headers):
    anadir(client, auth_headers, 25, is_captured=True)
    anadir(client, auth_headers, 4)
    r = client.get(f"{URL}/export?format=csv&captured=true", headers=auth_headers)
    assert "pikachu" in r.text and "charmander" not in r.text


def test_export_csv_blocks_formula_injection(client, auth_headers):
    """Un apodo que empieza por '=' no debe poder ejecutarse como fórmula en Excel."""
    anadir(client, auth_headers, 25, nickname="=1+1")
    r = client.get(f"{URL}/export?format=csv", headers=auth_headers)
    assert "'=1+1" in r.text


def test_export_pdf(client, auth_headers):
    anadir(client, auth_headers, 25, is_captured=True)
    r = client.get(f"{URL}/export?format=pdf", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_export_invalid_format(client, auth_headers):
    assert (
        client.get(f"{URL}/export?format=xml", headers=auth_headers).status_code == 422
    )


def test_v2_returns_envelope_with_types(client, auth_headers):
    """La v2 devuelve un objeto con total/paginación y `types` como lista."""
    anadir(client, auth_headers, 1)
    anadir(client, auth_headers, 25)
    r = client.get("/api/v2/pokedex?limit=1", headers=auth_headers)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] == 2 and cuerpo["limit"] == 1
    assert cuerpo["items"][0]["types"] == ["grass", "poison"]
    # la v1 sigue devolviendo una lista a secas: las dos versiones conviven
    assert isinstance(client.get(URL, headers=auth_headers).json(), list)
