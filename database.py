"""
Re-export del módulo de base de datos (compatibilidad).
"""
from src.database import (
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
