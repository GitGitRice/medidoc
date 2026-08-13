#!/usr/bin/env bash

set -Eeuo pipefail

exec > >(tee /var/log/medidoc-bootstrap.log) 2>&1

REPOSITORY_URL="https://github.com/GitGitRice/medidoc.git"
# main ist laut ADR-0006 der vorfuehrbare Stand. Fuer ein unveraenderliches Release
# kann GIT_REF vor dem Aufruf stattdessen auf einen Tag oder Commit-SHA gesetzt werden.
GIT_REF="${GIT_REF:-main}"
APP_DIR="/opt/medidoc"
# docker-compose.prod.yml ersetzt nur den frontend-Service: statt des
# Vite-Dev-Servers liefert nginx einen einmal gebauten Produktions-Build aus.
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
COMPOSE_VERSION="v5.1.2"
BUILDX_VERSION="v0.17.1"
POSTGRES_DB="medidoc"
POSTGRES_USER="medidoc"

echo "MediDoc bootstrap started"

if [[ -f "${APP_DIR}/.env" ]]; then
  echo "${APP_DIR}/.env existiert bereits. Bootstrap bricht ab." >&2
  echo "Sonst passen neue Zugangsdaten nicht mehr zu den vorhandenen Datenbank-Volumes." >&2
  exit 1
fi

dnf update -y
dnf install -y docker git
systemctl enable --now docker

if ! docker compose version >/dev/null 2>&1; then
  install -d -m 0755 /usr/local/lib/docker/cli-plugins
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod 0755 /usr/local/lib/docker/cli-plugins/docker-compose
fi

# Das Buildx-Paket von Amazon Linux ist aelter als von Compose 5 verlangt.
install -d -m 0755 /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod 0755 /usr/local/lib/docker/cli-plugins/docker-buildx

# t2.micro hat nur 1 GiB RAM. Swap verhindert, dass der erste Image-Build
# wegen Speichermangels abbricht.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile swap swap defaults 0 0' >> /etc/fstab

rm -rf "${APP_DIR}"
git clone "${REPOSITORY_URL}" "${APP_DIR}"
git -C "${APP_DIR}" checkout "${GIT_REF}"
cd "${APP_DIR}"

IMDS_TOKEN="$(curl -fsS -X PUT \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' \
  http://169.254.169.254/latest/api/token)"
PUBLIC_HOSTNAME="$(curl -fsS \
  -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  http://169.254.169.254/latest/meta-data/public-hostname)"
PUBLIC_IPV4="$(curl -fsS \
  -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  http://169.254.169.254/latest/meta-data/public-ipv4)"

POSTGRES_PASSWORD="$(openssl rand -hex 24)"
JWT_SECRET="$(openssl rand -hex 32)"
ADMIN_PASSWORD="$(openssl rand -hex 12)"
STAFF_PASSWORD="$(openssl rand -hex 12)"

umask 077
cp .env.example .env

set_env() {
  local key="$1"
  local value="$2"

  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*$|${key}=${value}|" .env
  else
    printf '%s=%s\n' "${key}" "${value}" >> .env
  fi
}

set_env POSTGRES_DB "${POSTGRES_DB}"
set_env POSTGRES_USER "${POSTGRES_USER}"
set_env POSTGRES_PASSWORD "${POSTGRES_PASSWORD}"
set_env DB_BIND_IP "127.0.0.1"
set_env JWT_SECRET "${JWT_SECRET}"
set_env SEED_ADMIN_EMAIL "anna.admin@medidoc.test"
set_env SEED_ADMIN_PASSWORD "${ADMIN_PASSWORD}"
set_env SEED_STAFF_EMAIL "tom.staff@medidoc.test"
set_env SEED_STAFF_PASSWORD "${STAFF_PASSWORD}"
set_env CORS_ORIGINS "http://${PUBLIC_HOSTNAME}:5173,http://${PUBLIC_IPV4}:5173"
set_env VITE_API_URL "http://${PUBLIC_HOSTNAME}:8000"
set_env VITE_ALLOWED_HOSTS "${PUBLIC_HOSTNAME}"
set_env LOG_JSON "true"

cat > /home/ec2-user/medidoc-demo-login.txt <<EOF
MediDoc URL: http://${PUBLIC_HOSTNAME}:5173
Admin: anna.admin@medidoc.test
Admin-Passwort: ${ADMIN_PASSWORD}
Staff: tom.staff@medidoc.test
Staff-Passwort: ${STAFF_PASSWORD}
EOF
chown ec2-user:ec2-user /home/ec2-user/medidoc-demo-login.txt
chmod 0600 /home/ec2-user/medidoc-demo-login.txt

docker compose "${COMPOSE_FILES[@]}" up -d --build --wait --wait-timeout 150

docker compose "${COMPOSE_FILES[@]}" exec -T fastapi python -m app.seed --patients 25

echo "MediDoc bootstrap completed: http://${PUBLIC_HOSTNAME}:5173"
