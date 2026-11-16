"""Tests del generador de PDF (sin FastAPI ni base de datos)."""

from app.services.pdf_service import _t, equipo_pdf, ficha_pokemon_pdf, pokedex_pdf
from tests.fakes import PNG_1X1

INFO = {
    "id": 25,
    "name": "pikachu",
    "types": ["electric"],
    "abilities": ["static"],
    "stats": {"hp": 35, "attack": 55, "defense": 40, "speed": 90},
}


def test_text_helper_replaces_unsupported_characters():
    assert _t("Pokémon") == "Pokémon"  # latin-1 sí soporta la é
    assert _t("♂") == "?"  # un símbolo fuera de latin-1 no rompe nada
    assert _t(None) == ""


def test_card_pdf_with_and_without_sprite():
    assert ficha_pokemon_pdf(INFO, {"description": "Texto"}, PNG_1X1).startswith(
        b"%PDF"
    )
    assert ficha_pokemon_pdf(INFO).startswith(b"%PDF")
    # un sprite corrupto se ignora en vez de romper el PDF
    assert ficha_pokemon_pdf(INFO, None, b"no soy una imagen").startswith(b"%PDF")


def test_pokedex_pdf_table():
    filas = [
        {
            "pokemon_id": 25,
            "pokemon_name": "pikachu",
            "nickname": None,
            "is_captured": True,
            "favorite": False,
            "capture_date": "2026-11-15T10:00:00",
        }
    ]
    assert pokedex_pdf(filas, "Pokédex de ash").startswith(b"%PDF")
    assert pokedex_pdf([]).startswith(b"%PDF")


def test_team_pdf_with_six_members_spans_pages():
    fichas = [(INFO, PNG_1X1)] * 6
    assert equipo_pdf("Elite", "Mi equipo", fichas).startswith(b"%PDF")
