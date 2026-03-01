"""
Módulo de base de datos SQLite para el bot de finanzas personales.
"""
import sqlite3
import uuid
from pathlib import Path
from contextlib import contextmanager

# Ruta al DB: desde src/database/db.py subimos 2 niveles a la raíz del proyecto
DB_PATH = Path(__file__).resolve().parent.parent.parent / "finanzas.db"


@contextmanager
def get_connection():
    """Context manager para conexiones a la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa las tablas de la base de datos."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cuentas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('credito', 'debito')),
                saldo REAL NOT NULL DEFAULT 0,
                creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, nombre)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cuenta_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('gasto', 'ingreso', 'transferencia_entrada', 'transferencia_salida')),
                monto REAL NOT NULL,
                cuenta_relacionada_id INTEGER,
                transfer_id TEXT,
                creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cuenta_id) REFERENCES cuentas(id),
                FOREIGN KEY (cuenta_relacionada_id) REFERENCES cuentas(id)
            )
        """)
        try:
            conn.execute("ALTER TABLE transacciones ADD COLUMN transfer_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE transacciones ADD COLUMN categoria TEXT DEFAULT 'sin_categoria'")
        except sqlite3.OperationalError:
            pass


def crear_cuenta(user_id: int, nombre: str, tipo: str) -> tuple[bool, str]:
    """Crea una nueva cuenta para el usuario. Retorna (éxito, mensaje)."""
    tipo = tipo.lower().strip()
    if tipo not in ("credito", "debito"):
        return False, "El tipo debe ser 'credito' o 'debito'."

    nombre = nombre.strip().lower()
    if not nombre:
        return False, "El nombre de la cuenta no puede estar vacío."

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO cuentas (user_id, nombre, tipo) VALUES (?, ?, ?)",
                (user_id, nombre, tipo)
            )
        return True, f"Cuenta '{nombre}' ({tipo}) creada correctamente."
    except sqlite3.IntegrityError:
        return False, f"Ya existe una cuenta con el nombre '{nombre}'."


def listar_cuentas(user_id: int) -> list[dict]:
    """Lista todas las cuentas del usuario."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nombre, tipo, saldo FROM cuentas WHERE user_id = ? ORDER BY nombre",
            (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def obtener_cuenta_por_nombre(user_id: int, nombre: str) -> dict | None:
    """Obtiene una cuenta por nombre (case-insensitive)."""
    nombre = nombre.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, nombre, tipo, saldo FROM cuentas WHERE user_id = ? AND LOWER(nombre) = LOWER(?)",
            (user_id, nombre)
        ).fetchone()
    return dict(row) if row else None


def registrar_gasto(user_id: int, nombre_cuenta: str, monto: float, categoria: str = "sin_categoria") -> tuple[bool, str]:
    """Registra un gasto en la cuenta especificada."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return False, f"No se encontró la cuenta '{nombre_cuenta}'."

    if monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = ((categoria or "sin_categoria").strip() or "sin_categoria").lower()

    with get_connection() as conn:
        if cuenta["tipo"] == "debito":
            nuevo_saldo = cuenta["saldo"] - monto
        else:
            nuevo_saldo = cuenta["saldo"] - monto

        conn.execute(
            "INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, categoria) VALUES (?, ?, 'gasto', ?, ?)",
            (user_id, cuenta["id"], monto, cat)
        )
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))

    return True, f"Gasto de ${monto:,.2f} registrado en '{cuenta['nombre']}' [{cat}]."


