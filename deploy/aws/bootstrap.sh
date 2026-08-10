#!/usr/bin/env bash

set -Eeuo pipefail

exec > >(tee /var/log/medidoc-bootstrap.log) 2>&1

REPOSITORY_URL="https://github.com/GitGitRice/medidoc.git"
GIT_REF="develop"
APP_DIR="/opt/medidoc"
COMPOSE_VERSION="v5.1.2"
BUILDX_VERSION="v0.17.1"

echo "MediDoc bootstrap started"

dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

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
git clone --branch "${GIT_REF}" --single-branch "${REPOSITORY_URL}" "${APP_DIR}"
cd "${APP_DIR}"

IMDS_TOKEN="$(curl -fsS -X PUT \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' \
  http://169.254.169.254/latest/api/token)"
PUBLIC_HOSTNAME="$(curl -fsS \
  -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  http://169.254.169.254/latest/meta-data/public-hostname)"

POSTGRES_PASSWORD="$(openssl rand -hex 24)"
JWT_SECRET="$(openssl rand -hex 32)"
ADMIN_PASSWORD="$(openssl rand -hex 12)"
STAFF_PASSWORD="$(openssl rand -hex 12)"

umask 077
cat > .env <<EOF
POSTGRES_DB=medidoc
POSTGRES_USER=medidoc
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_PORT=5432
DB_BIND_IP=127.0.0.1
JWT_SECRET=${JWT_SECRET}
SEED_ADMIN_EMAIL=anna.admin@medidoc.test
SEED_ADMIN_PASSWORD=${ADMIN_PASSWORD}
SEED_STAFF_EMAIL=tom.staff@medidoc.test
SEED_STAFF_PASSWORD=${STAFF_PASSWORD}
CORS_ORIGINS=http://${PUBLIC_HOSTNAME}:5173
VITE_API_URL=http://${PUBLIC_HOSTNAME}:8000
VITE_ALLOWED_HOST=${PUBLIC_HOSTNAME}
FRONTEND_PORT=5173
LOG_LEVEL=INFO
LOG_JSON=true
MONGO_URL=
MONGO_DB=medidoc
MONGO_DB_PORT=27017
AUDIT_RETENTION_DAYS=30
ABUSE_WINDOW_MINUTES=15
ABUSE_FAILED_LOGINS_PER_EMAIL=5
ABUSE_FAILED_LOGINS_PER_IP=10
ABUSE_REJECTED_TOKENS_PER_IP=10
ABUSE_FORBIDDEN_PER_USER=3
ABUSE_NOT_FOUND_PER_USER=20
EOF

cat > /home/ec2-user/medidoc-demo-login.txt <<EOF
MediDoc URL: http://${PUBLIC_HOSTNAME}:5173
Admin: anna.admin@medidoc.test
Admin-Passwort: ${ADMIN_PASSWORD}
Staff: tom.staff@medidoc.test
Staff-Passwort: ${STAFF_PASSWORD}
EOF
chown ec2-user:ec2-user /home/ec2-user/medidoc-demo-login.txt
chmod 0600 /home/ec2-user/medidoc-demo-login.txt

docker compose up -d --build

for attempt in {1..30}; do
  if docker compose exec -T postgres pg_isready -U medidoc -d medidoc; then
    break
  fi
  if [[ "${attempt}" -eq 30 ]]; then
    echo "PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 5
done

docker compose exec -T fastapi python -m app.seed --patients 25

echo "MediDoc bootstrap completed: http://${PUBLIC_HOSTNAME}:5173"
