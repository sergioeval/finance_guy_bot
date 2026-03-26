"""Flujos registros, editar, eliminar."""
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config import (
    REGISTROS_CUENTA,
    EDITAR_ID,
    EDITAR_MONTO,
    EDITAR_CATEGORIA,
    ELIMINAR_ID,
    END,
)
from src.database import (
    listar_cuentas,
    listar_registros,
    obtener_cuenta_por_id,
    editar_registro,
    eliminar_registro,
)
from src.handlers.cuenta_inline import keyboard_cuentas
from src.utils import is_null, parse_cantidad, formato_tipo

_REGISTROS_CUENTA_CB = re.compile(r"^reg:(\d+)$")


async def registros_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if not cuentas:
        await update.message.reply_text(
            "No tienes cuentas. Crea una con /crear_cuenta y vuelve a usar /registros."
        )
        return END
    await update.message.reply_text(
        "Elige la cuenta (o escribe el nombre):",
        reply_markup=keyboard_cuentas(cuentas, "reg"),
    )
    return REGISTROS_CUENTA


async def _enviar_registros_texto(message, user_id: int, nombre_cuenta: str) -> None:
    registros, nombre = listar_registros(user_id, nombre_cuenta)
    if registros is None:
        await message.reply_text(nombre)
        return
    if not registros:
        await message.reply_text(f"No hay registros en la cuenta '{nombre}'.")
        return
    LIMITE = 25
    mostrar = registros[:LIMITE]
    lineas = [f"📜 Registros de {nombre}:\n"]
    for r in mostrar:
        fecha = r["creada_en"][:10] if r.get("creada_en") else "?"
        tipo_str = formato_tipo(r["tipo"])
        monto = r["monto"]
        monto_str = f"-${monto:,.2f}" if r["tipo"] in ("gasto", "transferencia_salida") else f"+${monto:,.2f}"
        extra = f" → {r['cuenta_relacionada']}" if r.get("cuenta_relacionada") else ""
        cat = f" [{r.get('categoria', 'sin_categoria')}]" if r["tipo"] in ("gasto", "ingreso") else ""
        lineas.append(f"#{r['id']} | {fecha} | {tipo_str}{extra}{cat} | {monto_str}")
    if len(registros) > LIMITE:
        lineas.append(f"\n... y {len(registros) - LIMITE} más.")
    lineas.append("Usa /editar o /eliminar para modificar o borrar.")
    await message.reply_text("\n".join(lineas))


async def registros_cuenta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _REGISTROS_CUENTA_CB.match(query.data or "")
    if not m:
        await query.answer()
        return REGISTROS_CUENTA
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Usa /registros de nuevo.", show_alert=True)
        return REGISTROS_CUENTA
    await query.answer()
    await query.edit_message_text(f"Cuenta: {cuenta['nombre']}")
    await _enviar_registros_texto(query.message, user_id, cuenta["nombre"].strip().lower())
    return END


async def registros_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    nombre_cuenta = update.message.text.strip().lower()
    await _enviar_registros_texto(update.message, user_id, nombre_cuenta)
    return END


async def editar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿ID del registro? (usa /registros para ver los IDs)")
    return EDITAR_ID


async def editar_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        transaccion_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID inválido. Escribe un número.")
        return EDITAR_ID
    context.user_data["editar_id"] = transaccion_id
    await update.message.reply_text("¿Nuevo monto? (o null para no cambiar)")
    return EDITAR_MONTO


async def editar_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if is_null(text):
        context.user_data["editar_monto"] = None
    else:
        monto = parse_cantidad(text)
        if monto is not None and monto > 0:
            context.user_data["editar_monto"] = monto
        else:
            context.user_data["editar_monto"] = None
    await update.message.reply_text("¿Nueva categoría? (o null para no cambiar)")
    return EDITAR_CATEGORIA


async def editar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    monto = context.user_data.get("editar_monto")
    categoria = None if is_null(text) else text
    if monto is None and categoria is None:
        await update.message.reply_text("Debes cambiar al menos monto o categoría. Usa /editar para reintentar.")
        return END
    user_id = update.effective_user.id
    transaccion_id = context.user_data["editar_id"]
    exito, mensaje = editar_registro(user_id, transaccion_id, monto=monto, categoria=categoria)
    await update.message.reply_text(mensaje)
    return END


async def eliminar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿ID del registro? (usa /registros para ver los IDs)")
    return ELIMINAR_ID


async def eliminar_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        transaccion_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID inválido. Escribe un número.")
        return ELIMINAR_ID
    user_id = update.effective_user.id
    exito, mensaje = eliminar_registro(user_id, transaccion_id)
    await update.message.reply_text(mensaje)
    return END
