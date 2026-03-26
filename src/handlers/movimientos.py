"""Flujos gasto, ingreso, transferencia."""
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config import (
    GASTO_CUENTA,
    GASTO_MONTO,
    GASTO_CATEGORIA,
    INGRESO_CUENTA,
    INGRESO_MONTO,
    INGRESO_CATEGORIA,
    TRANSFERENCIA_ORIGEN,
    TRANSFERENCIA_DESTINO,
    TRANSFERENCIA_MONTO,
    AJUSTAR_CUENTA,
    AJUSTAR_MONTO,
    END,
)
from src.database import (
    listar_cuentas,
    obtener_cuenta_por_id,
    obtener_cuenta_por_nombre,
    registrar_gasto,
    registrar_ingreso,
    registrar_ajuste_saldo,
    transferir,
)
from src.handlers.cuenta_inline import keyboard_cuentas
from src.utils import is_null, parse_cantidad

_GASTO_CUENTA_CB = re.compile(r"^gc:(\d+)$")
_INGRESO_CUENTA_CB = re.compile(r"^ic:(\d+)$")
_TRANSF_ORIGEN_CB = re.compile(r"^tro:(\d+)$")
_TRANSF_DESTINO_CB = re.compile(r"^trd:(\d+)$")
_AJUSTAR_CUENTA_CB = re.compile(r"^ac:(\d+)$")


async def gasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if not cuentas:
        await update.message.reply_text(
            "No tienes cuentas. Crea una con /crear_cuenta y vuelve a usar /gasto."
        )
        return END
    await update.message.reply_text(
        "Elige la cuenta (o escribe el nombre si prefieres):",
        reply_markup=keyboard_cuentas(cuentas, "gc"),
    )
    return GASTO_CUENTA


async def gasto_cuenta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _GASTO_CUENTA_CB.match(query.data or "")
    if not m:
        await query.answer()
        return GASTO_CUENTA
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Usa /gasto de nuevo.", show_alert=True)
        return GASTO_CUENTA
    await query.answer()
    context.user_data["gasto_cuenta"] = cuenta["nombre"].strip().lower()
    await query.edit_message_text(
        f"Cuenta: {cuenta['nombre']}\n\n¿Monto?"
    )
    return GASTO_MONTO


async def gasto_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gasto_cuenta"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Monto?")
    return GASTO_MONTO


async def gasto_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_cantidad(update.message.text)
    if monto is None or monto <= 0:
        await update.message.reply_text("Monto inválido. Escribe un número mayor a 0.")
        return GASTO_MONTO
    context.user_data["gasto_monto"] = monto
    await update.message.reply_text("¿Categoría? (o null para sin_categoria)")
    return GASTO_CATEGORIA


async def gasto_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    categoria = "sin_categoria" if is_null(cat) else cat
    user_id = update.effective_user.id
    cuenta = context.user_data["gasto_cuenta"]
    monto = context.user_data["gasto_monto"]
    exito, mensaje = registrar_gasto(user_id, cuenta, monto, categoria)
    await update.message.reply_text(mensaje)
    return END


async def ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if not cuentas:
        await update.message.reply_text(
            "No tienes cuentas. Crea una con /crear_cuenta y vuelve a usar /ingreso."
        )
        return END
    await update.message.reply_text(
        "Elige la cuenta (o escribe el nombre si prefieres):",
        reply_markup=keyboard_cuentas(cuentas, "ic"),
    )
    return INGRESO_CUENTA


async def ingreso_cuenta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _INGRESO_CUENTA_CB.match(query.data or "")
    if not m:
        await query.answer()
        return INGRESO_CUENTA
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Usa /ingreso de nuevo.", show_alert=True)
        return INGRESO_CUENTA
    await query.answer()
    context.user_data["ingreso_cuenta"] = cuenta["nombre"].strip().lower()
    await query.edit_message_text(
        f"Cuenta: {cuenta['nombre']}\n\n¿Monto?"
    )
    return INGRESO_MONTO


async def ingreso_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ingreso_cuenta"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Monto?")
    return INGRESO_MONTO


async def ingreso_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_cantidad(update.message.text)
    if monto is None or monto <= 0:
        await update.message.reply_text("Monto inválido. Escribe un número mayor a 0.")
        return INGRESO_MONTO
    context.user_data["ingreso_monto"] = monto
    await update.message.reply_text("¿Categoría? (o null para sin_categoria)")
    return INGRESO_CATEGORIA


async def ingreso_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    categoria = "sin_categoria" if is_null(cat) else cat
    user_id = update.effective_user.id
    cuenta = context.user_data["ingreso_cuenta"]
    monto = context.user_data["ingreso_monto"]
    exito, mensaje = registrar_ingreso(user_id, cuenta, monto, categoria)
    await update.message.reply_text(mensaje)
    return END


async def transferencia_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if len(cuentas) < 2:
        await update.message.reply_text(
            "Necesitas al menos dos cuentas para transferir. Usa /crear_cuenta si hace falta."
        )
        return END
    await update.message.reply_text(
        "Elige la cuenta origen (o escribe el nombre):",
        reply_markup=keyboard_cuentas(cuentas, "tro"),
    )
    return TRANSFERENCIA_ORIGEN


