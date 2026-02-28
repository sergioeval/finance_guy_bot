"""
Bot de Telegram para gestión de finanzas personales.
Todos los comandos con parámetros piden los datos paso a paso.
Usa "null" para parámetros opcionales que quieras dejar vacíos.
"""
import os
import re
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import (
    init_db,
    crear_cuenta,
    listar_cuentas,
    listar_registros,
    eliminar_registro,
    editar_registro,
    registrar_gasto,
    registrar_ingreso,
    transferir,
    obtener_resumen,
    obtener_resumen_por_categoria,
    obtener_resumen_por_mes,
)

load_dotenv()

# Estados de conversación
(
    CREAR_CUENTA_NOMBRE,
    CREAR_CUENTA_TIPO,
    GASTO_CUENTA,
    GASTO_MONTO,
    GASTO_CATEGORIA,
    INGRESO_CUENTA,
    INGRESO_MONTO,
    INGRESO_CATEGORIA,
    TRANSFERENCIA_ORIGEN,
    TRANSFERENCIA_DESTINO,
    TRANSFERENCIA_MONTO,
    REGISTROS_CUENTA,
    EDITAR_ID,
    EDITAR_MONTO,
    EDITAR_CATEGORIA,
    ELIMINAR_ID,
    RESUMEN_CAT_MES,
    RESUMEN_CAT_ANO,
    RESUMEN_MES_ANO,
    RESUMEN_MES_MES,
) = range(20)

END = ConversationHandler.END


def is_null(text: str) -> bool:
    """True si el texto representa null (vacío/opcional)."""
    return text.strip().lower() == "null"


def parse_cantidad(texto: str) -> float | None:
    """Parsea una cantidad, aceptando formatos como 1000, 1.000,50, 1,000.50"""
    if not texto or not texto.strip():
        return None
    limpio = texto.strip().replace(",", ".")
    limpio = re.sub(r"\.(?=\d{3}\b)", "", limpio)
    try:
        return float(limpio)
    except ValueError:
        return None


def formato_tipo(tipo: str) -> str:
    mapeo = {
        "gasto": "Gasto",
        "ingreso": "Ingreso",
        "transferencia_salida": "Transferencia →",
        "transferencia_entrada": "Transferencia ←",
    }
    return mapeo.get(tipo, tipo)


MESES = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")

# --- Comandos sin parámetros (sin conversación) ---


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


# --- Flujo: crear_cuenta ---


async def crear_cuenta_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Nombre de la cuenta?")
    return CREAR_CUENTA_NOMBRE


async def crear_cuenta_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["crear_cuenta_nombre"] = update.message.text.strip()
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


# --- Flujo: gasto ---


async def gasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿En qué cuenta?")
    return GASTO_CUENTA


async def gasto_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gasto_cuenta"] = update.message.text.strip()
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
    cat = update.message.text.strip()
    categoria = "sin_categoria" if is_null(cat) else cat
    user_id = update.effective_user.id
    cuenta = context.user_data["gasto_cuenta"]
    monto = context.user_data["gasto_monto"]
    exito, mensaje = registrar_gasto(user_id, cuenta, monto, categoria)
    await update.message.reply_text(mensaje)
    return END


# --- Flujo: ingreso ---


async def ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿En qué cuenta?")
    return INGRESO_CUENTA


async def ingreso_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ingreso_cuenta"] = update.message.text.strip()
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
    cat = update.message.text.strip()
    categoria = "sin_categoria" if is_null(cat) else cat
    user_id = update.effective_user.id
    cuenta = context.user_data["ingreso_cuenta"]
    monto = context.user_data["ingreso_monto"]
    exito, mensaje = registrar_ingreso(user_id, cuenta, monto, categoria)
    await update.message.reply_text(mensaje)
    return END


# --- Flujo: transferencia ---


async def transferencia_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Cuenta origen?")
    return TRANSFERENCIA_ORIGEN


async def transferencia_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["transferencia_origen"] = update.message.text.strip()
    await update.message.reply_text("¿Cuenta destino?")
    return TRANSFERENCIA_DESTINO


async def transferencia_destino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["transferencia_destino"] = update.message.text.strip()
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


# --- Flujo: registros ---


async def registros_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Qué cuenta?")
    return REGISTROS_CUENTA


