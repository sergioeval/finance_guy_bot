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

<b>Categorías</b> (obligatorias para gastos e ingresos nuevos; los movimientos viejos no se borran)
/mis_categorias — Lista tus categorías con #id

/agregar_categoria — Nombre y ámbito: gasto, ingreso o ambos

/editar_mi_categoria — Renombra por #id (actualiza también movimientos con ese nombre)

<b>Movimientos</b>
/gasto — Cuenta, monto, luego categoría (botones o nombre exacto de /mis_categorias)

/ingreso — Igual que gasto, con categorías de ingreso o «ambos»

/transferencia — Elige origen y destino con botones (o nombre), luego monto (mínimo 2 cuentas)

/ajustar — Elige cuenta con botones (o nombre), luego saldo deseado (registro [ajuste])

<b>Historial</b>
/registros — Elige cuenta con botones (o escribe el nombre)

/editar — ID, monto (null = no cambiar), categoría (null = no cambiar; si cambias, debe estar en /mis_categorias)

/eliminar — Te pedirá: ID del registro

<b>Resúmenes</b>
/resumen — Resumen total (sin parámetros)

/resumen_categorias — Te pedirá: mes (1-12 o null), año (null = todos)

/resumen_mes — Te pedirá: año (null = últimos 12 meses), mes (null = todos)

<b>Presupuesto</b> (varios por nombre; no afecta cuentas ni transacciones reales)
/presupuestos — Lista nombres, #id y cantidad de líneas

/gasto_presupuesto — Nombre del presupuesto (se crea si no existe), monto, ¿anual?, categoría

/ingreso_presupuesto — Nombre del presupuesto, monto, categoría

/resumen_presupuesto — Nombre del presupuesto o «todos» para ver todos; líneas #id, totales y balance

/eliminar_registro_presupuesto — ID de la línea (# único entre presupuestos)

/clonar_presupuesto — Presupuesto origen (nombre o #id), luego nombre del presupuesto nuevo

/editar_registro_presupuesto — ID, monto y/o categoría válida en /mis_categorias (null = no cambiar)

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
