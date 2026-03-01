"""Flujos gasto, ingreso, transferencia."""
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
    END,
)
from src.database import registrar_gasto, registrar_ingreso, transferir
from src.utils import is_null, parse_cantidad


async def gasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿En qué cuenta?")
    return GASTO_CUENTA


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
    await update.message.reply_text("¿En qué cuenta?")
    return INGRESO_CUENTA


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
    await update.message.reply_text("¿Cuenta origen?")
    return TRANSFERENCIA_ORIGEN


async def transferencia_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["transferencia_origen"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Cuenta destino?")
    return TRANSFERENCIA_DESTINO


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
