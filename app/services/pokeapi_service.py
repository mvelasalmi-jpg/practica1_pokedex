"""Cliente de la PokeAPI (Parte 1 del enunciado).

Este módulo es la ÚNICA puerta por la que nuestra API habla con el exterior.
Si la PokeAPI cambia, o se cae, o responde raro, el problema se queda aquí y
el resto de la aplicación sólo ve nuestros propios diccionarios y errores.

Qué hace por cada petición externa:
  1. Valida lo que le piden (para no mandar basura a un servidor ajeno).
  2. Llama con httpx de forma asíncrona y con tiempo máximo (timeout).
  3. Anota en el log la URL, el código de respuesta y lo que ha tardado.
  4. Traduce los fallos de red a errores HTTP nuestros (404, 502, 504).
  5. Devuelve sólo los campos que nos interesan (la «frontera» del sistema).
  6. Guarda el resultado en una caché en memoria (bonus del enunciado).
"""

import asyncio
import logging
import re
import time
from typing import ClassVar

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("pokedex_api.pokeapi")

# Un identificador válido son letras minúsculas, números y guiones: "25", "pikachu",
# "mr-mime". Rechazar el resto evita meter "../", espacios o símbolos en la URL.
PATRON_IDENTIFICADOR = re.compile(r"^[a-z0-9-]{1,50}$")

# Los modelos del proyecto aceptan pokemon_id entre 1 y 1025 (los Pokémon «base»).
# La PokeAPI también lista formas alternativas con ids como 10001; las ignoramos.
ID_MAXIMO = 1025

# Las cuatro estadísticas que pide el enunciado.
STATS_BASICAS = ("hp", "attack", "defense", "speed")

# Cuántas peticiones simultáneas a la PokeAPI hacemos como máximo en una búsqueda.
# Así una búsqueda de 50 resultados no lanza 50 llamadas a la vez.
SIMULTANEAS = 10


def _id_desde_url(url: str) -> int:
    """La PokeAPI da URLs como '.../pokemon/25/'; de ahí sacamos el 25."""
    return int(url.rstrip("/").rsplit("/", 1)[-1])


def _limpiar_texto(texto: str) -> str:
    """Los textos de la PokeAPI traen saltos de línea y '\\f' dentro de las frases."""
    return " ".join(texto.replace("\f", " ").replace("\n", " ").split())


