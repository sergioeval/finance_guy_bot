#!/usr/bin/env python3
"""
Migración: convierte nombres de cuentas y categorías existentes a minúsculas.

Ejecutar desde la raíz del proyecto:
    python scripts/migrate_lowercase.py

Si hay cuentas duplicadas por mayúsculas (ej: "Banco" y "banco"), las fusiona
manteniendo una sola cuenta y actualizando todas las referencias.
"""
import sqlite3
import sys
from pathlib import Path

# Ruta al DB
DB_PATH = Path(__file__).resolve().parent.parent / "finanzas.db"


def migrate():
    if not DB_PATH.exists():
        print(f"Error: No se encontró la base de datos en {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 1. Categorías en transacciones
        cur = conn.execute(
            "UPDATE transacciones SET categoria = LOWER(COALESCE(categoria, 'sin_categoria'))"
        )
        cat_count = cur.rowcount
        print(f"✓ Categorías actualizadas: {cat_count} transacciones")

        # 2. Cuentas: detectar duplicados (mismo user_id, mismo nombre en minúsculas)
        cur = conn.execute("""
            SELECT user_id, LOWER(nombre) AS nombre_lower,
                   GROUP_CONCAT(id) AS ids, GROUP_CONCAT(nombre) AS nombres
            FROM cuentas
            GROUP BY user_id, nombre_lower
            HAVING COUNT(*) > 1
        """)
        duplicados = cur.fetchall()

        for row in duplicados:
            user_id = row["user_id"]
            nombre_lower = row["nombre_lower"]
            ids = [int(x) for x in row["ids"].split(",")]
            # Mantener el de menor ID, fusionar el resto
            id_principal = min(ids)
            ids_eliminar = [i for i in ids if i != id_principal]

            for id_dup in ids_eliminar:
                # Sumar saldo de la cuenta duplicada a la principal
                saldo_dup = conn.execute(
                    "SELECT saldo FROM cuentas WHERE id = ?", (id_dup,)
                ).fetchone()[0]
                conn.execute(
                    "UPDATE cuentas SET saldo = saldo + ? WHERE id = ?",
                    (saldo_dup, id_principal),
                )
                # Actualizar transacciones que apuntan a la cuenta duplicada
                conn.execute(
                    "UPDATE transacciones SET cuenta_id = ? WHERE cuenta_id = ?",
                    (id_principal, id_dup),
                )
                conn.execute(
                    "UPDATE transacciones SET cuenta_relacionada_id = ? WHERE cuenta_relacionada_id = ?",
                    (id_principal, id_dup),
                )
                conn.execute("DELETE FROM cuentas WHERE id = ?", (id_dup,))
                print(f"  Fusionada cuenta duplicada id={id_dup} → id={id_principal} (user={user_id})")

            # Asegurar que la principal tenga nombre en minúsculas
            conn.execute(
                "UPDATE cuentas SET nombre = ? WHERE id = ?",
                (nombre_lower, id_principal),
            )

        # 3. Cuentas sin duplicados: solo pasar a minúsculas
        cur = conn.execute("""
            UPDATE cuentas SET nombre = LOWER(nombre) WHERE nombre != LOWER(nombre)
        """)
        cuentas_count = cur.rowcount
        print(f"✓ Nombres de cuenta actualizados: {cuentas_count} cuentas")

        conn.commit()
        print("Migración completada correctamente.")

    except Exception as e:
        conn.rollback()
        print(f"Error durante la migración: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
