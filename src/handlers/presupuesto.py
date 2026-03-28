"""Presupuesto único por usuario (tabla presupuesto_movimientos; sin periodo año/mes)."""
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config import (
    GASTO_PRESUPUESTO_MONTO,
    GASTO_PRESUPUESTO_ANUAL,
    GASTO_PRESUPUESTO_CATEGORIA,
    INGRESO_PRESUPUESTO_MONTO,
    INGRESO_PRESUPUESTO_CATEGORIA,
    EDITAR_PRESUPUESTO_ID,
    EDITAR_PRESUPUESTO_MONTO,
    EDITAR_PRESUPUESTO_CATEGORIA,
    END,
)
from src.database import (
    agregar_presupuesto_registro,
    categoria_permitida_para_movimiento,
    editar_presupuesto_registro,
    listar_categorias_para_movimiento,
    listar_presupuesto,
    obtener_categoria_usuario_por_id,
    totales_presupuesto,
)
from src.handlers.categoria_inline import keyboard_categorias, texto_elegir_categoria
from src.utils import is_null, parse_cantidad

_PRES_GASTO_CAT_CB = re.compile(r"^pg:(\d+)$")
_PRES_INGRESO_CAT_CB = re.compile(r"^pi:(\d+)$")


def _formatear_linea_presupuesto(r: dict) -> str:
    es_anual = bool(r.get("es_anual", 0))
    if r["tipo"] == "gasto" and es_anual:
        mensual = r["monto"] / 12.0
        monto_str = f"${r['monto']:,.2f}/año → ${mensual:,.2f}/mes"
    else:
        monto_str = f"${r['monto']:,.2f}"
    return f"#{r['id']} | [{r.get('categoria', 'sin_categoria')}] | {monto_str}"


def _parse_gasto_anual(text: str) -> bool | None:
    """True = gasto anual, False = mensual, None = respuesta no reconocida."""
    t = text.strip().lower()
    if is_null(t) or t in ("no", "n", "false", "f", "0", "mensual"):
        return False
    if t in ("si", "sí", "s", "yes", "y", "true", "1", "anual", "año", "ano"):
        return True
    return None


async def gasto_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Monto?")
    return GASTO_PRESUPUESTO_MONTO


async def gasto_presupuesto_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_cantidad(update.message.text)
    if monto is None or monto <= 0:
        await update.message.reply_text("Monto inválido. Escribe un número mayor a 0.")
        return GASTO_PRESUPUESTO_MONTO
    context.user_data["pres_gasto_monto"] = monto
    await update.message.reply_text(
        "¿El monto anterior es un total anual (no mensual)?\n"
        "• si — en totales se usará ese monto ÷ 12 como gasto mensual\n"
        "• no o null — el monto ya es mensual"
    )
    return GASTO_PRESUPUESTO_ANUAL


async def gasto_presupuesto_anual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parsed = _parse_gasto_anual(update.message.text)
    if parsed is None:
        await update.message.reply_text(
            "Responde si, no o null (mensual). Ejemplos: si, no, anual, mensual."
        )
        return GASTO_PRESUPUESTO_ANUAL
    context.user_data["pres_gasto_es_anual"] = parsed
    user_id = update.effective_user.id
    cats = listar_categorias_para_movimiento(user_id, "gasto")
    if not cats:
        await update.message.reply_text(
            "No tienes categorías para gastos. Usa /agregar_categoria (gasto o ambos) y vuelve a /gasto_presupuesto."
        )
        return END
    await update.message.reply_text(
        texto_elegir_categoria(cats),
        reply_markup=keyboard_categorias(cats, "pg"),
    )
    return GASTO_PRESUPUESTO_CATEGORIA


async def gasto_presupuesto_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _PRES_GASTO_CAT_CB.match(query.data or "")
    if not m:
        await query.answer()
        return GASTO_PRESUPUESTO_CATEGORIA
    cat_id = int(m.group(1))
    user_id = update.effective_user.id
    row = obtener_categoria_usuario_por_id(user_id, cat_id)
    if not row or not categoria_permitida_para_movimiento(user_id, row["nombre"], "gasto"):
        await query.answer("Categoría no válida.", show_alert=True)
        return GASTO_PRESUPUESTO_CATEGORIA
    await query.answer()
    monto = context.user_data["pres_gasto_monto"]
    es_anual = bool(context.user_data.get("pres_gasto_es_anual", False))
    _, mensaje = agregar_presupuesto_registro(
        user_id, "gasto", monto, row["nombre"], es_anual=es_anual
    )
    await query.edit_message_text(mensaje)
    return END


async def gasto_presupuesto_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    user_id = update.effective_user.id
    if not categoria_permitida_para_movimiento(user_id, cat, "gasto"):
        await update.message.reply_text(
            "Categoría no reconocida. Usa /mis_categorias o los botones."
        )
        return GASTO_PRESUPUESTO_CATEGORIA
    monto = context.user_data["pres_gasto_monto"]
    es_anual = bool(context.user_data.get("pres_gasto_es_anual", False))
    _, mensaje = agregar_presupuesto_registro(
        user_id, "gasto", monto, cat, es_anual=es_anual
    )
    await update.message.reply_text(mensaje)
    return END


async def ingreso_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Monto?")
    return INGRESO_PRESUPUESTO_MONTO


