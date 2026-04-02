"""Presupuestos nombrados por usuario (varios por persona; movimientos por presupuesto)."""
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
    PRES_GASTO_NOMBRE,
    PRES_INGRESO_NOMBRE,
    RESUMEN_PRES_NOMBRE,
    PRES_ELIMINAR_ID,
    CLONAR_PRES_ORIGEN,
    CLONAR_PRES_NUEVO_NOMBRE,
    END,
)
from src.database import (
    agregar_presupuesto_registro,
    clonar_presupuesto,
    categoria_permitida_para_movimiento,
    editar_presupuesto_registro,
    eliminar_presupuesto_registro,
    listar_categorias_para_movimiento,
    listar_presupuesto,
    listar_presupuestos,
    obtener_categoria_usuario_por_id,
    obtener_presupuesto_por_id,
    obtener_presupuesto_por_nombre,
    resolver_presupuesto_por_nombre,
    totales_presupuesto,
)
from src.handlers.categoria_inline import keyboard_categorias, texto_elegir_categoria
from src.utils import is_null, parse_cantidad

_PRES_GASTO_CAT_CB = re.compile(r"^pg:(\d+)$")
_PRES_INGRESO_CAT_CB = re.compile(r"^pi:(\d+)$")
_MAX_MSG = 3900


async def _reply_texto_largo(message, texto: str) -> None:
    t = texto.strip()
    if len(t) <= _MAX_MSG:
        await message.reply_text(t)
        return
    while len(t) > _MAX_MSG:
        corte = t.rfind("\n", 0, _MAX_MSG)
        if corte < _MAX_MSG // 2:
            corte = _MAX_MSG
        await message.reply_text(t[:corte].strip())
        t = t[corte:].lstrip()
    if t:
        await message.reply_text(t)


def _formatear_linea_presupuesto(r: dict) -> str:
    es_anual = bool(r.get("es_anual", 0))
    if r["tipo"] == "gasto" and es_anual:
        mensual = r["monto"] / 12.0
        monto_str = f"${r['monto']:,.2f}/año → ${mensual:,.2f}/mes"
    else:
        monto_str = f"${r['monto']:,.2f}"
    return f"#{r['id']} | [{r.get('categoria', 'sin_categoria')}] | {monto_str}"


def _lineas_detalle_presupuesto(user_id: int, presupuesto_id: int, nombre: str) -> list[str]:
    registros = listar_presupuesto(user_id, presupuesto_id)
    t = totales_presupuesto(user_id, presupuesto_id)
    lineas = [f"📒 Presupuesto «{nombre}»\n"]
    if not registros:
        lineas.append("Sin líneas aún. Usa /gasto_presupuesto o /ingreso_presupuesto.")
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
        lineas.append("\nEdita con /editar_registro_presupuesto o borra con /eliminar_registro_presupuesto (#id).")
    return lineas


def _parse_gasto_anual(text: str) -> bool | None:
    """True = gasto anual, False = mensual, None = respuesta no reconocida."""
    t = text.strip().lower()
    if is_null(t) or t in ("no", "n", "false", "f", "0", "mensual"):
        return False
    if t in ("si", "sí", "s", "yes", "y", "true", "1", "anual", "año", "ano"):
        return True
    return None


async def gasto_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Nombre del presupuesto (si no existe, se crea ahora):\n"
        "Usa /presupuestos para ver los que ya tienes."
    )
    return PRES_GASTO_NOMBRE


async def gasto_presupuesto_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    pid, err = resolver_presupuesto_por_nombre(user_id, update.message.text)
    if err:
        await update.message.reply_text(err)
        return PRES_GASTO_NOMBRE
    context.user_data["presupuesto_id"] = pid
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
    pres_id = context.user_data.get("presupuesto_id")
    if pres_id is None:
        await query.edit_message_text("Sesión caducada. Usa /gasto_presupuesto de nuevo.")
        return END
    monto = context.user_data["pres_gasto_monto"]
    es_anual = bool(context.user_data.get("pres_gasto_es_anual", False))
    _, mensaje = agregar_presupuesto_registro(
        user_id, pres_id, "gasto", monto, row["nombre"], es_anual=es_anual
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
    pres_id = context.user_data.get("presupuesto_id")
    if pres_id is None:
        await update.message.reply_text("Sesión caducada. Usa /gasto_presupuesto de nuevo.")
        return END
    monto = context.user_data["pres_gasto_monto"]
    es_anual = bool(context.user_data.get("pres_gasto_es_anual", False))
    _, mensaje = agregar_presupuesto_registro(
        user_id, pres_id, "gasto", monto, cat, es_anual=es_anual
    )
    await update.message.reply_text(mensaje)
    return END


async def ingreso_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Nombre del presupuesto (si no existe, se crea ahora):\n"
        "Usa /presupuestos para ver los que ya tienes."
    )
    return PRES_INGRESO_NOMBRE


