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
        _ensure_presupuesto_tabla(conn)
        _ensure_presupuesto_es_anual(conn)
        _ensure_presupuestos_y_relacion(conn)
        _ensure_categorias_usuario_tabla(conn)


def _ensure_categorias_usuario_tabla(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categorias_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            ambito TEXT NOT NULL CHECK(ambito IN ('gasto', 'ingreso', 'ambos')),
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, nombre)
        )
    """)


def _normalizar_nombre_categoria(nombre: str) -> str:
    return (nombre or "").strip().lower()


def listar_categorias_usuario(user_id: int) -> list[dict]:
    """Todas las categorías definidas por el usuario (id, nombre, ambito)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, nombre, ambito FROM categorias_usuario
               WHERE user_id = ? ORDER BY nombre COLLATE NOCASE ASC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def listar_categorias_para_movimiento(user_id: int, movimiento_tipo: str) -> list[dict]:
    """Categorías aplicables a un gasto o ingreso (incluye ambito 'ambos')."""
    movimiento_tipo = movimiento_tipo.lower().strip()
    if movimiento_tipo not in ("gasto", "ingreso"):
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, nombre, ambito FROM categorias_usuario
               WHERE user_id = ? AND (ambito = ? OR ambito = 'ambos')
               ORDER BY nombre COLLATE NOCASE ASC""",
            (user_id, movimiento_tipo),
        ).fetchall()
    return [dict(r) for r in rows]


def categoria_permitida_para_movimiento(user_id: int, nombre: str, movimiento_tipo: str) -> bool:
    n = _normalizar_nombre_categoria(nombre)
    if not n:
        return False
    movimiento_tipo = movimiento_tipo.lower().strip()
    if movimiento_tipo not in ("gasto", "ingreso"):
        return False
    with get_connection() as conn:
        row = conn.execute(
            """SELECT 1 FROM categorias_usuario
               WHERE user_id = ? AND nombre = ?
                 AND (ambito = 'ambos' OR ambito = ?)""",
            (user_id, n, movimiento_tipo),
        ).fetchone()
    return row is not None


def obtener_categoria_usuario_por_id(user_id: int, categoria_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, nombre, ambito FROM categorias_usuario
               WHERE id = ? AND user_id = ?""",
            (categoria_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def agregar_categoria_usuario(user_id: int, nombre: str, ambito: str) -> tuple[bool, str]:
    n = _normalizar_nombre_categoria(nombre)
    if not n:
        return False, "El nombre de la categoría no puede estar vacío."
    ambito = ambito.lower().strip()
    if ambito not in ("gasto", "ingreso", "ambos"):
        return False, "El ámbito debe ser: gasto, ingreso o ambos."
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO categorias_usuario (user_id, nombre, ambito)
                   VALUES (?, ?, ?)""",
                (user_id, n, ambito),
            )
            cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return True, f"Categoría '{n}' (#{cid}, {ambito}) creada."
    except sqlite3.IntegrityError:
        return False, f"Ya tienes una categoría con el nombre '{n}'."


def renombrar_categoria_usuario(user_id: int, categoria_id: int, nuevo_nombre: str) -> tuple[bool, str]:
    nuevo = _normalizar_nombre_categoria(nuevo_nombre)
    if not nuevo:
        return False, "El nuevo nombre no puede estar vacío."
    actual = obtener_categoria_usuario_por_id(user_id, categoria_id)
    if not actual:
        return False, "No se encontró esa categoría o no te pertenece."
    viejo = actual["nombre"]
    if viejo == nuevo:
        return False, "El nombre es el mismo que ya tenías."

    try:
        with get_connection() as conn:
            conn.execute(
                """UPDATE categorias_usuario SET nombre = ?
                   WHERE id = ? AND user_id = ?""",
                (nuevo, categoria_id, user_id),
            )
            conn.execute(
                """UPDATE transacciones SET categoria = ?
                   WHERE user_id = ? AND categoria = ?
                     AND tipo IN ('gasto', 'ingreso')""",
                (nuevo, user_id, viejo),
            )
            conn.execute(
                """UPDATE presupuesto_movimientos SET categoria = ?
                   WHERE user_id = ? AND categoria = ?""",
                (nuevo, user_id, viejo),
            )
        return True, f"Categoría #{categoria_id} renombrada: '{viejo}' → '{nuevo}' (movimientos vinculados actualizados)."
    except sqlite3.IntegrityError:
        return False, f"Ya existe otra categoría con el nombre '{nuevo}'."


def _ensure_presupuesto_es_anual(conn: sqlite3.Connection) -> None:
    """Añade es_anual (gasto anual → se usa monto/12 en totales) si la tabla ya existía sin la columna."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='presupuesto_movimientos'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(presupuesto_movimientos)")}
    if "es_anual" in cols:
        return
    try:
        conn.execute(
            "ALTER TABLE presupuesto_movimientos ADD COLUMN es_anual INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass


def _ensure_presupuesto_tabla(conn: sqlite3.Connection) -> None:
    """Crea la tabla de presupuesto (única por usuario, sin periodo) o migra la versión con año/mes."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='presupuesto_movimientos'"
    ).fetchone()
    if not row:
        conn.execute("""
            CREATE TABLE presupuesto_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('gasto', 'ingreso')),
                monto REAL NOT NULL,
                categoria TEXT NOT NULL DEFAULT 'sin_categoria',
                es_anual INTEGER NOT NULL DEFAULT 0 CHECK(es_anual IN (0, 1)),
                creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        return

    cols = {r[1] for r in conn.execute("PRAGMA table_info(presupuesto_movimientos)")}
    if "ano" not in cols:
        return

    conn.execute("""
        CREATE TABLE presupuesto_movimientos_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('gasto', 'ingreso')),
            monto REAL NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'sin_categoria',
            es_anual INTEGER NOT NULL DEFAULT 0 CHECK(es_anual IN (0, 1)),
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO presupuesto_movimientos_new (id, user_id, tipo, monto, categoria, es_anual, creada_en)
        SELECT id, user_id, tipo, monto, categoria, 0, creada_en FROM presupuesto_movimientos
    """)
    conn.execute("DROP TABLE presupuesto_movimientos")
    conn.execute("ALTER TABLE presupuesto_movimientos_new RENAME TO presupuesto_movimientos")
    mx = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM presupuesto_movimientos"
    ).fetchone()[0]
    cur = conn.execute(
        "UPDATE sqlite_sequence SET seq = ? WHERE name = 'presupuesto_movimientos'",
        (mx,),
    )
    if cur.rowcount == 0:
        conn.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES ('presupuesto_movimientos', ?)",
            (mx,),
        )