async def registros_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    nombre_cuenta = update.message.text.strip()
    registros, nombre = listar_registros(user_id, nombre_cuenta)
    if registros is None:
        await update.message.reply_text(nombre)
        return END
    if not registros:
        await update.message.reply_text(f"No hay registros en la cuenta '{nombre}'.")
        return END
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
    await update.message.reply_text("\n".join(lineas))
    return END


# --- Flujo: editar ---


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
    text = update.message.text.strip()
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


# --- Flujo: eliminar ---


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


# --- Flujo: resumen_categorias ---


async def resumen_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Mes? (1-12, o null para todos)")
    return RESUMEN_CAT_MES


async def resumen_cat_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if is_null(text):
        context.user_data["resumen_cat_mes"] = None
    else:
        try:
            m = int(text)
            if 1 <= m <= 12:
                context.user_data["resumen_cat_mes"] = m
            else:
                context.user_data["resumen_cat_mes"] = None
        except ValueError:
            context.user_data["resumen_cat_mes"] = None
    await update.message.reply_text("¿Año? (ej: 2025, o null para todos)")
    return RESUMEN_CAT_ANO


async def resumen_cat_ano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mes = context.user_data.get("resumen_cat_mes")
    ano = None
    if not is_null(text):
        try:
            ano = int(text)
        except ValueError:
            pass
    user_id = update.effective_user.id
    resumen = obtener_resumen_por_categoria(user_id, ano=ano, mes=mes)
    titulo = "📂 Resumen por categoría"
    if ano is not None and mes is not None:
        titulo += f" ({MESES[mes]} {ano})"
    elif ano is not None:
        titulo += f" ({ano})"
    else:
        titulo += " (todo el historial)"
    lineas = [titulo + "\n"]
    if resumen["gastos"] or resumen["ingresos"]:
        lineas.append("📤 Gastos por categoría:")
        for g in resumen["gastos"]:
            lineas.append(f"  • {g['categoria']}: ${g['total']:,.2f}")
        lineas.append(f"  Total gastos: ${resumen['total_gastos']:,.2f}\n")
        lineas.append("📥 Ingresos por categoría:")
        for i in resumen["ingresos"]:
            lineas.append(f"  • {i['categoria']}: ${i['total']:,.2f}")
        lineas.append(f"  Total ingresos: ${resumen['total_ingresos']:,.2f}\n")
        balance = resumen["total_ingresos"] - resumen["total_gastos"]
        lineas.append(f"📊 Balance: ${balance:,.2f}")
    else:
        lineas.append("No hay gastos ni ingresos registrados.")
    await update.message.reply_text("\n".join(lineas))
    return END


# --- Flujo: resumen_mes ---


async def resumen_mes_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Año? (ej: 2025, o null para últimos 12 meses)")
    return RESUMEN_MES_ANO


async def resumen_mes_ano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if is_null(text):
        context.user_data["resumen_mes_ano"] = None
        context.user_data["resumen_mes_mes"] = None
        # Sin año = últimos 12 meses, no necesitamos mes
        user_id = update.effective_user.id
        registros = obtener_resumen_por_mes(user_id, ano=None, mes=None, limite=12)
        await _enviar_resumen_mes(update, registros, None, None)
        return END
    try:
        ano = int(text)
    except ValueError:
        await update.message.reply_text("Año inválido. Escribe un número (ej: 2025) o null.")
        return RESUMEN_MES_ANO
    context.user_data["resumen_mes_ano"] = ano
    await update.message.reply_text("¿Mes? (1-12, o null para todos los meses del año)")
    return RESUMEN_MES_MES


async def resumen_mes_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    ano = context.user_data["resumen_mes_ano"]
    mes = None
    if not is_null(text):
        try:
            m = int(text)
            if 1 <= m <= 12:
                mes = m
        except ValueError:
            pass
    user_id = update.effective_user.id
    registros = obtener_resumen_por_mes(user_id, ano=ano, mes=mes, limite=12)
    await _enviar_resumen_mes(update, registros, ano, mes)
    return END


async def _enviar_resumen_mes(update: Update, registros: list, ano: int | None, mes: int | None) -> None:
    if ano is not None and mes is not None:
        titulo = f"📅 Resumen {MESES[mes]} {ano}"
    elif ano is not None:
        titulo = f"📅 Resumen mensual {ano}"
    else:
        titulo = "📅 Resumen mensual (últimos 12 meses)"
    lineas = [titulo + "\n"]
    if registros:
        for r in registros:
            m = r["mes"]
            a = r["ano"]
            g = r["gastos"] or 0
            i = r["ingresos"] or 0
            b = r["balance"]
            mes_nom = MESES[m] if 1 <= m <= 12 else str(m)
            lineas.append(f"{mes_nom} {a}: gastos ${g:,.2f} | ingresos ${i:,.2f} | balance ${b:,.2f}")
    else:
        lineas.append("No hay movimientos en el período indicado.")
    await update.message.reply_text("\n".join(lineas))


