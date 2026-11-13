"""Modelos: Base (campos comunes) → Table (la tabla) → Create / Read / Update (los contratos)."""

#se importa utilidades de fecha y hora en formato estandar
from datetime import UTC, datetime

#validadores de Pydantic, comprueban que el email tiene @ y valida contraseñas
from pydantic import EmailStr, field_validator
#evitar duplicados en la base de datos
from sqlalchemy import UniqueConstraint
#importamos sqlmodel para la creacion de tablas, campos y relaciones
from sqlmodel import Field, Relationship, SQLModel

#funcion que devuelve fecha y hora exacta 
def ahora() -> datetime:
    return datetime.now(UTC)


# ───────────────────────────── Usuarios ─────────────────────────────

#tiene los campos comunes de un usuario
class UserBase(SQLModel):
    #nombre de usuario
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)
    #correo (pydantic es el encargado de ver que es valido)
    email: EmailStr = Field(unique=True, index=True)

#convierte una tabla real dentro de la pokedex.db
class User(UserBase, table=True):
    #clave primaria
    id: int | None = Field(default=None, primary_key=True)
    #se guarda la contraseña
    hashed_password: str
    #indica si la cuenta esta activa    
    is_active: bool = True
    #la fecha de registro
    created_at: datetime = Field(default_factory=ahora)

    #relaciona el ususario registrado con sus pokemons capturados y sus equipos 
    entries: list["PokedexEntry"] = Relationship(back_populates="owner")
    teams: list["Team"] = Relationship(back_populates="trainer")

#esquema de entrada cuando el usuario se registra
class UserCreate(UserBase):
    #pide la contraseña en texto para luego encriptarla    
    password: str = Field(min_length=8)

    #valida que la contraseña introducida sea valida: tener al menos una mayuscula y un numero
    @field_validator("password")
    @classmethod
    def password_robusta(cls, valor: str) -> str:
        if not any(c.isupper() for c in valor):
            raise ValueError("la contraseña necesita una mayúscula")
        if not any(c.isdigit() for c in valor):
            raise ValueError("la contraseña necesita un número")
        return valor

#esquema de salida con lo que le devolvemos al usuario
class UserRead(UserBase):
    # Lo que sale hacia fuera: nunca hashed_password.
    id: int
    created_at: datetime


# ───────────────────────────── Pokédex ─────────────────────────────

#modelo base: campos editables de cada pokemon guardado por un usuario
class PokedexEntryBase(SQLModel):
    nickname: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_captured: bool = False
    favorite: bool = False

#modelo de tablas: la tabla real en la pokedex.bd
class PokedexEntry(PokedexEntryBase, table=True):
    #restriccion: un umismo usuario no puede tener duplicados del mismo pokemon
    __table_args__ = (
        UniqueConstraint("owner_id", "pokemon_id", name="uq_pokedex_owner_pokemon"),
    )

    #es la clave foranea que enlaza esta entrada con el id de la tabla del usuario
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    pokemon_id: int = Field(index=True)
    pokemon_name: str
    pokemon_sprite: str | None = None
    capture_date: datetime | None = None
    created_at: datetime = Field(default_factory=ahora)

    #hace la realcion inversa para acceder a los datos del dueño desde la entrada
    owner: User | None = Relationship(back_populates="entries")

#lo que envia el usuario para añadir un pokemos a su pokedex
class PokedexEntryCreate(PokedexEntryBase):
    #se valida que la id del pkemos este entre 1 y 1025
    pokemon_id: int = Field(ge=1, le=1025)

#son los datos que se devuelven al usuario al consultar algo en la pokedex
class PokedexEntryRead(PokedexEntryBase):
    id: int
    owner_id: int
    pokemon_id: int
    pokemon_name: str
    pokemon_sprite: str | None
    capture_date: datetime | None
    created_at: datetime

#esquema de actualizacion parcial (para peticiones PATCH)
class PokedexEntryUpdate(SQLModel):
    # Todo opcional: PATCH sólo toca lo que llega. Modifica solo lo que envie el usuario
    nickname: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_captured: bool | None = None
    favorite: bool | None = None
    capture_date: datetime | None = None


# ───────────────────────────── Equipos ─────────────────────────────

#es una tabla que representa un equipo de pokemos creado por un entrenador
class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    trainer_id: int = Field(foreign_key="user.id", index=True) #dueño del equipo
    name: str = Field(max_length=100)      #nombre del equipo
    description: str | None = None
    created_at: datetime = Field(default_factory=ahora)

    #funcion que dice que si borras el equipo, directamente se borran los miembros asociados 
    trainer: User | None = Relationship(back_populates="teams")
    members: list["TeamMember"] = Relationship(
        back_populates="team", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

#es una tabla intermedia que une un equipo con una entrada pokedex
class TeamMember(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    pokedex_entry_id: int = Field(foreign_key="pokedexentry.id")
    #posicion del equipo (valida entre 1 y 6 como en los juegos de pokemospy -m pip install email-validator)
    position: int = Field(ge=1, le=6)

    team: Team | None = Relationship(back_populates="members")

# ───────────────────────────── Contratos de equipos ─────────────────────────────

#lo que envia el usuario para crear un equipo nuevo
class TeamCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)  # Nombre obligatorio del equipo
    description: str | None = None                   # Descripción opcional

#lo que se devuelve al consultar el equipo
class TeamRead(SQLModel):
    id: int
    trainer_id: int
    name: str
    description: str | None
    created_at: datetime

#update: modifica nombre o descripcion con PATCH
class TeamUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
