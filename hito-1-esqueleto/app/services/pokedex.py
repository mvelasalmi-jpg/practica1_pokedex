#importamos librerias 
import requests #libreria para hcer peticiones HTTP a la API
from typing import Dict, Any, Optional  #definie los tipos de datos con los que trabajan las funciones

#direccion de la API donde se piden los datos de los pokemon
POKEAPI_URL = "https://pokeapi.co/api/v2/pokemon"

#lista blanca - se definen los unicos parametros permitidos para la busqueda
ALLOWED_PARAMS = {"limit", "cursor", "name"}

#función que coge la lista de pokemon desde la API y aplica paginación por cursor y filtrado. 
def get_pokemon_list(limit: int = 10, cursor: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:

    #se crea el diccionario de condiciones de busqueda que se envia a la API
    params = {"limit": limit}
    
    #si el usuario no nos dice un cursor, se lo añadimos a las condiciones de la petición
    if cursor:
        params["offset"] = cursor

    #se hace la llamadda real a internet (se hace un GET de la API)
    response = requests.get(POKEAPI_URL, params=params)
    
    #si la API falla o no nos responde con código 200, se envia un mensaje de error
    if response.status_code != 200:
        return {"error": "Error al conectar con la PokéAPI", "status_code": response.status_code}
    
    #se convierte la respuesta de la API en un diccionario JSON
    data = response.json()
    
    # si existe respuesta, se extrae el cursor de lo que nos devuelve la API 
    next_cursor = None
    if data.get("next"):
        #se usan esta funciones para leer la URL y sacar el numero offset
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(data["next"])
        next_cursor = parse_qs(parsed_url.query).get("offset", [None])[0]

    #se devuelve la respuesta estructurada con los pokemos y la informacion de la pagina
    return {
        "items": data.get("results", []),
        "next_cursor": next_cursor,
        "total": data.get("count", 0)
    }