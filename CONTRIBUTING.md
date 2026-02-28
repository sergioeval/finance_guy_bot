# Guía para contribuir

¡Gracias por tu interés en contribuir a Finance Guy! Todas las contribuciones son bienvenidas.

## Cómo contribuir

### Reportar un bug

1. Revisa si ya existe un [issue](https://github.com/sergioeval/finance_guy_bot/issues) similar.
2. Si no existe, crea uno nuevo usando la plantilla de "Bug report".
3. Incluye pasos para reproducir el problema y la versión de Python que usas.

### Sugerir una mejora

1. Abre un [issue](https://github.com/sergioeval/finance_guy_bot/issues) con la plantilla de "Feature request".
2. Describe la funcionalidad que te gustaría ver y por qué sería útil.

### Enviar cambios (Pull Request)

1. **Haz fork** del repositorio y clónalo en tu máquina.

2. **Crea una rama** para tu cambio:
   ```bash
   git checkout -b mi-mejora
   ```

3. **Haz tus cambios** siguiendo el estilo del código existente.

4. **Prueba** que todo funcione correctamente.

5. **Haz commit** con mensajes claros:
   ```bash
   git add .
   git commit -m "feat: descripción breve del cambio"
   ```

6. **Haz push** a tu fork y abre un Pull Request contra la rama `main`.

7. Describe los cambios en el PR y enlaza el issue relacionado si aplica.

## Convenciones de commits

Usa prefijos para los mensajes de commit:

- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `docs:` cambios en documentación
- `refactor:` refactorización de código
- `test:` añadir o modificar tests

## Estructura del proyecto

- `bot.py` — Lógica del bot de Telegram (comandos, flujos conversacionales)
- `database.py` — Acceso a SQLite (cuentas, transacciones)
- `requirements.txt` — Dependencias Python

## Preguntas

Si tienes dudas, abre un issue y lo revisamos.
