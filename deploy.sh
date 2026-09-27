#!/bin/bash
set -euo pipefail

echo "=================================================================="
echo "🚀 INICIANDO DESPLIEGUE DE FOGATA A GITHUB Y SERVIDOR HOSTGATOR"
echo "=================================================================="

REMOTE_HOST="humm.cl"
REMOTE_PORT="2222"
REMOTE_USER="paulocis"
APP_DIR="/home1/paulocis/apps/fogata/app"
VENV_DIR="/home1/paulocis/apps/fogata/venv"
SUBDOMAIN_DIR="/home1/paulocis/fogata.humm.cl"
SECRETS_DIR="/home1/paulocis/apps/fogata/secrets"

# 1. Enviar cambios locales a GitHub
echo "📦 [1/3] Enviando cambios a GitHub (nativoaustral-bit/fogata)..."
git push origin main

# 2. Actualizar código en el servidor mediante Git y recargar
echo "🌐 [2/3] Actualizando código en servidor de producción ($APP_DIR)..."
ssh -i ~/.ssh/id_ed25519_humm -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" bash << 'EOF'
set -euo pipefail

APP_DIR="/home1/paulocis/apps/fogata/app"
VENV_DIR="/home1/paulocis/apps/fogata/venv"
SUBDOMAIN_DIR="/home1/paulocis/fogata.humm.cl"
SECRETS_DIR="/home1/paulocis/apps/fogata/secrets"

cd "$APP_DIR"
git fetch origin main
git checkout main
git merge origin/main --ff-only

# Instalar dependencias si hay cambios
/home1/paulocis/.local/bin/uv pip install -r requirements.txt --python "$VENV_DIR" --quiet

# Exportar variables de entorno para manage.py
set -a
source "${SECRETS_DIR}/.env"
set +a

# Ejecutar migraciones
echo "🗄️  Ejecutando migraciones de base de datos..."
"${VENV_DIR}/bin/python" manage.py migrate --noinput

# Recolectar archivos estáticos
echo "🎨 Recolectando archivos estáticos..."
"${VENV_DIR}/bin/python" manage.py collectstatic --noinput

# Reiniciar Passenger
echo "🔄 Reiniciando Phusion Passenger..."
touch "${SUBDOMAIN_DIR}/tmp/restart.txt"

echo "✔ Servidor actualizado con éxito."
EOF

# 3. Comprobación de salud HTTP en producción
echo "🔍 [3/3] Ejecutando comprobación de servicio web en https://fogata.humm.cl..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --resolve fogata.humm.cl:443:162.241.60.177 https://fogata.humm.cl/ 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" https://fogata.humm.cl/)
if [ "$HTTP_STATUS" != "200" ]; then
    echo "❌ Error: https://fogata.humm.cl/ devolvió código HTTP $HTTP_STATUS (esperado 200)." >&2
    exit 1
fi
echo "✔ Servicio web activo y saludable: HTTP $HTTP_STATUS en https://fogata.humm.cl/"

echo "=================================================================="
echo "✅ ¡DESPLIEGUE COMPLETADO CON ÉXITO!"
echo "URL activa: https://fogata.humm.cl/"
echo "=================================================================="
