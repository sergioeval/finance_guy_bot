"""Utilidades compartidas."""
import re


def is_null(text: str) -> bool:
    """True si el texto representa null (vacío/opcional)."""
    return text.strip().lower() == "null"


def parse_cantidad(texto: str) -> float | None:
    """Parsea una cantidad, aceptando formatos como 1000, 1.000,50, 1,000.50"""
    if not texto or not texto.strip():
        return None
    limpio = texto.strip().replace(",", ".")
    limpio = re.sub(r"\.(?=\d{3}\b)", "", limpio)
    try:
        return float(limpio)
    except ValueError:
        return None


def formato_tipo(tipo: str) -> str:
    """Convierte el tipo de transacción a texto legible."""
    mapeo = {
        "gasto": "Gasto",
        "ingreso": "Ingreso",
        "transferencia_salida": "Transferencia →",
        "transferencia_entrada": "Transferencia ←",
    }
    return mapeo.get(tipo, tipo)
