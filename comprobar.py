"""Comprueba, hito a hito, que tu Pokédex API hace lo que se ha visto en clase.

Con el servidor arrancado (uv run uvicorn app.main:app --reload), en otra terminal
y desde la carpeta de tu proyecto:

    python comprobar.py            # comprueba los cuatro hitos
    python comprobar.py 3          # sólo hasta el hito 3

Sólo usa la biblioteca estándar de Python: no hay nada que instalar.
Opciones: --url http://localhost:8000   --db pokedex.db
"""

import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USUARIO = "comprobador"
PASSWORD = "Comprueba2026"
EMAIL = "comprobador@ufv.es"

VERDE, ROJO, GRIS, FIN = "\033[32m", "\033[31m", "\033[90m", "\033[0m"
if sys.platform == "win32":
    import os

    os.system("")  # activa los colores ANSI en la consola de Windows

fallos = 0


def ok(texto):
    print(f"  {VERDE}✔{FIN} {texto}")


def mal(texto, pista):
    global fallos
    fallos += 1
    print(f"  {ROJO}✘ {texto}{FIN}\n    {GRIS}→ {pista}{FIN}")


def comprobar(condicion, texto, pista):
    (ok(texto) if condicion else mal(texto, pista))
    return condicion


def pedir(base, metodo, ruta, json_=None, form=None, token=None):
    """Devuelve (código, cuerpo ya decodificado o None)."""
    cabeceras = {}
    datos = None
    if json_ is not None:
        datos = json.dumps(json_).encode()
        cabeceras["Content-Type"] = "application/json"
    if form is not None:
        datos = urllib.parse.urlencode(form).encode()
        cabeceras["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(
        base + ruta, data=datos, headers=cabeceras, method=metodo
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as r:
            codigo, cuerpo = r.status, r.read()
    except urllib.error.HTTPError as e:
        codigo, cuerpo = e.code, e.read()
    try:
        return codigo, json.loads(cuerpo) if cuerpo else None
    except ValueError:
        return codigo, cuerpo.decode(errors="replace")


# ───────────────────────────── Hito 1 ─────────────────────────────


def hito_1(base, _db):
    print("\nHito 1 · entorno, configuración y /health  (diap. 9–20)")
    try:
        codigo, cuerpo = pedir(base, "GET", "/health")
    except urllib.error.URLError:
        mal(
            f"el servidor responde en {base}",
            "arráncalo en otra terminal: uv run uvicorn app.main:app --reload",
        )
        return False
    comprobar(
        codigo == 200 and cuerpo == {"status": "ok"},
        'GET /health → 200 {"status": "ok"}',
        f"ha respondido {codigo} {cuerpo}. Revisa el final de app/main.py",
    )
    codigo, cuerpo = pedir(base, "GET", "/openapi.json")
    comprobar(
        codigo == 200 and cuerpo.get("info", {}).get("title") == "Pokédex API",
        "/docs lleva el título «Pokédex API»",
        "el title va en FastAPI(title=..., version=..., description=...) (diap. 39)",
    )
    comprobar(
        Path(".env").exists(),
        "existe .env (copiado de .env.example)",
        "cp .env.example .env  y pon una SECRET_KEY propia (diap. 15–16)",
    )
    return True


# ───────────────────────────── Hito 2 ─────────────────────────────


def hito_2(_base, db):
    print("\nHito 2 · los modelos y sus tablas  (diap. 21–36)")
    ruta = Path(db)
    if not comprobar(
        ruta.exists(),
        f"existe la base de datos {ruta}",
        "se crea al arrancar el servidor (create_db_and_tables en el lifespan)",
    ):
        return False
    con = sqlite3.connect(ruta)
    tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for tabla in ("user", "pokedexentry", "team", "teammember"):
        comprobar(
            tabla in tablas,
            f"existe la tabla {tabla}",
            "¿está la clase con table=True en app/models.py? Si acabas de añadirla, "
            "borra pokedex.db y vuelve a arrancar: create_all no modifica tablas viejas",
        )
    if "pokedexentry" in tablas:
        sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE name='pokedexentry'"
        ).fetchone()[0]
        comprobar(
            "uq_pokedex_owner_pokemon" in sql,
            "pokedexentry tiene la restricción única (owner_id, pokemon_id)",
            "__table_args__ = (UniqueConstraint(...),) en PokedexEntry (diap. 29)",
        )
    if "user" in tablas:
        columnas = {f[1] for f in con.execute("PRAGMA table_info('user')")}
        comprobar(
            "hashed_password" in columnas and "password" not in columnas,
            "user guarda hashed_password y nunca password",
            "la contraseña en claro sólo existe en UserCreate (diap. 25–26)",
        )
    con.close()
    return True


