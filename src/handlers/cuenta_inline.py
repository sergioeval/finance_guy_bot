"""Teclado en línea para elegir una cuenta."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def keyboard_cuentas(
    cuentas: list[dict], prefix: str, *, excluir_id: int | None = None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for c in cuentas:
        if excluir_id is not None and c["id"] == excluir_id:
            continue
        row.append(
            InlineKeyboardButton(c["nombre"], callback_data=f"{prefix}:{c['id']}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)
