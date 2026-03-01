"""Flujo crear_cuenta."""
from telegram import Update
from telegram.ext import ContextTypes

from src.config import CREAR_CUENTA_NOMBRE, CREAR_CUENTA_TIPO, END
from src.database import crear_cuenta


async def crear_cuenta_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Nombre de la cuenta?")
    return CREAR_CUENTA_NOMBRE


async def crear_cuenta_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["crear_cuenta_nombre"] = update.message.text.strip().lower()
    await update.message.reply_text("¿Tipo? (credito o debito)")
    return CREAR_CUENTA_TIPO


async def crear_cuenta_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tipo = update.message.text.strip().lower()
    if tipo not in ("credito", "debito"):
        await update.message.reply_text("Tipo inválido. Escribe: credito o debito")
        return CREAR_CUENTA_TIPO
    nombre = context.user_data["crear_cuenta_nombre"]
    user_id = update.effective_user.id
    exito, mensaje = crear_cuenta(user_id, nombre, tipo)
    await update.message.reply_text(mensaje)
    return END