def registrar_ingreso(user_id: int, nombre_cuenta: str, monto: float, categoria: str = "sin_categoria") -> tuple[bool, str]:
    """Registra un ingreso en la cuenta especificada."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return False, f"No se encontró la cuenta '{nombre_cuenta}'."

    if monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = ((categoria or "sin_categoria").strip() or "sin_categoria").lower()
    nuevo_saldo = cuenta["saldo"] + monto

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, categoria) VALUES (?, ?, 'ingreso', ?, ?)",
            (user_id, cuenta["id"], monto, cat)
        )
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))

    return True, f"Ingreso de ${monto:,.2f} registrado en '{cuenta['nombre']}' [{cat}]."


def transferir(user_id: int, cuenta_origen: str, cuenta_destino: str, monto: float) -> tuple[bool, str]:
    """Transfiere dinero de una cuenta a otra."""
    if cuenta_origen.lower() == cuenta_destino.lower():
        return False, "La cuenta origen y destino no pueden ser la misma."

    origen = obtener_cuenta_por_nombre(user_id, cuenta_origen)
    destino = obtener_cuenta_por_nombre(user_id, cuenta_destino)

    if not origen:
        return False, f"No se encontró la cuenta origen '{cuenta_origen}'."
    if not destino:
        return False, f"No se encontró la cuenta destino '{cuenta_destino}'."

    if monto <= 0:
        return False, "El monto debe ser mayor a 0."

    if origen["tipo"] == "debito" and origen["saldo"] < monto:
        return False, f"Saldo insuficiente en '{origen['nombre']}'. Saldo actual: ${origen['saldo']:,.2f}"

    transfer_id = str(uuid.uuid4())
    with get_connection() as conn:
        saldo_origen = origen["saldo"] - monto
        saldo_destino = destino["saldo"] + monto

        conn.execute(
            """INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, cuenta_relacionada_id, transfer_id)
               VALUES (?, ?, 'transferencia_salida', ?, ?, ?)""",
            (user_id, origen["id"], monto, destino["id"], transfer_id)
        )
        conn.execute(
            """INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, cuenta_relacionada_id, transfer_id)
               VALUES (?, ?, 'transferencia_entrada', ?, ?, ?)""",
            (user_id, destino["id"], monto, origen["id"], transfer_id)
        )
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (saldo_origen, origen["id"]))
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (saldo_destino, destino["id"]))

    return True, f"Transferencia de ${monto:,.2f} de '{origen['nombre']}' a '{destino['nombre']}' completada."


def obtener_resumen(user_id: int) -> dict:
    """Obtiene el resumen total de las cuentas del usuario."""
    cuentas = listar_cuentas(user_id)
    total_debito = sum(c["saldo"] for c in cuentas if c["tipo"] == "debito")
    total_credito = sum(c["saldo"] for c in cuentas if c["tipo"] == "credito")
    return {
        "cuentas": cuentas,
        "total_debito": total_debito,
        "total_credito": total_credito,
        "patrimonio_neto": total_debito + total_credito,
    }


def obtener_resumen_por_categoria(
    user_id: int, ano: int | None = None, mes: int | None = None
) -> dict:
    """Resumen de gastos e ingresos agrupados por categoría."""
    with get_connection() as conn:
        filtro = "AND user_id = ?"
        params: list = [user_id]
        if ano is not None:
            filtro += " AND CAST(strftime('%Y', creada_en) AS INTEGER) = ?"
            params.append(ano)
        if mes is not None:
            filtro += " AND CAST(strftime('%m', creada_en) AS INTEGER) = ?"
            params.append(mes)

        gastos = conn.execute(f"""
            SELECT COALESCE(categoria, 'sin_categoria') AS categoria, SUM(monto) AS total
            FROM transacciones WHERE tipo = 'gasto' {filtro}
            GROUP BY COALESCE(categoria, 'sin_categoria') ORDER BY total DESC
        """, params).fetchall()

        ingresos = conn.execute(f"""
            SELECT COALESCE(categoria, 'sin_categoria') AS categoria, SUM(monto) AS total
            FROM transacciones WHERE tipo = 'ingreso' {filtro}
            GROUP BY COALESCE(categoria, 'sin_categoria') ORDER BY total DESC
        """, params).fetchall()

        total_g = conn.execute(f"""
            SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo = 'gasto' {filtro}
        """, params).fetchone()[0]

        total_i = conn.execute(f"""
            SELECT COALESCE(SUM(monto), 0) FROM transacciones WHERE tipo = 'ingreso' {filtro}
        """, params).fetchone()[0]

    return {
        "gastos": [dict(r) for r in gastos],
        "ingresos": [dict(r) for r in ingresos],
        "total_gastos": total_g,
        "total_ingresos": total_i,
        "ano": ano,
        "mes": mes,
    }


def obtener_resumen_por_mes(
    user_id: int, ano: int | None = None, mes: int | None = None, limite: int = 12
) -> list[dict]:
    """Resumen mensual: gastos, ingresos y balance por mes."""
    with get_connection() as conn:
        if ano is not None and mes is not None:
            rows = conn.execute("""
                SELECT CAST(strftime('%Y', creada_en) AS INTEGER) AS ano,
                       CAST(strftime('%m', creada_en) AS INTEGER) AS mes,
                       SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END) AS gastos,
                       SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END) AS ingresos
                FROM transacciones
                WHERE user_id = ? AND tipo IN ('gasto', 'ingreso')
                  AND CAST(strftime('%Y', creada_en) AS INTEGER) = ?
                  AND CAST(strftime('%m', creada_en) AS INTEGER) = ?
                GROUP BY ano, mes
            """, (user_id, ano, mes)).fetchall()
        elif ano is not None:
            rows = conn.execute("""
                SELECT CAST(strftime('%Y', creada_en) AS INTEGER) AS ano,
                       CAST(strftime('%m', creada_en) AS INTEGER) AS mes,
                       SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END) AS gastos,
                       SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END) AS ingresos
                FROM transacciones
                WHERE user_id = ? AND tipo IN ('gasto', 'ingreso')
                  AND CAST(strftime('%Y', creada_en) AS INTEGER) = ?
                GROUP BY ano, mes ORDER BY mes ASC
            """, (user_id, ano)).fetchall()
        else:
            rows = conn.execute("""
                SELECT CAST(strftime('%Y', creada_en) AS INTEGER) AS ano,
                       CAST(strftime('%m', creada_en) AS INTEGER) AS mes,
                       SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END) AS gastos,
                       SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END) AS ingresos
                FROM transacciones
                WHERE user_id = ? AND tipo IN ('gasto', 'ingreso')
                GROUP BY ano, mes ORDER BY ano DESC, mes DESC LIMIT ?
            """, (user_id, limite)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["balance"] = (d["ingresos"] or 0) - (d["gastos"] or 0)
        result.append(d)
    return result


def listar_registros(user_id: int, nombre_cuenta: str) -> tuple[list[dict] | None, str]:
    """Lista las transacciones de una cuenta. Retorna (lista, mensaje) o (None, mensaje_error)."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return None, f"No se encontró la cuenta '{nombre_cuenta}'."

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT t.id, t.tipo, t.monto, t.creada_en, t.transfer_id, t.categoria,
                   c_rel.nombre AS cuenta_relacionada
            FROM transacciones t
            LEFT JOIN cuentas c_rel ON t.cuenta_relacionada_id = c_rel.id
            WHERE t.user_id = ? AND t.cuenta_id = ?
            ORDER BY t.creada_en DESC
        """, (user_id, cuenta["id"])).fetchall()

    registros = []
    for row in rows:
        r = dict(row)
        r["cuenta_relacionada"] = r.get("cuenta_relacionada") or ""
        r["categoria"] = r.get("categoria") or "sin_categoria"
        registros.append(r)
    return registros, cuenta["nombre"]


def obtener_transaccion(user_id: int, transaccion_id: int) -> dict | None:
    """Obtiene una transacción por ID si pertenece al usuario."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transacciones WHERE id = ? AND user_id = ?",
            (transaccion_id, user_id)
        ).fetchone()
    return dict(row) if row else None


