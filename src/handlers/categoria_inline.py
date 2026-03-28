"""Teclado en línea para elegir una categoría definida por el usuario."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def texto_elegir_categoria(categorias: list[dict]) -> str:
    lineas = ["Elige categoría con los botones o escribe el nombre exacto:\n"]
    for c in categorias:
        lineas.append(f"• {c['nombre']}")
    return "\n".join(lineas)


def keyboard_categorias(categorias: list[dict], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for c in categorias:
        label = c["nombre"]
        if len(label) > 40:
            label = label[:37] + "..."
        row.append(
            InlineKeyboardButton(label, callback_data=f"{prefix}:{c['id']}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)
