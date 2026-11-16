"""Tests de los equipos de batalla."""

URL = "/api/v1/teams"


def llenar_pokedex(client, headers, ids):
    for i in ids:
        client.post("/api/v1/pokedex", json={"pokemon_id": i}, headers=headers)


def test_create_team(client, auth_headers):
    llenar_pokedex(client, auth_headers, [1, 4, 7, 25])
    r = client.post(
        URL,
        json={"name": "Elite", "description": "Principal", "pokemon_ids": [25, 1, 4]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    miembros = r.json()["members"]
    # La posición sigue el orden en que se enviaron los ids.
    assert [(m["position"], m["pokemon_name"]) for m in miembros] == [
        (1, "pikachu"),
        (2, "bulbasaur"),
        (3, "charmander"),
    ]


def test_team_with_more_than_six_is_rejected(client, auth_headers):
    r = client.post(
        URL,
        json={"name": "Enorme", "pokemon_ids": [1, 2, 3, 4, 5, 6, 7]},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_team_with_pokemon_not_in_pokedex(client, auth_headers):
    r = client.post(
        URL, json={"name": "Falso", "pokemon_ids": [25]}, headers=auth_headers
    )
    assert r.status_code == 422
    assert "[25]" in r.json()["detail"]


def test_team_with_duplicates_is_rejected(client, auth_headers):
    llenar_pokedex(client, auth_headers, [25])
    r = client.post(
        URL, json={"name": "Doble", "pokemon_ids": [25, 25]}, headers=auth_headers
    )
    assert r.status_code == 422


def test_list_teams_only_returns_mine(client, auth_headers, other_user_entry):
    llenar_pokedex(client, auth_headers, [25])
    client.post(URL, json={"name": "Mio", "pokemon_ids": [25]}, headers=auth_headers)
    r = client.get(URL, headers=auth_headers)
    assert [e["name"] for e in r.json()] == ["Mio"]


def test_update_team(client, auth_headers):
    llenar_pokedex(client, auth_headers, [1, 4, 25])
    equipo = client.post(
        URL, json={"name": "Viejo", "pokemon_ids": [1, 4]}, headers=auth_headers
    ).json()
    r = client.put(
        f"{URL}/{equipo['id']}",
        json={"name": "Nuevo", "pokemon_ids": [25]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Nuevo"
    assert [m["pokemon_id"] for m in r.json()["members"]] == [25]


def test_cannot_update_or_export_other_users_team(client, auth_headers, session):
    from tests.conftest import cabeceras, crear_usuario

    crear_usuario(session, "gary", "gary@example.com")
    otras = cabeceras(client, "gary")
    llenar_pokedex(client, otras, [25])
    equipo = client.post(
        URL, json={"name": "Suyo", "pokemon_ids": [25]}, headers=otras
    ).json()

    assert (
        client.put(
            f"{URL}/{equipo['id']}", json={"name": "Robado"}, headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.get(f"{URL}/{equipo['id']}/export", headers=auth_headers).status_code
        == 404
    )


def test_export_team_pdf(client, auth_headers):
    llenar_pokedex(client, auth_headers, [1, 4, 7, 25, 133, 143])
    equipo = client.post(
        URL,
        json={"name": "Elite", "pokemon_ids": [1, 4, 7, 25, 133, 143]},
        headers=auth_headers,
    ).json()
    r = client.get(f"{URL}/{equipo['id']}/export", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_deleting_pokedex_entry_removes_it_from_team(client, auth_headers):
    llenar_pokedex(client, auth_headers, [25, 4])
    client.post(URL, json={"name": "E", "pokemon_ids": [25, 4]}, headers=auth_headers)
    entrada_id = client.get(
        "/api/v1/pokedex?sort=pokemon_id", headers=auth_headers
    ).json()[1]["id"]
    client.delete(f"/api/v1/pokedex/{entrada_id}", headers=auth_headers)
    miembros = client.get(URL, headers=auth_headers).json()[0]["members"]
    assert [m["pokemon_id"] for m in miembros] == [4]
