# Finance Guy - Bot de Finanzas Personales

Bot de Telegram para gestionar tus finanzas personales. Los comandos piden los parámetros **paso a paso** en lugar de usar una sola línea.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Requisitos

- Python 3.10+
- Token de Telegram (ver sección siguiente)

## Crear tu bot en BotFather

Para usar este proyecto necesitas crear tu propio bot en Telegram y obtener un token. Sigue estos pasos:

1. **Abre Telegram** y busca [@BotFather](https://t.me/BotFather) (el bot oficial de Telegram para crear bots).

2. **Inicia la conversación** con `/start`.

3. **Crea un nuevo bot** con el comando:
   ```
   /newbot
   ```

4. **Elige un nombre** para tu bot cuando te lo pida (ej: "Mi Finance Guy"). Este nombre se muestra en el perfil del bot.

5. **Elige un username** que termine en `bot` (ej: `mi_finance_guy_bot`). Debe ser único en Telegram.

6. **Guarda el token** que BotFather te devuelve. Tendrá un formato como:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   ⚠️ **Importante:** No compartas este token con nadie. Quien lo tenga puede controlar tu bot.

7. **Opcional:** Puedes usar `/setdescription` en BotFather para añadir una descripción que los usuarios verán al iniciar el bot.

Con el token listo, continúa con la instalación del proyecto.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Asegúrate de tener el archivo `.env` con tu token:

```
TELEGRAM_BOT_TOKEN=tu_token_aqui
```

## Ejecución

```bash
source .venv/bin/activate
python bot.py
```

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida |
| `/help` | Ayuda detallada de todos los comandos |
| `/cancel` | Cancela el comando actual |
| `/crear_cuenta` | Crear cuenta (te pide: nombre, tipo) |
| `/cuentas` | Listar todas las cuentas |
| `/gasto` | Registrar gasto (cuenta, monto, categoría) |
| `/ingreso` | Registrar ingreso (cuenta, monto, categoría) |
| `/transferencia` | Transferir (origen, destino, monto) |
| `/registros` | Listar movimientos (nombre de cuenta) |
| `/editar` | Editar gasto/ingreso (ID, monto, categoría) |
| `/eliminar` | Eliminar registro por ID |
| `/resumen` | Resumen total de cuentas |
| `/resumen_categorias` | Resumen por categoría (mes, año) |
| `/resumen_mes` | Resumen mensual (año, mes) |

### Flujo paso a paso

Los comandos con parámetros inician una conversación y van preguntando cada dato. Por ejemplo, al usar `/gasto`:

1. ¿En qué cuenta?
2. ¿Monto?
3. ¿Categoría? (o null para sin_categoria)

### Parámetro `null`

Para parámetros opcionales, escribe **`null`** para dejarlos vacíos:

- **gasto/ingreso**: categoría `null` → se usa "sin_categoria"
- **editar**: monto `null` → no cambia; categoría `null` → no cambia (al menos uno debe ser distinto de null)
- **resumen_categorias**: mes `null` → todos; año `null` → todos
- **resumen_mes**: año `null` → últimos 12 meses; mes `null` → todos los meses del año

### Notas

- **Cuentas de débito**: saldo positivo = dinero disponible
- **Cuentas de crédito**: saldo negativo = deuda
- Los IDs de registros se ven en `/registros` (nombre de cuenta)

## Estructura del proyecto

```
finance_guy/
├── src/
│   ├── main.py          # Entry point del bot
│   ├── config.py        # Constantes y estados
│   ├── utils.py         # Utilidades (parse_cantidad, is_null, etc.)
│   ├── database/        # Lógica de base de datos SQLite
│   └── handlers/        # Comandos y flujos conversacionales
│       ├── commands.py  # start, help, cuentas, resumen
│       ├── cuentas.py   # crear_cuenta
│       ├── movimientos.py   # gasto, ingreso, transferencia
│       ├── historial.py     # registros, editar, eliminar
│       └── resumenes.py     # resumen_categorias, resumen_mes
├── bot.py               # Wrapper (ejecuta src.main)
├── database.py          # Re-export para compatibilidad
└── finanzas.db          # Base de datos (se crea al ejecutar)
```

## Base de datos

Los datos se guardan en `finanzas.db` (SQLite) en el directorio del proyecto. Cada usuario de Telegram tiene sus propias cuentas y transacciones aisladas.

## Ejecutar como servicio de systemd

Para que el bot se ejecute automáticamente al iniciar el servidor:

```bash
# Instalación automática (recomendado)
sudo ./install-service.sh
```

O manualmente:

```bash
# Copiar el archivo de servicio (requiere sudo)
sudo cp finance-guy-bot@.service /etc/systemd/system/

# Habilitar e iniciar el servicio (reemplaza 'tu_usuario' por tu usuario de sistema)
sudo systemctl daemon-reload
sudo systemctl enable finance-guy-bot@tu_usuario.service
sudo systemctl start finance-guy-bot@tu_usuario.service

# Verificar estado
sudo systemctl status finance-guy-bot@tu_usuario.service
```

Comandos útiles:
- `sudo systemctl stop finance-guy-bot@tu_usuario.service` - Detener el bot
- `sudo systemctl restart finance-guy-bot@tu_usuario.service` - Reiniciar el bot
- `journalctl -u finance-guy-bot@tu_usuario.service -f` - Ver logs en tiempo real

**Nota:** Si el proyecto está en otra ruta, edita el archivo `.service` y cambia las rutas en `WorkingDirectory` y `ExecStart`.

## Contribuir

Las contribuciones son bienvenidas. Lee la [guía de contribución](CONTRIBUTING.md) para más detalles.

Si encuentras una vulnerabilidad de seguridad, consulta la [política de seguridad](SECURITY.md).

## Licencia

Este proyecto está bajo la [Licencia MIT](LICENSE).