async def _transferencia_pedir_destino(
    message,
    user_id: int,
    origen_nombre_lower: str,
) -> bool:
    """Envía el teclado de destino. Retorna False si no hay otra cuenta."""
    origen = obtener_cuenta_por_nombre(user_id, origen_nombre_lower)
    if not origen:
        await message.reply_text(f"No se encontró la cuenta '{origen_nombre_lower}'.")
        return False
    cuentas = listar_cuentas(user_id)
    otras = [c for c in cuentas if c["id"] != origen["id"]]
    if not otras:
        await message.reply_text("No tienes otra cuenta como destino.")
        return False
    await message.reply_text(
        "Elige la cuenta destino (o escribe el nombre):",
        reply_markup=keyboard_cuentas(cuentas, "trd", excluir_id=origen["id"]),
    )
    return True


async def transferencia_origen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _TRANSF_ORIGEN_CB.match(query.data or "")
    if not m:
        await query.answer()
        return TRANSFERENCIA_ORIGEN
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Usa /transferencia de nuevo.", show_alert=True)
        return TRANSFERENCIA_ORIGEN
    await query.answer()
    context.user_data["transferencia_origen"] = cuenta["nombre"].strip().lower()
    await query.edit_message_text(f"Origen: {cuenta['nombre']}")
    ok = await _transferencia_pedir_destino(query.message, user_id, cuenta["nombre"].strip().lower())
    if not ok:
        return END
    return TRANSFERENCIA_DESTINO


async def transferencia_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    nombre = update.message.text.strip().lower()
    cuenta = obtener_cuenta_por_nombre(user_id, nombre)
    if not cuenta:
        await update.message.reply_text(f"No se encontró la cuenta '{nombre}'.")
        return TRANSFERENCIA_ORIGEN
    context.user_data["transferencia_origen"] = nombre
    ok = await _transferencia_pedir_destino(update.message, user_id, nombre)
    if not ok:
        return END
    return TRANSFERENCIA_DESTINO


async def transferencia_destino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _TRANSF_DESTINO_CB.match(query.data or "")
    if not m:
        await query.answer()
        return TRANSFERENCIA_DESTINO
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Elige otra o usa /transferencia de nuevo.", show_alert=True)
        return TRANSFERENCIA_DESTINO
    await query.answer()
    context.user_data["transferencia_destino"] = cuenta["nombre"].strip().lower()
    await query.edit_message_text(
        f"Destino: {cuenta['nombre']}\n\n¿Monto?"
    )
    return TRANSFERENCIA_MONTO


async def transferencia_destino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["transferencia_destino"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Monto?")
    return TRANSFERENCIA_MONTO


async def transferencia_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_cantidad(update.message.text)
    if monto is None or monto <= 0:
        await update.message.reply_text("Monto inválido. Escribe un número mayor a 0.")
        return TRANSFERENCIA_MONTO
    user_id = update.effective_user.id
    origen = context.user_data["transferencia_origen"]
    destino = context.user_data["transferencia_destino"]
    exito, mensaje = transferir(user_id, origen, destino, monto)
    await update.message.reply_text(mensaje)
    return END


async def ajustar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if not cuentas:
        await update.message.reply_text(
            "No tienes cuentas. Crea una con /crear_cuenta y vuelve a usar /ajustar."
        )
        return END
    await update.message.reply_text(
        "Elige la cuenta a ajustar (o escribe el nombre):",
        reply_markup=keyboard_cuentas(cuentas, "ac"),
    )
    return AJUSTAR_CUENTA


async def ajustar_cuenta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _AJUSTAR_CUENTA_CB.match(query.data or "")
    if not m:
        await query.answer()
        return AJUSTAR_CUENTA
    cuenta_id = int(m.group(1))
    user_id = update.effective_user.id
    cuenta = obtener_cuenta_por_id(user_id, cuenta_id)
    if not cuenta:
        await query.answer("Esa cuenta ya no existe. Usa /ajustar de nuevo.", show_alert=True)
        return AJUSTAR_CUENTA
    await query.answer()
    context.user_data["ajustar_cuenta"] = cuenta["nombre"].strip().lower()
    await query.edit_message_text(
        f"Cuenta: {cuenta['nombre']}\n\n"
        "¿Saldo deseado? (la cuenta quedará exactamente con ese monto)"
    )
    return AJUSTAR_MONTO


async def ajustar_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ajustar_cuenta"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Saldo deseado? (la cuenta quedará exactamente con ese monto)")
    return AJUSTAR_MONTO


async def ajustar_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    saldo_objetivo = parse_cantidad(update.message.text)
    if saldo_objetivo is None:
        await update.message.reply_text("Monto inválido. Escribe un número (ej. 1500 o -50).")
        return AJUSTAR_MONTO
    user_id = update.effective_user.id
    cuenta = context.user_data["ajustar_cuenta"]
    _, mensaje = registrar_ajuste_saldo(user_id, cuenta, saldo_objetivo)
    await update.message.reply_text(mensaje)
    return END