def _ensure_presupuestos_y_relacion(conn: sqlite3.Connection) -> None:
    """Varios presupuestos por usuario; movimientos enlazados con presupuesto_id."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, nombre)
        )
    """)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='presupuesto_movimientos'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(presupuesto_movimientos)")}
    if "presupuesto_id" in cols:
        return
    for (uid,) in conn.execute(
        "SELECT DISTINCT user_id FROM presupuesto_movimientos"
    ).fetchall():
        conn.execute(
            "INSERT OR IGNORE INTO presupuestos (user_id, nombre) VALUES (?, ?)",
            (uid, "principal"),
        )
    conn.execute("ALTER TABLE presupuesto_movimientos ADD COLUMN presupuesto_id INTEGER")
    for mid, uid in conn.execute(
        "SELECT id, user_id FROM presupuesto_movimientos"
    ).fetchall():
        pr = conn.execute(
            "SELECT id FROM presupuestos WHERE user_id = ? AND nombre = ?",
            (uid, "principal"),
        ).fetchone()
        if pr:
            conn.execute(
                "UPDATE presupuesto_movimientos SET presupuesto_id = ? WHERE id = ?",
                (pr[0], mid),
            )


def _normalizar_nombre_presupuesto(nombre: str) -> str:
    return (nombre or "").strip().lower()


def obtener_presupuesto_por_nombre(user_id: int, nombre: str) -> dict | None:
    n = _normalizar_nombre_presupuesto(nombre)
    if not n:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, nombre FROM presupuestos WHERE user_id = ? AND nombre = ?",
            (user_id, n),
        ).fetchone()
    return dict(row) if row else None


