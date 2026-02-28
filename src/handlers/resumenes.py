"""Flujos resumen_categorias, resumen_mes."""
from telegram import Update
from telegram.ext import ContextTypes

from src.config import (
    RESUMEN_CAT_MES,
    RESUMEN_CAT_ANO,
    RESUMEN_MES_ANO,
    RESUMEN_MES_MES,
    MESES,
    END,
)
from src.database import obtener_resumen_por_categoria, obtener_resumen_por_mes
from src.utils import is_null


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


async def resumen_mes_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("¿Año? (ej: 2025, o null para últimos 12 meses)")
    return RESUMEN_MES_ANO


async def resumen_mes_ano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if is_null(text):
        context.user_data["resumen_mes_ano"] = None
        context.user_data["resumen_mes_mes"] = None
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


async def _enviar_resumen_mes(
    update: Update, registros: list, ano: int | None, mes: int | None
) -> None:
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
