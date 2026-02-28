"""
Punto de entrada del bot (compatibilidad con systemd).
Ejecuta el bot modular desde src.main.
"""
from src.main import main

if __name__ == "__main__":
    main()