def editar_registro(
    user_id: int,
    transaccion_id: int,
    monto: float | None = None,
    categoria: str | None = None,
) -> tuple[bool, str]:
    """Edita un gasto o ingreso. Retorna (éxito, mensaje)."""
    trans = obtener_transaccion(user_id, transaccion_id)
    if not trans:
        return False, "No se encontró el registro o no te pertenece."

    tipo = trans["tipo"]
    if tipo not in ("gasto", "ingreso"):
        return False, "Solo se pueden editar gastos e ingresos. Las transferencias no son editables."

    if monto is None and categoria is None:
        return False, "Debes indicar al menos monto o categoría para editar."

    if monto is not None and monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = None
    if categoria is not None:
        cat = (categoria.strip() or "sin_categoria").lower()

    with get_connection() as conn:
        cuenta = conn.execute(
            "SELECT id, nombre, saldo, tipo FROM cuentas WHERE id = ?",
            (trans["cuenta_id"],)
        ).fetchone()
        if not cuenta:
            return False, "Error: cuenta no encontrada."
        cuenta = dict(cuenta)
        saldo_actual = cuenta["saldo"]
        monto_viejo = trans["monto"]

        if monto is not None:
            if tipo == "gasto":
                nuevo_saldo = saldo_actual + monto_viejo - monto
            else:
                nuevo_saldo = saldo_actual - monto_viejo + monto

            conn.execute("UPDATE transacciones SET monto = ? WHERE id = ?", (monto, transaccion_id))
            conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))

        if cat is not None:
            conn.execute("UPDATE transacciones SET categoria = ? WHERE id = ?", (cat, transaccion_id))

    cambios = []
    if monto is not None:
        cambios.append(f"monto ${monto:,.2f}")
    if cat is not None:
        cambios.append(f"categoría '{cat}'")
    return True, f"Registro #{transaccion_id} actualizado: {', '.join(cambios)}."


