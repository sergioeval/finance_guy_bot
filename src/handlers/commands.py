"""Comandos simples sin conversación."""
from telegram import Update
from telegram.ext import ContextTypes

from src.config import END
from src.database import listar_cuentas, obtener_resumen


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 ¡Hola! Soy tu bot de finanzas personales.\n\n"
        "Usa /help para ver la guía completa. Los comandos piden los datos paso a paso."
    )


def get_help_text() -> str:
    return """📖 <b>Ayuda - Bot de Finanzas Personales</b>

Los comandos piden cada parámetro <b>paso a paso</b>. Para parámetros opcionales, escribe <b>null</b>.

<b>Cuentas</b>
/crear_cuenta — Te pedirá: nombre, tipo (credito/debito)

/cuentas — Lista todas tus cuentas

<b>Movimientos</b>
/gasto — Te pedirá: cuenta, monto, categoría (null = sin_categoria)

/ingreso — Te pedirá: cuenta, monto, categoría (null = sin_categoria)

/transferencia — Te pedirá: cuenta origen, cuenta destino, monto

<b>Historial</b>
/registros — Te pedirá: nombre de cuenta

/editar — Te pedirá: ID, nuevo monto (null = no cambiar), categoría (null = no cambiar)

/eliminar — Te pedirá: ID del registro

<b>Resúmenes</b>
/resumen — Resumen total (sin parámetros)

/resumen_categorias — Te pedirá: mes (1-12 o null), año (null = todos)

/resumen_mes — Te pedirá: año (null = últimos 12 meses), mes (null = todos)

<b>Otros</b>
/cancel — Cancela el comando actual
/help — Esta ayuda"""


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(get_help_text(), parse_mode="HTML")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operación cancelada.")
    return END


async def cmd_cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cuentas = listar_cuentas(user_id)
    if not cuentas:
        await update.message.reply_text("No tienes ninguna cuenta. Usa /crear_cuenta para crear una.")
        return
    lineas = ["📋 Tus cuentas:\n"]
    for c in cuentas:
        emoji = "💳" if c["tipo"] == "debito" else "📄"
        lineas.append(f"{emoji} {c['nombre']} ({c['tipo']}): ${c['saldo']:,.2f}")
    await update.message.reply_text("\n".join(lineas))


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    resumen = obtener_resumen(user_id)
    cuentas = resumen["cuentas"]
    if not cuentas:
        await update.message.reply_text("No tienes ninguna cuenta. Usa /crear_cuenta para crear una.")
        return
    lineas = ["📊 Resumen de finanzas\n"]
    for c in cuentas:
        emoji = "💳" if c["tipo"] == "debito" else "📄"
        lineas.append(f"{emoji} {c['nombre']}: ${c['saldo']:,.2f}")
    lineas.append("")
    lineas.append(f"💰 Total débito: ${resumen['total_debito']:,.2f}")
    lineas.append(f"📄 Total crédito: ${resumen['total_credito']:,.2f}")
    lineas.append(f"📈 Patrimonio neto: ${resumen['patrimonio_neto']:,.2f}")
    await update.message.reply_text("\n".join(lineas))