# ───────────────────────────── Hito 3 ─────────────────────────────


def entrar(base):
    codigo, cuerpo = pedir(
        base, "POST", "/api/v1/auth/login", form={"username": USUARIO, "password": PASSWORD}
    )
    return cuerpo.get("access_token") if codigo == 200 else None


def hito_3(base, _db):
    print("\nHito 3 · autenticación  (diap. 37–54)")
    token = entrar(base)
    if token is None:
        codigo, cuerpo = pedir(
            base,
            "POST",
            "/api/v1/auth/register",
            json_={"username": USUARIO, "email": EMAIL, "password": PASSWORD},
        )
        if codigo == 429:
            mal("registro", "has superado los 5 registros por hora: espera o reinicia")
            return False
        comprobar(
            codigo == 201,
            "POST /auth/register → 201",
            f"ha respondido {codigo} {cuerpo}. ¿status_code=201 en el decorador? (diap. 50)",
        )
        comprobar(
            isinstance(cuerpo, dict) and "hashed_password" not in cuerpo,
            "la respuesta del registro no incluye hashed_password",
            "response_model=UserRead en el decorador (diap. 50)",
        )
        token = entrar(base)
    else:
        ok("el usuario de comprobación ya existía (registro hecho en otra pasada)")

    codigo, _ = pedir(
        base,
        "POST",
        "/api/v1/auth/register",
        json_={"username": USUARIO, "email": EMAIL, "password": PASSWORD},
    )
    comprobar(
        codigo in (409, 429),
        "registrar otra vez el mismo usuario → 409",
        f"ha respondido {codigo}. Busca antes con or_() y responde 409 (diap. 51)",
    )
    codigo, _ = pedir(
        base,
        "POST",
        "/api/v1/auth/register",
        json_={"username": "debil", "email": "debil@ufv.es", "password": "sinmayus1"},
    )
    comprobar(
        codigo in (422, 429),
        "una contraseña sin mayúscula → 422",
        "field_validator en UserCreate (diap. 26)",
    )
    if not comprobar(
        token is not None,
        "POST /auth/login devuelve un access_token",
        "el login recibe un formulario OAuth2, no JSON (diap. 52)",
    ):
        return False
    codigo, cuerpo = pedir(
        base, "POST", "/api/v1/auth/login", form={"username": USUARIO, "password": "Mala2026"}
    )
    comprobar(
        codigo == 401,
        "login con contraseña mala → 401",
        f"ha respondido {codigo} {cuerpo} (diap. 52–53)",
    )
    return token


# ───────────────────────────── Hito 4 ─────────────────────────────


