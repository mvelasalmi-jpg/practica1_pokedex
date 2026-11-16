"""Generación de PDF: ficha de un Pokémon, exportación de la Pokédex y de un equipo.

Usamos la librería fpdf2, que dibuja el PDF con instrucciones simples:
«escribe este texto aquí», «pon esta imagen», «dibuja este rectángulo».

Importante: este módulo NO sabe nada de FastAPI ni de la base de datos. Recibe
datos ya preparados y devuelve los bytes del PDF. Así es fácil de probar.
"""

import io
import logging

from fpdf import FPDF

logger = logging.getLogger("pokedex_api.pdf")

STATS = ("hp", "attack", "defense", "speed")
NOMBRES_STATS = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defensa",
    "speed": "Velocidad",
}


def _t(texto: object) -> str:
    """Prepara un texto para el PDF.

    Las fuentes básicas de PDF sólo conocen el alfabeto latin-1 (con tildes y ñ, pero
    sin emojis ni símbolos raros). Lo que no cabe se sustituye por '?' en vez de
    hacer fallar la generación entera.
    """
    if texto is None:
        return ""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _nuevo_pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(
        auto=True, margin=15
    )  # salta de página solo al llegar abajo
    pdf.add_page()
    return pdf


def _titulo(pdf: FPDF, texto: str, tamano: int = 20) -> None:
    pdf.set_font("Helvetica", "B", tamano)
    # new_x/new_y: después de escribir, baja a la línea siguiente y vuelve al margen.
    pdf.cell(0, 12, _t(texto), new_x="LMARGIN", new_y="NEXT")


def _linea(pdf: FPDF, texto: str, negrita: bool = False, tamano: int = 11) -> None:
    pdf.set_font("Helvetica", "B" if negrita else "", tamano)
    # multi_cell reparte el texto en varias líneas si no cabe en el ancho de página.
    pdf.multi_cell(0, 6, _t(texto), new_x="LMARGIN", new_y="NEXT")


def _barra(pdf: FPDF, etiqueta: str, valor: int | None) -> None:
    """Una estadística con su barra proporcional (255 es el máximo posible)."""
    valor = valor or 0
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(38, 6, _t(f"{etiqueta}: {valor}"))
    x, y = pdf.get_x(), pdf.get_y() + 1.5
    pdf.set_fill_color(80, 160, 220)
    pdf.rect(x, y, 90 * min(valor, 255) / 255, 3, style="F")
    pdf.ln(6)


def _imagen(pdf: FPDF, datos: bytes | None, ancho: float = 35) -> None:
    """Pone el sprite si lo tenemos; si la imagen está rota, simplemente se omite."""
    if not datos:
        return
    try:
        pdf.image(io.BytesIO(datos), w=ancho)
    except Exception as error:  # noqa: BLE001 - imagen corrupta: no tiramos el PDF
        logger.warning("No se pudo incrustar el sprite: %s", error)


def _bloque_pokemon(
    pdf: FPDF, info: dict, especie: dict | None, sprite: bytes | None
) -> None:
    """Dibuja una ficha completa. La reutilizan la ficha suelta y la de equipos."""
    _titulo(pdf, f"#{info['id']}  {info['name'].capitalize()}", tamano=16)
    _imagen(pdf, sprite)
    _linea(pdf, "Tipos: " + (", ".join(info.get("types", [])) or "-"))
    _linea(pdf, "Habilidades: " + (", ".join(info.get("abilities", [])) or "-"))
    for clave in STATS:
        _barra(pdf, NOMBRES_STATS[clave], (info.get("stats") or {}).get(clave))
    if especie and especie.get("description"):
        pdf.ln(2)
        _linea(pdf, especie["description"], tamano=10)


def _a_bytes(pdf: FPDF) -> bytes:
    return bytes(pdf.output())


# ───────────────────────── PDFs públicos ─────────────────────────


def ficha_pokemon_pdf(
    info: dict, especie: dict | None = None, sprite: bytes | None = None
) -> bytes:
    """Ficha de un Pokémon: sprite, estadísticas, tipos, habilidades y descripción."""
    pdf = _nuevo_pdf()
    _bloque_pokemon(pdf, info, especie, sprite)
    return _a_bytes(pdf)


def pokedex_pdf(entradas: list[dict], titulo: str = "Mi Pokédex") -> bytes:
    """Tabla con las entradas de la Pokédex de un usuario."""
    pdf = _nuevo_pdf()
    _titulo(pdf, titulo)
    _linea(pdf, f"Total de entradas: {len(entradas)}")
    pdf.ln(3)

    columnas = [
        ("ID", 15),
        ("Nombre", 40),
        ("Apodo", 40),
        ("Capturado", 28),
        ("Favorito", 25),
        ("Fecha captura", 42),
    ]
    pdf.set_font("Helvetica", "B", 10)
    for nombre, ancho in columnas:
        pdf.cell(ancho, 8, nombre, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    for e in entradas:
        fila = [
            e["pokemon_id"],
            e["pokemon_name"],
            e.get("nickname") or "-",
            "Si" if e["is_captured"] else "No",
            "Si" if e["favorite"] else "No",
            (e.get("capture_date") or "-")[:10],
        ]
        for valor, (_, ancho) in zip(fila, columnas):
            # [:22] recorta textos largos para que no se salgan de su celda
            pdf.cell(ancho, 7, _t(valor)[:22], border=1)
        pdf.ln()
    return _a_bytes(pdf)


def equipo_pdf(
    nombre: str,
    descripcion: str | None,
    fichas: list[tuple[dict, bytes | None]],
) -> bytes:
    """Equipo completo: cabecera, una ficha por Pokémon y estadísticas combinadas.

    `fichas` es una lista de (info_del_pokemon, bytes_del_sprite).
    """
    pdf = _nuevo_pdf()
    _titulo(pdf, f"Equipo: {nombre}", tamano=22)
    if descripcion:
        _linea(pdf, descripcion)
    pdf.ln(3)

    # Estadísticas combinadas = suma de cada estadística de todos los miembros.
    totales = {clave: 0 for clave in STATS}
    for info, _ in fichas:
        for clave in STATS:
            totales[clave] += (info.get("stats") or {}).get(clave) or 0

    _titulo(pdf, "Estadisticas combinadas", tamano=14)
    for clave in STATS:
        _linea(pdf, f"{NOMBRES_STATS[clave]}: {totales[clave]}")
    _linea(pdf, f"Total: {sum(totales.values())}", negrita=True)

    for info, sprite in fichas:
        # Si la ficha no cabe en lo que queda de página, empieza una nueva.
        if pdf.will_page_break(75):
            pdf.add_page()
        pdf.ln(4)
        _bloque_pokemon(pdf, info, None, sprite)
    return _a_bytes(pdf)
