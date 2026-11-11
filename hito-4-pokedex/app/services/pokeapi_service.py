"""Cliente de la PokeAPI: llama fuera, traduce los errores y simplifica la respuesta."""

import httpx
from fastapi import HTTPException, status


class PokeAPIService:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_pokemon(self, identificador: int | str) -> dict:
        url = f"{self.base_url}/pokemon/{str(identificador).lower()}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as cliente:
                respuesta = await cliente.get(url)
        except httpx.TimeoutException:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "PokeAPI no responde")
        except httpx.HTTPError:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PokeAPI no disponible")

        if respuesta.status_code == 404:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"No existe el Pokémon {identificador}"
            )
        if respuesta.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PokeAPI no disponible")
        return self._simplificar(respuesta.json())

    @staticmethod
    def _simplificar(bruto: dict) -> dict:
        # La frontera del sistema: lo ajeno entra aquí y sale con nuestro vocabulario.
        stats = {s["stat"]["name"]: s["base_stat"] for s in bruto.get("stats", [])}
        return {
            "id": bruto["id"],
            "name": bruto["name"],
            "sprite": bruto["sprites"]["front_default"],
            "types": [t["type"]["name"] for t in bruto.get("types", [])],
            "stats": {
                clave: stats.get(clave)
                for clave in ("hp", "attack", "defense", "speed")
            },
        }