def obtener_presupuesto_por_id(user_id: int, presupuesto_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, nombre FROM presupuestos WHERE id = ? AND user_id = ?",
            (presupuesto_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def resolver_presupuesto_por_nombre(user_id: int, nombre: str) -> tuple[int | None, str | None]:
    """Devuelve (presupuesto_id, None) o (None, error). Crea el presupuesto si no existe."""
    n = _normalizar_nombre_presupuesto(nombre)
    if not n:
        return None, "El nombre del presupuesto no puede estar vacío."
    existing = obtener_presupuesto_por_nombre(user_id, n)
    if existing:
        return existing["id"], None
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO presupuestos (user_id, nombre) VALUES (?, ?)",
                (user_id, n),
            )
            pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return pid, None
    except sqlite3.IntegrityError:
        row2 = obtener_presupuesto_por_nombre(user_id, n)
        if row2:
            return row2["id"], None
        return None, "No se pudo crear el presupuesto."


def listar_presupuestos(user_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT p.id, p.nombre,
               (SELECT COUNT(*) FROM presupuesto_movimientos m
                WHERE m.presupuesto_id = p.id) AS n_movimientos
               FROM presupuestos p WHERE p.user_id = ?
               ORDER BY p.nombre COLLATE NOCASE ASC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def clonar_presupuesto(
    user_id: int, presupuesto_origen_id: int, nuevo_nombre: str
) -> tuple[bool, str]:
    """Copia todas las líneas de un presupuesto a uno nuevo con otro nombre."""
    n = _normalizar_nombre_presupuesto(nuevo_nombre)
    if not n:
        return False, "El nombre del presupuesto nuevo no puede estar vacío."
    orig = obtener_presupuesto_por_id(user_id, presupuesto_origen_id)
    if not orig:
        return False, "El presupuesto a copiar no existe o no te pertenece."
    if orig["nombre"] == n:
        return False, "El nombre nuevo debe ser distinto al del presupuesto original."
    if obtener_presupuesto_por_nombre(user_id, n):
        return False, f"Ya tienes un presupuesto llamado «{n}»."

    with get_connection() as conn:
        movs = conn.execute(
            """SELECT tipo, monto, categoria, COALESCE(es_anual, 0) AS es_anual
               FROM presupuesto_movimientos
               WHERE user_id = ? AND presupuesto_id = ?""",
            (user_id, presupuesto_origen_id),
        ).fetchall()
        conn.execute(
            "INSERT INTO presupuestos (user_id, nombre) VALUES (?, ?)",
            (user_id, n),
        )
        nuevo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in movs:
            conn.execute(
                """INSERT INTO presupuesto_movimientos
                   (user_id, presupuesto_id, tipo, monto, categoria, es_anual)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    nuevo_id,
                    r["tipo"],
                    r["monto"],
                    r["categoria"],
                    int(r["es_anual"]),
                ),
            )
        n_copias = len(movs)

    return True, (
        f"Presupuesto «{orig['nombre']}» clonado como «{n}» (#{nuevo_id}): "
        f"{n_copias} línea(s) copiada(s)."
    )


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


def obtener_ids_usuarios_con_cuentas() -> list[int]:
    """Obtiene los user_id de todos los usuarios que tienen al menos una cuenta."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM cuentas ORDER BY user_id"
        ).fetchall()
    return [row[0] for row in rows]


def listar_cuentas(user_id: int) -> list[dict]:
    """Lista todas las cuentas del usuario."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nombre, tipo, saldo FROM cuentas WHERE user_id = ? ORDER BY nombre COLLATE NOCASE",
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


def obtener_cuenta_por_id(user_id: int, cuenta_id: int) -> dict | None:
    """Obtiene una cuenta por id si pertenece al usuario."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, nombre, tipo, saldo FROM cuentas WHERE user_id = ? AND id = ?",
            (user_id, cuenta_id),
        ).fetchone()
    return dict(row) if row else None


def registrar_gasto(user_id: int, nombre_cuenta: str, monto: float, categoria: str) -> tuple[bool, str]:
    """Registra un gasto en la cuenta especificada."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return False, f"No se encontró la cuenta '{nombre_cuenta}'."

    if monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = _normalizar_nombre_categoria(categoria)
    if not cat:
        return False, "Debes elegir una categoría de tu lista (/mis_categorias)."
    if not categoria_permitida_para_movimiento(user_id, cat, "gasto"):
        return False, (
            "Esa categoría no es válida para gastos. Revisa /mis_categorias o usa /agregar_categoria."
        )

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


def registrar_ingreso(user_id: int, nombre_cuenta: str, monto: float, categoria: str) -> tuple[bool, str]:
    """Registra un ingreso en la cuenta especificada."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return False, f"No se encontró la cuenta '{nombre_cuenta}'."

    if monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = _normalizar_nombre_categoria(categoria)
    if not cat:
        return False, "Debes elegir una categoría de tu lista (/mis_categorias)."
    if not categoria_permitida_para_movimiento(user_id, cat, "ingreso"):
        return False, (
            "Esa categoría no es válida para ingresos. Revisa /mis_categorias o usa /agregar_categoria."
        )
    nuevo_saldo = cuenta["saldo"] + monto

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, categoria) VALUES (?, ?, 'ingreso', ?, ?)",
            (user_id, cuenta["id"], monto, cat)
        )
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))

    return True, f"Ingreso de ${monto:,.2f} registrado en '{cuenta['nombre']}' [{cat}]."


