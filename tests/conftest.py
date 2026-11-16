"""Ajustes compartidos por todos los tests (pytest los carga solo).

Un «fixture» es una pieza de preparación que pytest construye y entrega a los
tests que la piden por nombre. Aquí montamos: una base de datos limpia en memoria,
un cliente HTTP de pruebas, usuarios ya creados y cabeceras de login.
"""

import os

# IMPORTANTE: estas variables se fijan ANTES de importar la app, porque la
# configuración se lee en el momento del import. Así los tests nunca tocan la
# base de datos real ni dependen de tu .env.
os.environ["SECRET_KEY"] = "clave-solo-para-tests-0123456789abcdef"
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.auth import hash_password
from app.database import get_session
from app.dependencies import get_pokeapi_service
from app.limits import limiter
from app.main import app
from app.models import PokedexEntry, User
from app.services.pokeapi_service import PokeAPIService
from tests.fakes import FakePokeAPI

PASSWORD = "Pikachu123"


@pytest.fixture(autouse=True)
def limpiar_estado():
    """Se ejecuta antes de CADA test: contadores de rate limit y caché a cero."""
    limiter.reset()
    PokeAPIService.vaciar_cache()


@pytest.fixture
def engine():
    # StaticPool = una única conexión compartida; sin ella, cada hilo vería su
    # propia base de datos en memoria vacía.
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(motor)
    yield motor
    SQLModel.metadata.drop_all(motor)


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    def sesion_de_test():
        with Session(engine) as s:
            yield s

    # dependency_overrides: «cuando la app pida X, dale Y». Cambiamos la base de
    # datos real por la de memoria y la PokeAPI real por la falsa.
    app.dependency_overrides[get_session] = sesion_de_test
    app.dependency_overrides[get_pokeapi_service] = lambda: FakePokeAPI()
    yield TestClient(app)
    app.dependency_overrides.clear()


def crear_usuario(session: Session, username: str, email: str) -> User:
    usuario = User(
        username=username, email=email, hashed_password=hash_password(PASSWORD)
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def cabeceras(client: TestClient, username: str) -> dict:
    """Hace login y devuelve la cabecera Authorization lista para usar."""
    r = client.post(
        "/api/v1/auth/login", data={"username": username, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def test_user(session):
    return crear_usuario(session, "ash", "ash@example.com")


@pytest.fixture
def auth_headers(client, test_user):
    return cabeceras(client, "ash")


@pytest.fixture
def other_user_entry(session):
    """Una entrada de la Pokédex que pertenece a OTRO usuario."""
    otro = crear_usuario(session, "gary", "gary@example.com")
    entrada = PokedexEntry(
        owner_id=otro.id,
        pokemon_id=25,
        pokemon_name="pikachu",
        pokemon_types="electric",
    )
    session.add(entrada)
    session.commit()
    session.refresh(entrada)
    return entrada
