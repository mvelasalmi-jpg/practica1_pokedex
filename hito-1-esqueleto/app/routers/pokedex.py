#importamos la API para crear las rutas y Query para verificar lo que manda el usuario
from fastapi import APIRouter, Query
from typing import Optional
from app.services.pokedex import get_pokemon_list

#se crea el enrutador para especificar la URL y la etiqueta 
router = APIRouter(
    prefix="/pokedex",
    tags=["Pokédex"]
)

#definimos el GET para consultar y leer datos 
@router.get("", summary="Listar Pokémon paginados por cursor")

#funcion que recibe las peticiones del usuario, llama a la pokedex con las limitaciones y devuelve el resultado en JSON
def list_pokemon(
    #limita la cantidad de datos que nos traemos de la API (10 por defecto, minimo 1 y maximo 50)
    limit: int = Query(10, ge=1, le=50, description="Número de elementos a devolver"),
    #el cursor indica desde que punto de la lista hay que comenzar a leer
    cursor: Optional[str] = Query(None, description="Cursor para la siguiente página (offset)")
):

#es lo que llama directamenete a la pokedes con las especificaciones de antes y devuelve el resultado
    result = get_pokemon_list(limit=limit, cursor=cursor)
    return result