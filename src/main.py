"""Punto de entrada del bot."""
import os
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler

from src.database import init_db
from src.handlers import commands, conv_handler

load_dotenv()


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

    app.add_handler(CommandHandler("start", commands.cmd_start))
    app.add_handler(CommandHandler("help", commands.cmd_help))
    app.add_handler(CommandHandler("cuentas", commands.cmd_cuentas))
    app.add_handler(CommandHandler("resumen", commands.cmd_resumen))
    app.add_handler(conv_handler)

    print("Bot iniciado. Presiona Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
