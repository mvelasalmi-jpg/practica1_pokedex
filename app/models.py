"""Modelos: Base (campos comunes) → Table (la tabla) → Create / Read / Update (los contratos)."""

from datetime import UTC, datetime

from pydantic import EmailStr, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def ahora() -> datetime:
    return datetime.now(UTC)


# ───────────────────────────── Usuarios ─────────────────────────────


class UserBase(SQLModel):
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)
    email: EmailStr = Field(unique=True, index=True)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=ahora)

    entries: list["PokedexEntry"] = Relationship(back_populates="owner")
    teams: list["Team"] = Relationship(back_populates="trainer")


class UserCreate(UserBase):
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_robusta(cls, valor: str) -> str:
        if not any(c.isupper() for c in valor):
            raise ValueError("la contraseña necesita una mayúscula")
        if not any(c.isdigit() for c in valor):
            raise ValueError("la contraseña necesita un número")
        return valor


class UserRead(UserBase):
    # Lo que sale hacia fuera: nunca hashed_password.
    id: int
    created_at: datetime


# ───────────────────────────── Pokédex ─────────────────────────────


class PokedexEntryBase(SQLModel):
    nickname: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_captured: bool = False
    favorite: bool = False


class PokedexEntry(PokedexEntryBase, table=True):
    __table_args__ = (
        UniqueConstraint("owner_id", "pokemon_id", name="uq_pokedex_owner_pokemon"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    pokemon_id: int = Field(index=True)
    pokemon_name: str
    pokemon_sprite: str | None = None
    # Tipos del Pokémon separados por comas, p. ej. "grass,poison".
    # Los guardamos al añadir el Pokémon para poder calcular el tipo más común en
    # /pokedex/stats SIN tener que volver a llamar a la PokeAPI por cada entrada.
    pokemon_types: str | None = None
    capture_date: datetime | None = None
    created_at: datetime = Field(default_factory=ahora)

    owner: User | None = Relationship(back_populates="entries")


class PokedexEntryCreate(PokedexEntryBase):
    pokemon_id: int = Field(ge=1, le=1025)


class PokedexEntryRead(PokedexEntryBase):
    id: int
    owner_id: int
    pokemon_id: int
    pokemon_name: str
    pokemon_sprite: str | None
    pokemon_types: str | None
    capture_date: datetime | None
    created_at: datetime


class PokedexEntryUpdate(SQLModel):
    # Todo opcional: PATCH sólo toca lo que llega.
    nickname: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_captured: bool | None = None
    favorite: bool | None = None
    capture_date: datetime | None = None


# ───────────────────────────── Equipos ─────────────────────────────


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    trainer_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=100)
    description: str | None = None
    created_at: datetime = Field(default_factory=ahora)

    trainer: User | None = Relationship(back_populates="teams")
    members: list["TeamMember"] = Relationship(
        back_populates="team", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class TeamMember(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    pokedex_entry_id: int = Field(foreign_key="pokedexentry.id")
    position: int = Field(ge=1, le=6)

    team: Team | None = Relationship(back_populates="members")


# Contratos de los equipos. La tabla Team/TeamMember ya existía; faltaban los
# esquemas que definen qué entra y qué sale por la API.


def _sin_repetidos(ids: list[int] | None) -> list[int] | None:
    """Un Pokémon no puede estar dos veces en el mismo equipo."""
    if ids is not None and len(set(ids)) != len(ids):
        raise ValueError("no puede haber Pokémon repetidos en el equipo")
    return ids


class TeamCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    # IDs de PokeAPI (los mismos que pokemon_id de la Pokédex). Máximo 6.
    pokemon_ids: list[int] = Field(min_length=1, max_length=6)

    @field_validator("pokemon_ids")
    @classmethod
    def sin_repetidos(cls, valor: list[int]) -> list[int]:
        return _sin_repetidos(valor)


class TeamUpdate(SQLModel):
    # Todo opcional: sólo se cambia lo que llega en la petición.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    pokemon_ids: list[int] | None = Field(default=None, min_length=1, max_length=6)

    @field_validator("pokemon_ids")
    @classmethod
    def sin_repetidos(cls, valor: list[int] | None) -> list[int] | None:
        return _sin_repetidos(valor)


class TeamMemberRead(SQLModel):
    position: int
    pokemon_id: int
    pokemon_name: str
    pokemon_sprite: str | None
    nickname: str | None


class TeamRead(SQLModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    members: list[TeamMemberRead]
