"""Motor de base de datos y sesión por petición."""

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False: FastAPI atiende cada petición en un hilo distinto
# y SQLite, por defecto, sólo deja usar la conexión al hilo que la abrió.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    # Una sesión por petición; el with la cierra pase lo que pase.
    with Session(engine) as session:
        yield session
