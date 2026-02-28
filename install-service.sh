#!/bin/bash
# Instala el servicio systemd para Finance Guy Bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/finance-guy-bot@.service"
SYSTEMD_DIR="/etc/systemd/system"

# Usuario que ejecutó el script (funciona con sudo)
RUN_USER="${SUDO_USER:-$USER}"

if [[ $EUID -ne 0 ]]; then
    echo "Este script debe ejecutarse con sudo:"
    echo "  sudo ./install-service.sh"
    exit 1
fi

if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "Error: No se encontró $SERVICE_FILE"
    exit 1
fi

echo "Instalando servicio Finance Guy Bot para usuario: $RUN_USER"
echo ""

cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
echo "✓ Archivo copiado a $SYSTEMD_DIR/"

systemctl daemon-reload
echo "✓ systemd recargado"

systemctl enable "finance-guy-bot@$RUN_USER.service"
echo "✓ Servicio habilitado (inicio automático al reiniciar)"

systemctl start "finance-guy-bot@$RUN_USER.service"
echo "✓ Servicio iniciado"

echo ""
echo "Instalación completada. El bot está corriendo."
echo ""
echo "Comandos útiles:"
echo "  sudo systemctl status finance-guy-bot@$RUN_USER.service  # Ver estado"
echo "  sudo systemctl restart finance-guy-bot@$RUN_USER.service # Reiniciar"
echo "  sudo systemctl stop finance-guy-bot@$RUN_USER.service     # Detener"
echo "  journalctl -u finance-guy-bot@$RUN_USER.service -f       # Ver logs"
echo ""
