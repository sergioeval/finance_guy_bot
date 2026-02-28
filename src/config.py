"""Constantes y configuración del bot."""
from telegram.ext import ConversationHandler, filters

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

# Filtro para mensajes de texto que no son comandos
TEXT = filters.TEXT & ~filters.COMMAND

MESES = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