def registrar_ajuste_saldo(user_id: int, nombre_cuenta: str, saldo_objetivo: float) -> tuple[bool, str]:
    """Deja el saldo de la cuenta igual a saldo_objetivo mediante un ingreso o gasto con categoría 'ajuste'."""
    cuenta = obtener_cuenta_por_nombre(user_id, nombre_cuenta)
    if not cuenta:
        return False, f"No se encontró la cuenta '{nombre_cuenta}'."

    delta = saldo_objetivo - cuenta["saldo"]
    if abs(delta) < 1e-9:
        return True, f"El saldo de '{cuenta['nombre']}' ya es ${saldo_objetivo:,.2f}. No se registró ningún movimiento."

    cat = "ajuste"
    with get_connection() as conn:
        if delta > 0:
            nuevo_saldo = cuenta["saldo"] + delta
            conn.execute(
                "INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, categoria) VALUES (?, ?, 'ingreso', ?, ?)",
                (user_id, cuenta["id"], delta, cat),
            )
        else:
            monto_gasto = -delta
            nuevo_saldo = cuenta["saldo"] - monto_gasto
            conn.execute(
                "INSERT INTO transacciones (user_id, cuenta_id, tipo, monto, categoria) VALUES (?, ?, 'gasto', ?, ?)",
                (user_id, cuenta["id"], monto_gasto, cat),
            )
        conn.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (nuevo_saldo, cuenta["id"]))

    return True, (
        f"Saldo de '{cuenta['nombre']}' ajustado a ${saldo_objetivo:,.2f} "
        f"(registro [ajuste]: {'+' if delta > 0 else '-'}${abs(delta):,.2f})."
    )


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
            GROUP BY COALESCE(categoria, 'sin_categoria')
            ORDER BY categoria COLLATE NOCASE ASC
        """, params).fetchall()

        ingresos = conn.execute(f"""
            SELECT COALESCE(categoria, 'sin_categoria') AS categoria, SUM(monto) AS total
            FROM transacciones WHERE tipo = 'ingreso' {filtro}
            GROUP BY COALESCE(categoria, 'sin_categoria')
            ORDER BY categoria COLLATE NOCASE ASC
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
                GROUP BY ano, mes
            """, (user_id, ano)).fetchall()
        else:
            rows = conn.execute("""
                SELECT CAST(strftime('%Y', creada_en) AS INTEGER) AS ano,
                       CAST(strftime('%m', creada_en) AS INTEGER) AS mes,
                       SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END) AS gastos,
                       SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END) AS ingresos
                FROM transacciones
                WHERE user_id = ? AND tipo IN ('gasto', 'ingreso')
                GROUP BY ano, mes
                ORDER BY ano DESC, mes DESC LIMIT ?
            """, (user_id, limite)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["balance"] = (d["ingresos"] or 0) - (d["gastos"] or 0)
        result.append(d)
    # Orden alfabético por período Año-Mes (p. ej. 2024-01 antes que 2025-03)
    result.sort(key=lambda d: (d["ano"], d["mes"]))
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
        cat = _normalizar_nombre_categoria(categoria)
        if not cat:
            return False, "La categoría no puede estar vacía."
        if not categoria_permitida_para_movimiento(user_id, cat, tipo):
            return False, (
                f"Esa categoría no es válida para {tipo}s. Revisa /mis_categorias o usa /agregar_categoria."
            )

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


def agregar_presupuesto_registro(
    user_id: int,
    presupuesto_id: int,
    tipo: str,
    monto: float,
    categoria: str,
    es_anual: bool = False,
) -> tuple[bool, str]:
    """Registra un gasto o ingreso en un presupuesto concreto del usuario.

    Si es gasto anual, `monto` es el total del año; en totales se usa monto/12 como carga mensual.
    """
    tipo = tipo.lower().strip()
    if tipo not in ("gasto", "ingreso"):
        return False, "Tipo interno inválido."
    if monto <= 0:
        return False, "El monto debe ser mayor a 0."
    if tipo == "ingreso":
        es_anual = False
    cat = _normalizar_nombre_categoria(categoria)
    if not cat:
        return False, "Debes indicar una categoría de tu lista (/mis_categorias)."
    if not categoria_permitida_para_movimiento(user_id, cat, tipo):
        return False, (
            f"Esa categoría no es válida para {tipo}s de presupuesto. "
            "Revisa /mis_categorias o usa /agregar_categoria."
        )
    anual_flag = 1 if es_anual else 0

    with get_connection() as conn:
        pn = conn.execute(
            "SELECT nombre FROM presupuestos WHERE id = ? AND user_id = ?",
            (presupuesto_id, user_id),
        ).fetchone()
        if not pn:
            return False, "Presupuesto no encontrado o no te pertenece."
        nombre_pres = pn[0]
        conn.execute(
            """INSERT INTO presupuesto_movimientos
               (user_id, presupuesto_id, tipo, monto, categoria, es_anual)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, presupuesto_id, tipo, monto, cat, anual_flag),
        )
        reg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    etiqueta = "Gasto" if tipo == "gasto" else "Ingreso"
    sufijo = f" [«{nombre_pres}»]"
    if tipo == "gasto" and es_anual:
        mensual = monto / 12.0
        return True, (
            f"{etiqueta} de presupuesto #{reg_id}{sufijo} (anual): ${monto:,.2f}/año "
            f"→ ${mensual:,.2f}/mes en totales [{cat}]."
        )
    return True, f"{etiqueta} de presupuesto #{reg_id}{sufijo}: ${monto:,.2f} [{cat}]."