def eliminar_registro(user_id: int, transaccion_id: int) -> tuple[bool, str]:
    """Elimina una transacción y revierte el saldo. Retorna (éxito, mensaje)."""
    trans = obtener_transaccion(user_id, transaccion_id)
    if not trans:
        return False, "No se encontró el registro o no te pertenece."

    with get_connection() as conn:
        cuenta = conn.execute(
            "SELECT id, nombre, saldo, tipo FROM cuentas WHERE id = ?",
            (trans["cuenta_id"],)
        ).fetchone()
        if not cuenta:
            return False, "Error: cuenta no encontrada."
        cuenta = dict(cuenta)

        tipo = trans["tipo"]
        monto = trans["monto"]

        if tipo == "gasto":
            nuevo_saldo = cuenta["saldo"] + monto
            conn.execute("DELETE FROM transacciones WHERE id = ?", (transaccion_id,))
            conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))
            return True, f"Gasto de ${monto:,.2f} eliminado de '{cuenta['nombre']}'."

        elif tipo == "ingreso":
            nuevo_saldo = cuenta["saldo"] - monto
            conn.execute("DELETE FROM transacciones WHERE id = ?", (transaccion_id,))
            conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))
            return True, f"Ingreso de ${monto:,.2f} eliminado de '{cuenta['nombre']}'."

        elif tipo in ("transferencia_salida", "transferencia_entrada"):
            if trans.get("transfer_id"):
                par = conn.execute(
                    "SELECT * FROM transacciones WHERE transfer_id = ? AND id != ?",
                    (trans["transfer_id"], transaccion_id)
                ).fetchone()
            else:
                par = conn.execute("""
                    SELECT * FROM transacciones
                    WHERE user_id = ? AND monto = ? AND id != ?
                    AND (
                        (tipo = 'transferencia_entrada' AND cuenta_id = ? AND cuenta_relacionada_id = ?)
                        OR (tipo = 'transferencia_salida' AND cuenta_id = ? AND cuenta_relacionada_id = ?)
                    )
                """, (user_id, monto, transaccion_id,
                      trans["cuenta_relacionada_id"], trans["cuenta_id"],
                      trans["cuenta_relacionada_id"], trans["cuenta_id"])).fetchone()

            if not par:
                return False, "No se encontró el par de la transferencia."

            par = dict(par)
            cuenta_origen_id = trans["cuenta_id"] if tipo == "transferencia_salida" else trans["cuenta_relacionada_id"]
            cuenta_destino_id = trans["cuenta_relacionada_id"] if tipo == "transferencia_salida" else trans["cuenta_id"]

            saldo_origen = conn.execute("SELECT saldo FROM cuentas WHERE id = ?", (cuenta_origen_id,)).fetchone()[0]
            saldo_destino = conn.execute("SELECT saldo FROM cuentas WHERE id = ?", (cuenta_destino_id,)).fetchone()[0]

            nuevo_saldo_origen = saldo_origen + monto
            nuevo_saldo_destino = saldo_destino - monto

            conn.execute("DELETE FROM transacciones WHERE id IN (?, ?)", (transaccion_id, par["id"]))
            conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo_origen, cuenta_origen_id))
            conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo_destino, cuenta_destino_id))
            return True, f"Transferencia de ${monto:,.2f} eliminada correctamente."

    return False, "Error al eliminar."
