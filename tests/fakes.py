"""PokeAPI «de mentira» para los tests.

Los tests NO deben llamar a internet: serían lentos, dependerían de que la PokeAPI
esté levantada y fallarían sin conexión (como en GitHub Actions si hay un corte).
En su lugar, sustituimos el servicio real por este, que responde con datos fijos.
"""

import base64

from fastapi import HTTPException

# Un PNG válido de 1x1 píxel, para probar que el sprite se incrusta en los PDF.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

# id → (nombre, tipos)
POKEMON = {
    1: ("bulbasaur", ["grass", "poison"]),
    4: ("charmander", ["fire"]),
    7: ("squirtle", ["water"]),
    25: ("pikachu", ["electric"]),
    133: ("eevee", ["normal"]),
    143: ("snorlax", ["normal"]),
}
POR_NOMBRE = {nombre: id_ for id_, (nombre, _) in POKEMON.items()}


class FakePokeAPI:
    """Misma «forma» que PokeAPIService, pero sin red."""

    async def get_pokemon(self, identificador):
        id_ = POR_NOMBRE.get(str(identificador).lower())
        if id_ is None and str(identificador).isdigit():
            id_ = int(identificador)
        if id_ not in POKEMON:
            raise HTTPException(404, f"No existe el Pokémon {identificador}")
        nombre, tipos = POKEMON[id_]
        return {
            "id": id_,
            "name": nombre,
            "sprite": f"https://example.test/sprites/{id_}.png",
            "sprites": {
                "front_default": f"https://example.test/sprites/{id_}.png",
                "front_shiny": None,
            },
            "types": tipos,
            "abilities": ["static"],
            "height": 4,
            "weight": 60,
            "stats": {"hp": 35, "attack": 55, "defense": 40, "speed": 90},
        }

    async def buscar(self, nombre=None, limit=20, offset=0):
        todos = [i for i, (n, _) in POKEMON.items() if not nombre or nombre in n]
        pagina = todos[offset : offset + limit]
        return {
            "total": len(todos),
            "limit": limit,
            "offset": offset,
            "results": [
                {"id": i, "name": POKEMON[i][0], "sprite": None, "types": POKEMON[i][1]}
                for i in pagina
            ],
        }

    async def get_species(self, identificador):
        return {
            "id": identificador,
            "description": "Un Pokémon de prueba.",
            "genus": "Ratón",
        }

    async def fetch_image(self, url):
        return PNG_1X1
