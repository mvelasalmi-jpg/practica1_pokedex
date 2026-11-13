from fastapi import APIRouter, Depends, status
from sqlmodel import Session

# Importamos la función que abre y cierra la sesión de la base de datos
from app.database import get_session
# Importamos los contratos de entrada (Create/Update) y salida (Read) que revisamos en models.py
from app.models import PokedexEntryCreate, PokedexEntryRead, PokedexEntryUpdate
# Importamos las funciones de negocio que se han creado en services/pokedex_db.py
from app.services.pokedex_db import (
    create_pokedex_entry,
    get_all_entries,
    update_pokedex_entry,
)

# se crea el grupo de rutas
router = APIRouter(
    prefix="/my-pokedex",
    tags=["Mi Pokédex (BD Local)"]
)

#fucnion que crea o guarda un nuevo pokemon en la base de datos. status_code=201 indica "Created". response_model=PokedexEntryRead filtra la salida usando nuestro contrato de lectura
@router.post("", response_model=PokedexEntryRead, status_code=status.HTTP_201_CREATED, summary="Registrar un Pokémon en tu Pokédex")
def add_pokemon_to_pokedex(
    entry_in: PokedexEntryCreate,
    session: Session = Depends(get_session)  # Inyecta automáticamente la sesión de base de datos
):
    return create_pokedex_entry(session=session, entry_in=entry_in)

#funcion que consulta todos lo pokemons que tenemos en la pokedex
@router.get("", response_model=list[PokedexEntryRead], summary="Listar todos tus Pokémon guardados")
def list_my_pokedex(
    session: Session = Depends(get_session)
):
    return get_all_entries(session=session)

#funcion que modifica parcialmente (opcionl) un pokemos guardado
@router.patch("/{entry_id}", response_model=PokedexEntryRead, summary="Actualizar datos de un Pokémon guardado")
def patch_pokemon_entry(
    entry_id: int,
    entry_in: PokedexEntryUpdate,
    session: Session = Depends(get_session)
):
    return update_pokedex_entry(session=session, entry_id=entry_id, entry_in=entry_in)