def hito_4(base, _db, token):
    print("\nHito 4 · PokeAPI y CRUD del Pokédex  (diap. 55–70)")
    _, contrato = pedir(base, "GET", "/openapi.json")
    rutas = set(contrato.get("paths", {})) if isinstance(contrato, dict) else set()
    faltan = []
    if not any(r.startswith("/api/v1/pokemon/") for r in rutas):
        faltan.append("/api/v1/pokemon/{...}")
    faltan += [r for r in ("/api/v1/pokedex", "/api/v1/pokedex/stats") if r not in rutas]
    if not comprobar(
        not faltan,
        "las rutas /pokemon y /pokedex están registradas",
        f"faltan {', '.join(faltan)}: ¿has hecho include_router en app/main.py? "
        "¿Lleva cada router su prefix?",
    ):
        return
    codigo, _ = pedir(base, "GET", "/api/v1/pokedex")
    comprobar(
        codigo == 401,
        "GET /pokedex sin testigo → 401",
        "¿lleva el endpoint usuario: CurrentUser? (diap. 48)",
    )
    codigo, cuerpo = pedir(base, "GET", "/api/v1/pokemon/charizard", token=token)
    comprobar(
        codigo == 200
        and isinstance(cuerpo, dict)
        and {"id", "name", "sprite"} <= set(cuerpo),
        "GET /pokemon/charizard → ficha simplificada con id, name y sprite",
        f"ha respondido {codigo}. Revisa _simplificar en el servicio (diap. 55–57)",
    )
    codigo, cuerpo = pedir(base, "GET", "/api/v1/pokemon/pikachuu", token=token)
    comprobar(
        codigo == 404 and "pikachuu" in str(cuerpo),
        "GET /pokemon/pikachuu → 404 con nuestro mensaje",
        f"ha respondido {codigo}. Traduce el 404 de la PokeAPI (diap. 56)",
    )

    # Empezamos de cero: borramos lo que dejara una pasada anterior.
    codigo, previas = pedir(base, "GET", "/api/v1/pokedex?limit=100", token=token)
    for entrada in previas if codigo == 200 and isinstance(previas, list) else []:
        pedir(base, "DELETE", f"/api/v1/pokedex/{entrada['id']}", token=token)

    creadas = {}
    for pid, capturado in ((25, True), (1, False), (4, False)):
        codigo, cuerpo = pedir(
            base,
            "POST",
            "/api/v1/pokedex",
            json_={"pokemon_id": pid, "is_captured": capturado},
            token=token,
        )
        if codigo == 201:
            creadas[pid] = cuerpo
    if not comprobar(
        len(creadas) == 3,
        "POST /pokedex de Pikachu, Bulbasaur y Charmander → 201",
        f"último código {codigo}: {cuerpo} (diap. 59–61)",
    ):
        return
    comprobar(
        creadas[25]["pokemon_name"] == "pikachu" and creadas[25]["capture_date"],
        "la entrada trae el nombre de la PokeAPI y fecha de captura",
        "pokemon_name sale de la PokeAPI; capture_date=ahora() si is_captured (diap. 60)",
    )
    codigo, _ = pedir(base, "POST", "/api/v1/pokedex", json_={"pokemon_id": 25}, token=token)
    comprobar(
        codigo == 409, "añadir Pikachu otra vez → 409", f"ha respondido {codigo} (diap. 59)"
    )
    codigo, _ = pedir(
        base, "POST", "/api/v1/pokedex", json_={"pokemon_id": 2000}, token=token
    )
    comprobar(
        codigo == 422,
        "pokemon_id 2000 → 422",
        "Field(ge=1, le=1025) en PokedexEntryCreate (diap. 31)",
    )

    codigo, lista = pedir(
        base, "GET", "/api/v1/pokedex?sort=pokemon_name&order=desc", token=token
    )
    nombres = [e["pokemon_name"] for e in lista] if codigo == 200 else lista
    comprobar(
        nombres == ["pikachu", "charmander", "bulbasaur"],
        "GET /pokedex?sort=pokemon_name&order=desc ordena bien",
        f"ha devuelto {nombres} (diap. 62–64)",
    )
    codigo, lista = pedir(base, "GET", "/api/v1/pokedex?captured=true", token=token)
    comprobar(
        codigo == 200 and [e["pokemon_id"] for e in lista] == [25],
        "GET /pokedex?captured=true filtra",
        f"ha devuelto {codigo} {lista} (diap. 63)",
    )
    codigo, _ = pedir(base, "GET", "/api/v1/pokedex?limit=500", token=token)
    comprobar(codigo == 422, "limit=500 → 422", "Query(ge=1, le=100) (diap. 62)")

    bulbasaur = creadas[1]["id"]
    codigo, cuerpo = pedir(
        base,
        "PATCH",
        f"/api/v1/pokedex/{bulbasaur}",
        json_={"favorite": True},
        token=token,
    )
    comprobar(
        codigo == 200 and cuerpo["favorite"] is True and cuerpo["is_captured"] is False,
        "PATCH sólo cambia lo que llega",
        "model_dump(exclude_unset=True) (diap. 66–67)",
    )

    codigo, cuerpo = pedir(base, "GET", "/api/v1/pokedex/stats", token=token)
    comprobar(
        cuerpo
        == {
            "total_pokemon": 3,
            "captured": 1,
            "favorites": 1,
            "completion_percentage": 33.3,
        },
        "GET /pokedex/stats → 3 · 1 · 1 · 33.3",
        f"ha devuelto {codigo} {cuerpo}. ¿/stats está declarada antes que "
        "/{entry_id}? (diap. 69–70)",
    )

    charmander = creadas[4]["id"]
    codigo, _ = pedir(base, "DELETE", f"/api/v1/pokedex/{charmander}", token=token)
    comprobar(codigo == 204, "DELETE → 204", f"ha respondido {codigo} (diap. 68)")
    codigo, _ = pedir(base, "DELETE", f"/api/v1/pokedex/{charmander}", token=token)
    comprobar(
        codigo == 404,
        "borrar dos veces → 404 la segunda",
        f"ha respondido {codigo} (diap. 65, 68)",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("hasta", nargs="?", type=int, default=4, choices=[1, 2, 3, 4])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--db", default="pokedex.db")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    if hito_1(base, args.db) and args.hasta >= 2:
        hito_2(base, args.db)
        if args.hasta >= 3:
            token = hito_3(base, args.db)
            if token and args.hasta >= 4:
                hito_4(base, args.db, token)

    print()
    if fallos:
        print(f"{ROJO}{fallos} comprobación(es) fallida(s).{FIN} Lee la pista y la diapositiva.")
        sys.exit(1)
    print(f"{VERDE}Todo en verde hasta el hito {args.hasta}.{FIN}")


if __name__ == "__main__":
    main()
