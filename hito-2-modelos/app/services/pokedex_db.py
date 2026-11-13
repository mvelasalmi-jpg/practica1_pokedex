#logica para guardar, leer y actualizar pokemos en la base de datos 

from datetime import UTC, datetime
from fastapi import HTTPException
from sqlmodel import Session, select
from app.models import PokedexEntry, PokedexEntryCreate, PokedexEntryUpdate, User

#funcion que nos asegura que existe al menos un usuario entrenador de prueba 
def get_or_create_default_user(session: Session) -> User:
    user = session.exec(select(User)).first()
    if not user:
        user = User(
            username="ash_ketchum",
            email="ash@pokedex.com",
            hashed_password="hash_de_prueba_hito2"
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


#guardar un pokemon en la pokedex
def create_pokedex_entry(session: Session, entry_in: PokedexEntryCreate) -> PokedexEntry:
    user = get_or_create_default_user(session)

    # se comprueba si este usuario ya tiene registrado ese Pokémon para evitar duplicados
    existing = session.exec(
        select(PokedexEntry).where(
            PokedexEntry.owner_id == user.id,
            PokedexEntry.pokemon_id == entry_in.pokemon_id
        )
    ).first()

    if existing:
        # si existe manda este error estandarizado RFC 9457 (409 Conflict)
        raise HTTPException(
            status_code=409,
            detail={
                "type": "about:blank",
                "title": "Pokémon ya registrado",
                "status": 409,
                "detail": f"El Pokémon con ID {entry_in.pokemon_id} ya está en tu Pokédex."
            }
        )

    # Creamos el registro real para la tabla PokedexEntry
    db_entry = PokedexEntry(
        owner_id=user.id,
        pokemon_id=entry_in.pokemon_id,
        pokemon_name=f"pokemon-{entry_in.pokemon_id}",
        nickname=entry_in.nickname,
        notes=entry_in.notes,
        is_captured=entry_in.is_captured,
        favorite=entry_in.favorite,
        capture_date=datetime.now(UTC) if entry_in.is_captured else None
    )

    session.add(db_entry)      # Lo preparamos para guardar
    session.commit()           # Lo guardamos de verdad en pokedex.db
    session.refresh(db_entry)  # Recargamos el objeto para obtener su ID asignado
    return db_entry

#lee todos los pokemons guardados en en la base de datos
def get_all_entries(session: Session) -> list[PokedexEntry]:
    statement = select(PokedexEntry)
    return list(session.exec(statement).all())

#actualizacion parcial: PATCH, modifica mote, notas, favoritos....
def update_pokedex_entry(session: Session, entry_id: int, entry_in: PokedexEntryUpdate) -> PokedexEntry:
    db_entry = session.get(PokedexEntry, entry_id)

    #si el id no existe manda el error 404
    if not db_entry:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "about:blank",
                "title": "Entrada no encontrada",
                "status": 404,
                "detail": f"No existe ninguna entrada en la Pokédex con id={entry_id}."
            }
        )

    #se cogen solo los datos que el usuario haya enviado en el JSON
    update_data = entry_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_entry, key, value)

    session.add(db_entry)
    session.commit()
    session.refresh(db_entry)
    return db_entry