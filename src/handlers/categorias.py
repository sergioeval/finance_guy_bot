"""Listar, crear y renombrar categorías del usuario."""
from telegram import Update
from telegram.ext import ContextTypes

from src.config import (
    CAT_AGREGAR_NOMBRE,
    CAT_AGREGAR_AMBITO,
    CAT_EDITAR_ID,
    CAT_EDITAR_NOMBRE,
    END,
)
from src.database import (
    agregar_categoria_usuario,
    listar_categorias_usuario,
    renombrar_categoria_usuario,
)


def texto_mis_categorias(user_id: int) -> str:
    cats = listar_categorias_usuario(user_id)
    if not cats:
        return (
            "📂 Aún no tienes categorías.\n\n"
            "Usa /agregar_categoria para crear la primera. "
            "Luego podrás usarlas en /gasto, /ingreso y presupuesto."
        )
    lineas = ["📂 Tus categorías (nombre [#id] · ámbito):\n"]
    for c in cats:
        lineas.append(f"• {c['nombre']} [#{c['id']}] · {c['ambito']}")
    lineas.append("\n/editar_mi_categoria — cambiar nombre (y actualiza movimientos con ese nombre)")
    return "\n".join(lineas)


async def cmd_mis_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(texto_mis_categorias(user_id))


def _parse_ambito(text: str) -> str | None:
    t = text.strip().lower()
    if t in ("gasto", "gastos", "g"):
        return "gasto"
    if t in ("ingreso", "ingresos", "i"):
        return "ingreso"
    if t in ("ambos", "ambas", "a", "todo", "todos"):
        return "ambos"
    return None


async def agregar_categoria_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Nombre de la categoría (una sola línea, sin comillas):\n\n"
        "Luego te preguntaré si aplica a gastos, ingresos o ambos."
    )
    return CAT_AGREGAR_NOMBRE


async def agregar_categoria_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = update.message.text.strip()
    if not nombre:
        await update.message.reply_text("El nombre no puede estar vacío.")
        return CAT_AGREGAR_NOMBRE
    context.user_data["cat_nuevo_nombre"] = nombre
    await update.message.reply_text(
        "¿Ámbito?\n"
        "• gasto — solo gastos y gastos de presupuesto\n"
        "• ingreso — solo ingresos e ingresos de presupuesto\n"
        "• ambos — gastos e ingresos"
    )
    return CAT_AGREGAR_AMBITO


async def agregar_categoria_ambito(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ambito = _parse_ambito(update.message.text)
    if ambito is None:
        await update.message.reply_text("Responde: gasto, ingreso o ambos.")
        return CAT_AGREGAR_AMBITO
    user_id = update.effective_user.id
    nombre = context.user_data.get("cat_nuevo_nombre", "")
    exito, mensaje = agregar_categoria_usuario(user_id, nombre, ambito)
    await update.message.reply_text(mensaje)
    context.user_data.pop("cat_nuevo_nombre", None)
    return END


async def editar_mi_categoria_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "ID de la categoría a renombrar (número, ver /mis_categorias):"
    )
    return CAT_EDITAR_ID


async def editar_mi_categoria_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        cid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID inválido. Escribe el número que aparece en /mis_categorias.")
        return CAT_EDITAR_ID
    context.user_data["cat_edit_id"] = cid
    await update.message.reply_text("Nuevo nombre para esa categoría:")
    return CAT_EDITAR_NOMBRE


async def editar_mi_categoria_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nuevo = update.message.text.strip()
    user_id = update.effective_user.id
    cid = context.user_data.get("cat_edit_id")
    if cid is None:
        await update.message.reply_text("Algo salió mal. Usa /edita_mi_categoria de nuevo.")
        return END
    exito, mensaje = renombrar_categoria_usuario(user_id, cid, nuevo)
    await update.message.reply_text(mensaje)
    context.user_data.pop("cat_edit_id", None)
    return END
