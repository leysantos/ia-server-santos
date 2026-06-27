#!/usr/bin/env bash
# Instala serviço systemd user para cloudflared (inicia com o WSL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "$UNIT_DIR"

cat > "${UNIT_DIR}/cloudflared-ia-server.service" <<EOF
[Unit]
Description=Cloudflare Tunnel — IA Server Santos
After=network-online.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
ExecStart=${ROOT}/scripts/cloudflare/run_tunnel.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable cloudflared-ia-server.service
echo "Serviço instalado. Comandos:"
echo "  systemctl --user start cloudflared-ia-server"
echo "  systemctl --user status cloudflared-ia-server"
echo "  journalctl --user -u cloudflared-ia-server -f"