async def ingreso_presupuesto_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    pid, err = resolver_presupuesto_por_nombre(user_id, update.message.text)
    if err:
        await update.message.reply_text(err)
        return PRES_INGRESO_NOMBRE
    context.user_data["presupuesto_id"] = pid
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
    pres_id = context.user_data.get("presupuesto_id")
    if pres_id is None:
        await query.edit_message_text("Sesión caducada. Usa /ingreso_presupuesto de nuevo.")
        return END
    monto = context.user_data["pres_ing_monto"]
    _, mensaje = agregar_presupuesto_registro(user_id, pres_id, "ingreso", monto, row["nombre"])
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
    pres_id = context.user_data.get("presupuesto_id")
    if pres_id is None:
        await update.message.reply_text("Sesión caducada. Usa /ingreso_presupuesto de nuevo.")
        return END
    monto = context.user_data["pres_ing_monto"]
    _, mensaje = agregar_presupuesto_registro(user_id, pres_id, "ingreso", monto, cat)
    await update.message.reply_text(mensaje)
    return END


async def editar_registro_presupuesto_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "¿ID de la línea? (el # es único entre todos tus presupuestos; ver /resumen_presupuesto)."
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


async def resumen_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Nombre del presupuesto a consultar, o escribe todos para listar todos.\n"
        "/presupuestos muestra nombres e IDs."
    )
    return RESUMEN_PRES_NOMBRE


async def resumen_presupuesto_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    user_id = update.effective_user.id
    if raw.lower() == "todos":
        pres_list = listar_presupuestos(user_id)
        if not pres_list:
            await update.message.reply_text(
                "No tienes presupuestos. Indica un nombre en /gasto_presupuesto para crear el primero."
            )
            return END
        bloques: list[str] = []
        for p in pres_list:
            bloques.append("\n".join(_lineas_detalle_presupuesto(user_id, p["id"], p["nombre"])))
        await _reply_texto_largo(update.message, "\n\n═══════════════\n\n".join(bloques))
        return END

    p = obtener_presupuesto_por_nombre(user_id, raw)
    if not p:
        await update.message.reply_text(
            f"No existe el presupuesto «{raw}». Revisa /presupuestos o el nombre exacto."
        )
        return RESUMEN_PRES_NOMBRE
    await _reply_texto_largo(
        update.message,
        "\n".join(_lineas_detalle_presupuesto(user_id, p["id"], p["nombre"])),
    )
    return END


async def eliminar_registro_presupuesto_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "¿ID de la línea a borrar? (# único; aparece en /resumen_presupuesto)."
    )
    return PRES_ELIMINAR_ID


async def eliminar_presupuesto_por_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID inválido. Escribe el número del registro.")
        return PRES_ELIMINAR_ID
    user_id = update.effective_user.id
    exito, mensaje = eliminar_presupuesto_registro(user_id, rid)
    await update.message.reply_text(mensaje)
    return END


async def clonar_presupuesto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "¿Qué presupuesto quieres copiar? Escribe su nombre o su #id (ver /presupuestos)."
    )
    return CLONAR_PRES_ORIGEN


async def clonar_presupuesto_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    orig = None
    if text.isdigit():
        orig = obtener_presupuesto_por_id(user_id, int(text))
    if orig is None:
        orig = obtener_presupuesto_por_nombre(user_id, text)
    if not orig:
        await update.message.reply_text(
            "No encontré ese presupuesto. Revisa /presupuestos (nombre o #id)."
        )
        return CLONAR_PRES_ORIGEN
    context.user_data["pres_clonar_origen_id"] = orig["id"]
    await update.message.reply_text(
        f"Origen: «{orig['nombre']}». Escribe el nombre del presupuesto nuevo "
        "(debe ser distinto al original y no coincidir con uno que ya tengas)."
    )
    return CLONAR_PRES_NUEVO_NOMBRE


async def clonar_presupuesto_nuevo_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_id = update.effective_user.id
    oid = context.user_data.get("pres_clonar_origen_id")
    if oid is None:
        await update.message.reply_text("Sesión caducada. Usa /clonar_presupuesto de nuevo.")
        return END
    _, mensaje = clonar_presupuesto(user_id, oid, update.message.text)
    await update.message.reply_text(mensaje)
    context.user_data.pop("pres_clonar_origen_id", None)
    return END


async def cmd_presupuestos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lst = listar_presupuestos(user_id)
    if not lst:
        await update.message.reply_text(
            "No tienes presupuestos. El primero se crea al usar /gasto_presupuesto o /ingreso_presupuesto "
            "e indicar un nombre nuevo."
        )
        return
    lineas = ["📋 Tus presupuestos:\n"]
    for p in lst:
        lineas.append(f"• «{p['nombre']}» (#{p['id']}) — {p['n_movimientos']} líneas")
    lineas.append("\n/resumen_presupuesto — detalle de uno o todos")
    lineas.append("/clonar_presupuesto — copiar uno con otro nombre")
    await update.message.reply_text("\n".join(lineas))