# --- ConversationHandler ---

TEXT = filters.TEXT & ~filters.COMMAND

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("crear_cuenta", crear_cuenta_start),
        CommandHandler("gasto", gasto_start),
        CommandHandler("ingreso", ingreso_start),
        CommandHandler("transferencia", transferencia_start),
        CommandHandler("registros", registros_start),
        CommandHandler("editar", editar_start),
        CommandHandler("eliminar", eliminar_start),
        CommandHandler("resumen_categorias", resumen_cat_start),
        CommandHandler("resumen_mes", resumen_mes_start),
    ],
    states={
        CREAR_CUENTA_NOMBRE: [MessageHandler(TEXT, crear_cuenta_nombre)],
        CREAR_CUENTA_TIPO: [MessageHandler(TEXT, crear_cuenta_tipo)],
        GASTO_CUENTA: [MessageHandler(TEXT, gasto_cuenta)],
        GASTO_MONTO: [MessageHandler(TEXT, gasto_monto)],
        GASTO_CATEGORIA: [MessageHandler(TEXT, gasto_categoria)],
        INGRESO_CUENTA: [MessageHandler(TEXT, ingreso_cuenta)],
        INGRESO_MONTO: [MessageHandler(TEXT, ingreso_monto)],
        INGRESO_CATEGORIA: [MessageHandler(TEXT, ingreso_categoria)],
        TRANSFERENCIA_ORIGEN: [MessageHandler(TEXT, transferencia_origen)],
        TRANSFERENCIA_DESTINO: [MessageHandler(TEXT, transferencia_destino)],
        TRANSFERENCIA_MONTO: [MessageHandler(TEXT, transferencia_monto)],
        REGISTROS_CUENTA: [MessageHandler(TEXT, registros_cuenta)],
        EDITAR_ID: [MessageHandler(TEXT, editar_id)],
        EDITAR_MONTO: [MessageHandler(TEXT, editar_monto)],
        EDITAR_CATEGORIA: [MessageHandler(TEXT, editar_categoria)],
        ELIMINAR_ID: [MessageHandler(TEXT, eliminar_id)],
        RESUMEN_CAT_MES: [MessageHandler(TEXT, resumen_cat_mes)],
        RESUMEN_CAT_ANO: [MessageHandler(TEXT, resumen_cat_ano)],
        RESUMEN_MES_ANO: [MessageHandler(TEXT, resumen_mes_ano)],
        RESUMEN_MES_MES: [MessageHandler(TEXT, resumen_mes_mes)],
    },
    fallbacks=[
        CommandHandler("cancel", cmd_cancel),
        CommandHandler("crear_cuenta", crear_cuenta_start),
        CommandHandler("gasto", gasto_start),
        CommandHandler("ingreso", ingreso_start),
        CommandHandler("transferencia", transferencia_start),
        CommandHandler("registros", registros_start),
        CommandHandler("editar", editar_start),
        CommandHandler("eliminar", eliminar_start),
        CommandHandler("resumen_categorias", resumen_cat_start),
        CommandHandler("resumen_mes", resumen_mes_start),
    ],
)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Mensaje de bienvenida"),
        BotCommand("help", "Ayuda detallada"),
        BotCommand("cancel", "Cancelar comando actual"),
        BotCommand("crear_cuenta", "Crear cuenta"),
        BotCommand("cuentas", "Ver cuentas"),
        BotCommand("gasto", "Registrar gasto"),
        BotCommand("ingreso", "Registrar ingreso"),
        BotCommand("transferencia", "Transferir"),
        BotCommand("registros", "Listar movimientos"),
        BotCommand("editar", "Editar registro"),
        BotCommand("eliminar", "Eliminar registro"),
        BotCommand("resumen", "Resumen total"),
        BotCommand("resumen_categorias", "Resumen por categoría"),
        BotCommand("resumen_mes", "Resumen mensual"),
    ])


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN no encontrado en .env")
        return

    init_db()

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cuentas", cmd_cuentas))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(conv_handler)

    print("Bot iniciado. Presiona Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
