"""Tests de los endpoints de búsqueda de Pokémon (con la PokeAPI falsa)."""

URL = "/api/v1/pokemon"


def test_search_returns_simplified_list(client, auth_headers):
    r = client.get(f"{URL}/search?name=char", headers=auth_headers)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] == 1
    assert set(cuerpo["results"][0]) == {"id", "name", "sprite", "types"}


def test_search_requires_auth(client):
    assert client.get(f"{URL}/search").status_code == 401


def test_search_limit_validation(client, auth_headers):
    assert client.get(f"{URL}/search?limit=0", headers=auth_headers).status_code == 422


def test_pokemon_detail(client, auth_headers):
    r = client.get(f"{URL}/pikachu", headers=auth_headers)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["id"] == 25
    assert {"stats", "abilities", "types", "sprites"} <= set(cuerpo)


def test_pokemon_not_found(client, auth_headers):
    assert client.get(f"{URL}/missingno", headers=auth_headers).status_code == 404


def test_pokemon_card_is_pdf(client, auth_headers):
    r = client.get(f"{URL}/25/card", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "pikachu.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")


def test_pokemon_card_requires_auth(client):
    assert client.get(f"{URL}/25/card").status_code == 401