class PokeAPIService:
    # Caché compartida por TODAS las instancias. Hace falta que sea de clase porque
    # FastAPI crea una instancia nueva del servicio en cada petición (ver
    # dependencies.py), y una caché de instancia moriría con ella.
    _cache: ClassVar[dict[str, object]] = {}
    _CACHE_MAX = 2000  # tope de entradas para no crecer sin límite

    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # transport sólo se usa en los tests: permite sustituir la red real por una
        # falsa (httpx.MockTransport) sin tocar el resto del código.
        self.transport = transport

    # ───────────────────────── utilidades internas ─────────────────────────

    @classmethod
    def vaciar_cache(cls) -> None:
        cls._cache.clear()

    def _guardar_en_cache(self, clave: str, valor: object) -> None:
        if len(self._cache) >= self._CACHE_MAX:
            self._cache.clear()  # estrategia simple: al llenarse, se empieza de cero
        self._cache[clave] = valor

    @staticmethod
    def _validar_identificador(identificador: int | str) -> str:
        """Devuelve el identificador normalizado o lanza 422 si no es válido."""
        if isinstance(identificador, int):
            if identificador < 1:
                raise HTTPException(422, "El id debe ser mayor que 0")
            return str(identificador)
        limpio = str(identificador).strip().lower()
        if not PATRON_IDENTIFICADOR.match(limpio):
            raise HTTPException(422, "Identificador no válido")
        return limpio

    async def _get(
        self,
        ruta: str,
        params: dict | None = None,
        no_encontrado: str = "Recurso no encontrado en la PokeAPI",
    ) -> dict:
        """Hace UN GET a la PokeAPI y traduce cualquier fallo a un HTTPException."""
        url = f"{self.base_url}{ruta}"
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as cliente:
                respuesta = await cliente.get(url, params=params)
        except httpx.TimeoutException:
            logger.error("PokeAPI GET %s → timeout", url)
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "PokeAPI no responde")
        except httpx.HTTPError as error:
            # Cualquier otro fallo de red: DNS, conexión rechazada, etc.
            logger.error("PokeAPI GET %s → error de red (%s)", url, error)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PokeAPI no disponible")

        ms = (time.perf_counter() - inicio) * 1000
        logger.info("PokeAPI GET %s → %s (%.0f ms)", url, respuesta.status_code, ms)

        if respuesta.status_code == 404:
            raise HTTPException(status.HTTP_404_NOT_FOUND, no_encontrado)
        if respuesta.is_error:  # 500, 503... → el fallo es de ellos, no del cliente
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PokeAPI no disponible")
        try:
            return respuesta.json()
        except ValueError:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "Respuesta no válida de la PokeAPI"
            )

    # ───────────────────────── Pokémon concreto ─────────────────────────

    async def get_pokemon(self, identificador: int | str) -> dict:
        """Datos de un Pokémon por id o nombre, ya simplificados."""
        ident = self._validar_identificador(identificador)
        clave = f"pokemon:{ident}"
        if clave in self._cache:
            logger.info("PokeAPI caché · %s", clave)
            return self._cache[clave]  # type: ignore[return-value]

        bruto = await self._get(
            f"/pokemon/{ident}", no_encontrado=f"No existe el Pokémon {identificador}"
        )
        resultado = self._simplificar(bruto)
        self._guardar_en_cache(clave, resultado)
        return resultado

    @staticmethod
    def _simplificar(bruto: dict) -> dict:
        """La PokeAPI devuelve cientos de campos; aquí nos quedamos con los útiles.

        Entra el vocabulario de la PokeAPI y sale el nuestro (la «frontera»).
        """
        stats = {s["stat"]["name"]: s["base_stat"] for s in bruto.get("stats", [])}
        sprites = bruto.get("sprites") or {}
        return {
            "id": bruto["id"],
            "name": bruto["name"],
            "sprite": sprites.get("front_default"),
            "sprites": {
                "front_default": sprites.get("front_default"),
                "front_shiny": sprites.get("front_shiny"),
            },
            "types": [t["type"]["name"] for t in bruto.get("types", [])],
            "abilities": [a["ability"]["name"] for a in bruto.get("abilities", [])],
            "height": bruto.get("height"),
            "weight": bruto.get("weight"),
            "stats": {clave: stats.get(clave) for clave in STATS_BASICAS},
        }

    # ───────────────────────── listados y búsqueda ─────────────────────────

    async def search_pokemon(self, limit: int = 20, offset: int = 0) -> dict:
        """Lista Pokémon paginada, tal como la ofrece la PokeAPI.

        Devuelve {"count": total, "results": [{"id": 1, "name": "bulbasaur"}, ...]}
        """
        if limit < 1 or limit > 100000 or offset < 0:
            raise HTTPException(422, "limit u offset no válidos")
        bruto = await self._get("/pokemon", params={"limit": limit, "offset": offset})
        resultados = []
        for item in bruto.get("results", []):
            ident = _id_desde_url(item["url"])
            if ident <= ID_MAXIMO:  # descartamos las formas alternativas (id > 1025)
                resultados.append({"id": ident, "name": item["name"]})
        return {"count": bruto.get("count", len(resultados)), "results": resultados}

    async def _todos_los_nombres(self) -> list[dict]:
        """Lista completa de (id, nombre). Pesa poco y se pide una sola vez (caché)."""
        clave = "todos-los-nombres"
        if clave not in self._cache:
            pagina = await self.search_pokemon(limit=100000, offset=0)
            self._guardar_en_cache(clave, pagina["results"])
        return self._cache[clave]  # type: ignore[return-value]

    async def buscar(
        self, nombre: str | None = None, limit: int = 20, offset: int = 0
    ) -> dict:
        """Búsqueda por trozo de nombre, con paginación y resumen de cada resultado.

        La PokeAPI NO permite buscar por nombre parcial, así que: 1) bajamos la
        lista de nombres (una vez), 2) filtramos aquí, 3) pedimos el detalle sólo
        de la página que toca, para sacar sprite y tipos.
        """
        if limit < 1 or limit > 100 or offset < 0:
            raise HTTPException(422, "limit u offset no válidos")
        todos = await self._todos_los_nombres()
        if nombre:
            trozo = nombre.strip().lower()
            todos = [p for p in todos if trozo in p["name"]]

        pagina = todos[offset : offset + limit]
        semaforo = asyncio.Semaphore(SIMULTANEAS)

        async def detalle(pokemon: dict) -> dict:
            async with semaforo:  # sólo SIMULTANEAS peticiones a la vez
                info = await self.get_pokemon(pokemon["id"])
            return {
                "id": info["id"],
                "name": info["name"],
                "sprite": info["sprite"],
                "types": info["types"],
            }

        # gather lanza todas las corrutinas «a la vez» y espera a que acaben.
        resultados = await asyncio.gather(*(detalle(p) for p in pagina))
        return {
            "total": len(todos),
            "limit": limit,
            "offset": offset,
            "results": list(resultados),
        }

    async def get_pokemon_by_type(self, type_name: str) -> list[dict]:
        """Todos los Pokémon de un tipo ('fire', 'water'...), como [{id, name}]."""
        tipo = self._validar_identificador(type_name)
        bruto = await self._get(
            f"/type/{tipo}", no_encontrado=f"No existe el tipo {type_name}"
        )
        resultado = []
        for item in bruto.get("pokemon", []):
            ident = _id_desde_url(item["pokemon"]["url"])
            if ident <= ID_MAXIMO:
                resultado.append({"id": ident, "name": item["pokemon"]["name"]})
        return resultado

    async def get_species(self, identificador: int | str) -> dict:
        """Información de especie: descripción (en español si existe) y categoría."""
        ident = self._validar_identificador(identificador)
        clave = f"especie:{ident}"
        if clave in self._cache:
            return self._cache[clave]  # type: ignore[return-value]

        bruto = await self._get(
            f"/pokemon-species/{ident}", no_encontrado=f"No existe la especie {ident}"
        )

        def en_idioma(items: list[dict], campo: str) -> str | None:
            # Preferimos español; si no hay, inglés; si no, nada.
            for idioma in ("es", "en"):
                for item in items:
                    if item.get("language", {}).get("name") == idioma:
                        return _limpiar_texto(item[campo])
            return None

        resultado = {
            "id": bruto.get("id"),
            "description": en_idioma(
                bruto.get("flavor_text_entries", []), "flavor_text"
            ),
            "genus": en_idioma(bruto.get("genera", []), "genus"),
        }
        self._guardar_en_cache(clave, resultado)
        return resultado

    # ───────────────────────── imágenes ─────────────────────────

    async def fetch_image(self, url: str | None) -> bytes | None:
        """Descarga una imagen (el sprite) para meterla en un PDF.

        Si falla, devuelve None: un sprite que no carga no debe impedir que se
        genere la ficha. Sólo aceptamos https para no seguir URLs raras.
        """
        if not url or not url.startswith("https://"):
            return None
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as cliente:
                respuesta = await cliente.get(url)
        except httpx.HTTPError as error:
            logger.warning("Sprite GET %s → fallo (%s)", url, error)
            return None
        ms = (time.perf_counter() - inicio) * 1000
        logger.info("Sprite GET %s → %s (%.0f ms)", url, respuesta.status_code, ms)
        if respuesta.is_error:
            return None
        if not respuesta.headers.get("content-type", "").startswith("image/"):
            return None
        return respuesta.content
