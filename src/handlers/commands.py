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
/gasto — Elige cuenta con los botones (o escribe el nombre), luego monto y categoría (null = sin_categoria)

/ingreso — Elige cuenta con los botones (o escribe el nombre), luego monto y categoría (null = sin_categoria)

/transferencia — Elige origen y destino con botones (o nombre), luego monto (mínimo 2 cuentas)

/ajustar — Elige cuenta con botones (o nombre), luego saldo deseado (registro [ajuste])

<b>Historial</b>
/registros — Elige cuenta con botones (o escribe el nombre)

/editar — Te pedirá: ID, nuevo monto (null = no cambiar), categoría (null = no cambiar)

/eliminar — Te pedirá: ID del registro

<b>Resúmenes</b>
/resumen — Resumen total (sin parámetros)

/resumen_categorias — Te pedirá: mes (1-12 o null), año (null = todos)

/resumen_mes — Te pedirá: año (null = últimos 12 meses), mes (null = todos)

<b>Presupuesto</b> (una sola lista por usuario; tabla aparte; no afecta cuentas ni transacciones)
/gasto_presupuesto — Monto, ¿anual? (si = total año, se divide entre 12 en totales; null = mensual), categoría

/ingreso_presupuesto — Igual, como ingreso planificado

/resumen_presupuesto — Lista #id, totales y balance (sin preguntas)

/editar_registro_presupuesto — ID (ver /resumen_presupuesto), monto y/o categoría (null = no cambiar)

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


def formatear_resumen(user_id: int) -> str | None:
    """Genera el texto del resumen para un usuario. Retorna None si no tiene cuentas."""
    resumen = obtener_resumen(user_id)
    cuentas = resumen["cuentas"]
    if not cuentas:
        return None
    lineas = ["📊 Resumen de finanzas\n"]
    for c in cuentas:
        emoji = "💳" if c["tipo"] == "debito" else "📄"
        lineas.append(f"{emoji} {c['nombre']}: ${c['saldo']:,.2f}")
    lineas.append("")
    lineas.append(f"💰 Total débito: ${resumen['total_debito']:,.2f}")
    lineas.append(f"📄 Total crédito: ${resumen['total_credito']:,.2f}")
    lineas.append(f"📈 Patrimonio neto: ${resumen['patrimonio_neto']:,.2f}")
    return "\n".join(lineas)


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    texto = formatear_resumen(user_id)
    if texto is None:
        await update.message.reply_text("No tienes ninguna cuenta. Usa /crear_cuenta para crear una.")
        return
    await update.message.reply_text(texto)
