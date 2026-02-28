"""Flujos registros, editar, eliminar."""
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
from src.database import listar_registros, editar_registro, eliminar_registro
from src.utils import is_null, parse_cantidad, formato_tipo


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
