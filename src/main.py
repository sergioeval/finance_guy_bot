"""Punto de entrada del bot."""
import os
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler

from src.database import init_db, obtener_ids_usuarios_con_cuentas
from src.handlers import commands, conv_handler

load_dotenv()


async def send_resumen_diario(context) -> None:
    """Envía el resumen diario a todos los usuarios con cuentas."""
    for user_id in obtener_ids_usuarios_con_cuentas():
        texto = commands.formatear_resumen(user_id)
        if texto:
            try:
                await context.bot.send_message(chat_id=user_id, text=texto)
            except Exception:
                pass  # Usuario puede haber bloqueado el bot o no existir


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

    # Resumen diario automático a las 10:00 (zona configurable vía RESUMEN_DIARIO_TZ)
    tz = ZoneInfo(os.getenv("RESUMEN_DIARIO_TZ", "Europe/Madrid"))
    application.job_queue.run_daily(
        send_resumen_diario,
        time=time(10, 0, 0, tzinfo=tz),
        name="resumen_diario",
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN no encontrado en .env")
        return

    init_db()

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", commands.cmd_start))
    app.add_handler(CommandHandler("help", commands.cmd_help))
    app.add_handler(CommandHandler("cuentas", commands.cmd_cuentas))
    app.add_handler(CommandHandler("resumen", commands.cmd_resumen))
    app.add_handler(conv_handler)

    print("Bot iniciado. Presiona Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