async def ingreso_presupuesto_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_cantidad(update.message.text)
    if monto is None or monto <= 0:
        await update.message.reply_text("Monto inválido. Escribe un número mayor a 0.")
        return INGRESO_PRESUPUESTO_MONTO
    context.user_data["pres_ing_monto"] = monto
    user_id = update.effective_user.id
    cats = listar_categorias_para_movimiento(user_id, "ingreso")
    if not cats:
        await update.message.reply_text(
            "No tienes categorías para ingresos. Usa /agregar_categoria (ingreso o ambos) y vuelve a /ingreso_presupuesto."
        )
        return END
    await update.message.reply_text(
        texto_elegir_categoria(cats),
        reply_markup=keyboard_categorias(cats, "pi"),
    )
    return INGRESO_PRESUPUESTO_CATEGORIA


async def ingreso_presupuesto_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    m = _PRES_INGRESO_CAT_CB.match(query.data or "")
    if not m:
        await query.answer()
        return INGRESO_PRESUPUESTO_CATEGORIA
    cat_id = int(m.group(1))
    user_id = update.effective_user.id
    row = obtener_categoria_usuario_por_id(user_id, cat_id)
    if not row or not categoria_permitida_para_movimiento(user_id, row["nombre"], "ingreso"):
        await query.answer("Categoría no válida.", show_alert=True)
        return INGRESO_PRESUPUESTO_CATEGORIA
    await query.answer()
    monto = context.user_data["pres_ing_monto"]
    _, mensaje = agregar_presupuesto_registro(user_id, "ingreso", monto, row["nombre"])
    await query.edit_message_text(mensaje)
    return END


async def ingreso_presupuesto_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    user_id = update.effective_user.id
    if not categoria_permitida_para_movimiento(user_id, cat, "ingreso"):
        await update.message.reply_text(
            "Categoría no reconocida. Usa /mis_categorias o los botones."
        )
        return INGRESO_PRESUPUESTO_CATEGORIA
    monto = context.user_data["pres_ing_monto"]
    _, mensaje = agregar_presupuesto_registro(user_id, "ingreso", monto, cat)
    await update.message.reply_text(mensaje)
    return END


async def editar_registro_presupuesto_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "¿ID del registro? (usa /resumen_presupuesto para ver los IDs)"
    )
    return EDITAR_PRESUPUESTO_ID


async def editar_presupuesto_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID inválido. Escribe un número.")
        return EDITAR_PRESUPUESTO_ID
    context.user_data["pres_edit_id"] = rid
    await update.message.reply_text(
        "¿Nuevo monto? (o null para no cambiar). "
        "Si la línea es gasto anual, escribe el total anual."
    )
    return EDITAR_PRESUPUESTO_MONTO


async def editar_presupuesto_monto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if is_null(text):
        context.user_data["pres_edit_monto"] = None
    else:
        monto = parse_cantidad(text)
        if monto is not None and monto > 0:
            context.user_data["pres_edit_monto"] = monto
        else:
            context.user_data["pres_edit_monto"] = None
    await update.message.reply_text(
        "¿Nueva categoría? (o null para no cambiar). Debe ser una de /mis_categorias según el tipo del registro."
    )
    return EDITAR_PRESUPUESTO_CATEGORIA


async def editar_presupuesto_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    monto = context.user_data.get("pres_edit_monto")
    categoria = None if is_null(text) else text
    if monto is None and categoria is None:
        await update.message.reply_text(
            "Debes cambiar al menos monto o categoría. Usa /editar_registro_presupuesto para reintentar."
        )
        return END
    user_id = update.effective_user.id
    rid = context.user_data["pres_edit_id"]
    _, mensaje = editar_presupuesto_registro(user_id, rid, monto=monto, categoria=categoria)
    await update.message.reply_text(mensaje)
    return END


async def cmd_resumen_presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    registros = listar_presupuesto(user_id)
    t = totales_presupuesto(user_id)
    lineas = ["📒 Tu presupuesto (planificado)\n"]
    if not registros:
        lineas.append("Aún no hay líneas. Usa /gasto_presupuesto o /ingreso_presupuesto.")
    else:
        gastos = [r for r in registros if r["tipo"] == "gasto"]
        ingresos_list = [r for r in registros if r["tipo"] == "ingreso"]
        LIMITE = 30

        lineas.append("📤 Gastos")
        if not gastos:
            lineas.append("  (ninguno)")
        else:
            for r in gastos[:LIMITE]:
                lineas.append(_formatear_linea_presupuesto(r))
            if len(gastos) > LIMITE:
                lineas.append(f"  ... y {len(gastos) - LIMITE} más.")

        lineas.append("")
        lineas.append("─────────────────────")
        lineas.append("")

        lineas.append("📥 Ingresos")
        if not ingresos_list:
            lineas.append("  (ninguno)")
        else:
            for r in ingresos_list[:LIMITE]:
                lineas.append(_formatear_linea_presupuesto(r))
            if len(ingresos_list) > LIMITE:
                lineas.append(f"  ... y {len(ingresos_list) - LIMITE} más.")

        lineas.append("")
    lineas.append(f"Total gastos planificados (mensual): ${t['total_gasto']:,.2f}")
    lineas.append(f"Total ingresos planificados: ${t['total_ingreso']:,.2f}")
    lineas.append(f"Balance (ingresos − gastos): ${t['balance']:,.2f}")
    lineas.append("(Los gastos anuales entran en el total como monto ÷ 12.)")
    if registros:
        lineas.append("\nEdita con /editar_registro_presupuesto usando el #id.")
    await update.message.reply_text("\n".join(lineas))