def obtener_presupuesto_registro(user_id: int, registro_id: int) -> dict | None:
    """Obtiene un movimiento de presupuesto por ID si pertenece al usuario."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM presupuesto_movimientos WHERE id = ? AND user_id = ?",
            (registro_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def editar_presupuesto_registro(
    user_id: int,
    registro_id: int,
    monto: float | None = None,
    categoria: str | None = None,
) -> tuple[bool, str]:
    """Edita monto y/o categoría de un registro de presupuesto."""
    reg = obtener_presupuesto_registro(user_id, registro_id)
    if not reg:
        return False, "No se encontró el registro o no te pertenece."
    if monto is None and categoria is None:
        return False, "Debes cambiar al menos monto o categoría."
    if monto is not None and monto <= 0:
        return False, "El monto debe ser mayor a 0."

    cat = None
    if categoria is not None:
        cat = _normalizar_nombre_categoria(categoria)
        if not cat:
            return False, "La categoría no puede estar vacía."
        reg_tipo = reg["tipo"]
        if not categoria_permitida_para_movimiento(user_id, cat, reg_tipo):
            return False, (
                f"Esa categoría no es válida para {reg_tipo}s de presupuesto. "
                "Revisa /mis_categorias o usa /agregar_categoria."
            )

    with get_connection() as conn:
        if monto is not None:
            conn.execute(
                "UPDATE presupuesto_movimientos SET monto = ? WHERE id = ? AND user_id = ?",
                (monto, registro_id, user_id),
            )
        if cat is not None:
            conn.execute(
                "UPDATE presupuesto_movimientos SET categoria = ? WHERE id = ? AND user_id = ?",
                (cat, registro_id, user_id),
            )

    es_anual = bool(reg.get("es_anual", 0))
    cambios = []
    if monto is not None:
        if es_anual and reg["tipo"] == "gasto":
            cambios.append(f"monto anual ${monto:,.2f} (${monto / 12.0:,.2f}/mes en totales)")
        else:
            cambios.append(f"monto ${monto:,.2f}")
    if cat is not None:
        cambios.append(f"categoría '{cat}'")
    return True, f"Registro de presupuesto #{registro_id} actualizado: {', '.join(cambios)}."


def eliminar_presupuesto_registro(user_id: int, registro_id: int) -> tuple[bool, str]:
    """Elimina una línea de presupuesto por ID (único entre todos los presupuestos del usuario)."""
    reg = obtener_presupuesto_registro(user_id, registro_id)
    if not reg:
        return False, "No se encontró el registro o no te pertenece."
    pid = reg.get("presupuesto_id")
    nombre_pres = "?"
    with get_connection() as conn:
        if pid is not None:
            pr = conn.execute(
                "SELECT nombre FROM presupuestos WHERE id = ? AND user_id = ?",
                (pid, user_id),
            ).fetchone()
            if pr:
                nombre_pres = pr[0]
        conn.execute(
            "DELETE FROM presupuesto_movimientos WHERE id = ? AND user_id = ?",
            (registro_id, user_id),
        )
    tipo = reg["tipo"]
    monto = reg["monto"]
    cat = reg.get("categoria", "")
    return True, (
        f"Línea #{registro_id} eliminada del presupuesto «{nombre_pres}» "
        f"({tipo}, [{cat}] ${monto:,.2f})."
    )


def listar_presupuesto(user_id: int, presupuesto_id: int) -> list[dict]:
    """Lista movimientos de un presupuesto concreto."""
    with get_connection() as conn:
        ok = conn.execute(
            "SELECT 1 FROM presupuestos WHERE id = ? AND user_id = ?",
            (presupuesto_id, user_id),
        ).fetchone()
        if not ok:
            return []
        rows = conn.execute(
            """SELECT id, tipo, monto, categoria, COALESCE(es_anual, 0) AS es_anual, creada_en
               FROM presupuesto_movimientos
               WHERE user_id = ? AND presupuesto_id = ?
               ORDER BY categoria COLLATE NOCASE ASC, tipo DESC, id ASC""",
            (user_id, presupuesto_id),
        ).fetchall()
    return [dict(r) for r in rows]


def totales_presupuesto(user_id: int, presupuesto_id: int) -> dict:
    """Totales de un presupuesto concreto.

    Los gastos marcados como anuales cuentan como monto/12 en el total de gastos mensual.
    """
    with get_connection() as conn:
        ok = conn.execute(
            "SELECT 1 FROM presupuestos WHERE id = ? AND user_id = ?",
            (presupuesto_id, user_id),
        ).fetchone()
        if not ok:
            return {"total_gasto": 0.0, "total_ingreso": 0.0, "balance": 0.0}
        row = conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN
                       CASE WHEN COALESCE(es_anual, 0) = 1 THEN monto / 12.0 ELSE monto END
                   ELSE 0 END), 0) AS total_gasto,
                   COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) AS total_ingreso
               FROM presupuesto_movimientos
               WHERE user_id = ? AND presupuesto_id = ?""",
            (user_id, presupuesto_id),
        ).fetchone()
    g = row["total_gasto"] if row else 0.0
    i = row["total_ingreso"] if row else 0.0
    return {
        "total_gasto": g,
        "total_ingreso": i,
        "balance": i - g,
    }
