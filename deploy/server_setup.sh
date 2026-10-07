#!/usr/bin/env bash
# ERP serverini bir marta sozlash (Ubuntu 24.04, root sifatida).
# Qayta ishga tushirish xavfsiz: bor narsani buzmaydi, yetishmaganini qo'shadi.
#
#   DOMAIN=erp.example.uz EMAIL=admin@example.uz bash server_setup.sh
#
# Railway o'zgaruvchilarini ko'chirish uchun (ixtiyoriy): Railway → Variables →
# Raw Editor matnini serverda /root/railway.env ga saqlang, skript uni .env ga qo'shadi.
set -euo pipefail

DOMAIN="${DOMAIN:?DOMAIN kerak, masalan: DOMAIN=erp.example.uz}"
EMAIL="${EMAIL:-}"
PG_VERSION="${PG_VERSION:-18}"  # Railway bilan bir xil
PY_VERSION="${PY_VERSION:-3.11}"
REPO_URL="${REPO_URL:-https://github.com/avazbektoxirjonovich-commits/edu_erp.git}"
BRANCH="${BRANCH:-main}"
RAILWAY_ENV="${RAILWAY_ENV:-/root/railway.env}"

ERP_USER=erp
ERP_HOME=/srv/erp
APP_DIR=$ERP_HOME/app
VENV=$ERP_HOME/venv
ENV_FILE=$ERP_HOME/.env
BACKUP_DIR=$ERP_HOME/backups

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "root sifatida ishga tushiring" >&2; exit 1; }

# .env qiymati: systemd ham, bash ham bir xil o'qishi uchun bitta qo'shtirnoqda yoziladi.
set_env() {
  local key=$1 value=$2
  if [[ $value == *"'"* ]]; then warn "$key qiymatida ' belgisi bor — qo'lda tekshiring"; fi
  { grep -v "^${key}=" "$ENV_FILE" || true; printf "%s='%s'\n" "$key" "$value"; } > "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
}

merge_railway_env() {
  local line key value
  while IFS= read -r line || [[ -n $line ]]; do
    line=${line%$'\r'}
    [[ $line =~ ^[[:space:]]*(#|$) ]] && continue
    [[ $line =~ ^(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key=${BASH_REMATCH[2]} value=${BASH_REMATCH[3]}
    case $key in
      DATABASE_URL|DATABASE_PUBLIC_URL|ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|CORS_ALLOWED_ORIGINS|\
      PORT|DJANGO_SETTINGS_MODULE|RAILWAY_*|PG*|NIXPACKS_*|RAILPACK_*)
        echo "   o'tkazildi (server o'zi beradi): $key"; continue ;;
    esac
    if [[ $value =~ ^\"(.*)\"$ || $value =~ ^\'(.*)\'$ ]]; then value=${BASH_REMATCH[1]}; fi
    if [[ $value == *'${{'* ]]; then warn "$key Railway havolasi (\${{...}}) — qo'lda to'ldiring"; continue; fi
    set_env "$key" "$value"
    echo "   ko'chirildi: $key"
  done < "$RAILWAY_ENV"
}

log "1/11 Swap (2 GB)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-erp.conf
  sysctl -q -p /etc/sysctl.d/99-erp.conf
fi

log "2/11 Tizim paketlari"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq curl ca-certificates gnupg git build-essential libpq-dev \
  nginx ufw fail2ban unattended-upgrades certbot python3-certbot-nginx \
  libgl1 libglib2.0-0 libgomp1 libsm6 libxext6 libxrender1 libxcb1 libx11-6

log "3/11 PostgreSQL $PG_VERSION (rasmiy PGDG ombori)"
if [[ ! -f /etc/apt/sources.list.d/pgdg.list ]]; then
  install -d /usr/share/postgresql-common/pgdg
  curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release; echo "$VERSION_CODENAME")-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update -q
fi
# postgresql-client — eng yangi pg_dump (Railway versiyasidan past bo'lmasligi uchun)
apt-get install -yq "postgresql-$PG_VERSION" postgresql-client

log "4/11 Firewall"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null
systemctl enable --now fail2ban >/dev/null

log "5/11 erp foydalanuvchisi va papkalar"
id "$ERP_USER" &>/dev/null || useradd --system --create-home --home-dir "$ERP_HOME" --shell /bin/bash "$ERP_USER"
usermod -aG systemd-journal "$ERP_USER"   # deploy.sh xatoda jurnalni ko'rsata olishi uchun
usermod -aG "$ERP_USER" www-data          # nginx static/media va socketni o'qiy olishi uchun
chmod 750 "$ERP_HOME"
install -d -o "$ERP_USER" -g "$ERP_USER" -m 700 "$BACKUP_DIR" "$ERP_HOME/.ssh"

log "6/11 Kod (GitHub)"
if [[ ! -d $APP_DIR/.git ]]; then
  sudo -u "$ERP_USER" git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
sudo -u "$ERP_USER" install -d -m 750 "$APP_DIR/media"

log "7/11 Baza va .env"
[[ -f $ENV_FILE ]] || install -o "$ERP_USER" -g "$ERP_USER" -m 600 /dev/null "$ENV_FILE"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='erp'" | grep -q 1; then
  sudo -u postgres psql -qc "CREATE ROLE erp LOGIN"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='erp_db'" | grep -q 1; then
  sudo -u postgres createdb -O erp erp_db
fi
if ! grep -q '^DATABASE_URL=' "$ENV_FILE"; then
  db_pass=$(openssl rand -hex 24)
  sudo -u postgres psql -qc "ALTER ROLE erp PASSWORD '$db_pass'"
  set_env DATABASE_URL "postgres://erp:${db_pass}@127.0.0.1:5432/erp_db"
fi
grep -q '^SECRET_KEY=' "$ENV_FILE" || set_env SECRET_KEY "$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9')"
set_env DJANGO_SETTINGS_MODULE config.settings.production
set_env DEBUG False
set_env ALLOWED_HOSTS "$DOMAIN"
set_env CSRF_TRUSTED_ORIGINS "https://$DOMAIN"
set_env CORS_ALLOWED_ORIGINS "https://$DOMAIN"
grep -q '^TIME_ZONE=' "$ENV_FILE" || set_env TIME_ZONE Asia/Tashkent
if [[ -f $RAILWAY_ENV ]]; then
  echo "   Railway o'zgaruvchilari: $RAILWAY_ENV"
  merge_railway_env
  shred -u "$RAILWAY_ENV"
fi
chown "$ERP_USER:$ERP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"

log "8/11 Python $PY_VERSION va kutubxonalar (birinchi marta ~10 daqiqa)"
cd "$ERP_HOME"   # uv joriy papkadan (/root) sozlama izlamasin
UV=$ERP_HOME/.local/bin/uv
[[ -x $UV ]] || sudo -u "$ERP_USER" -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' >/dev/null
[[ -x $VENV/bin/python ]] || sudo -u "$ERP_USER" -H "$UV" venv --no-config --quiet --seed --python "$PY_VERSION" "$VENV"
sudo -u "$ERP_USER" -H bash -c "cd '$APP_DIR' && '$VENV/bin/pip' install --quiet --disable-pip-version-check -r requirements.txt && sha256sum requirements.txt > '$VENV/.req.sha'"

log "9/11 systemd xizmati (gunicorn)"
cat > /etc/systemd/system/erp.service <<EOF
[Unit]
Description=ERP (Django + gunicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=$ERP_USER
Group=$ERP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
RuntimeDirectory=erp
RuntimeDirectoryMode=0750
ExecStart=$VENV/bin/gunicorn config.wsgi:application \\
    --workers 2 --threads 2 --worker-class gthread --timeout 120 \\
    --bind unix:/run/erp/gunicorn.sock --umask 007 \\
    --access-logfile - --error-logfile -
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable erp >/dev/null

cat > /etc/sudoers.d/erp-deploy <<EOF
$ERP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl reload erp, /usr/bin/systemctl restart erp
EOF
chmod 440 /etc/sudoers.d/erp-deploy
visudo -cqf /etc/sudoers.d/erp-deploy

cat > /etc/cron.d/erp-backup <<EOF
30 3 * * * $ERP_USER $APP_DIR/deploy/backup.sh >> $BACKUP_DIR/backup.log 2>&1
EOF

log "10/11 nginx"
cat > /etc/nginx/sites-available/erp <<EOF
upstream erp_app {
    server unix:/run/erp/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 25m;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://erp_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
}

# Domensiz (IP orqali) so'rovlarga javob berilmaydi
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}
EOF
ln -sf /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/erp
rm -f /etc/nginx/sites-enabled/default
nginx -t -q
systemctl restart nginx

log "11/11 HTTPS (Let's Encrypt)"
public_ip=$(curl -fsS --max-time 5 http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address || true)
domain_ip=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
if [[ -n $public_ip && $public_ip == "$domain_ip" ]]; then
  if [[ -n $EMAIL ]]; then email_opt=(-m "$EMAIL"); else email_opt=(--register-unsafely-without-email); fi
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect "${email_opt[@]}"
else
  warn "$DOMAIN hali bu serverga ($public_ip) qaramayapti (hozir: ${domain_ip:-topilmadi})."
  warn "DNS A yozuvini qo'shib, shu skriptni qayta ishga tushiring — sertifikat shunda olinadi."
fi

log "Tayyor. Keyingi qadamlar:"
cat <<EOF
  1) Bazani ko'chirish:   bash $APP_DIR/deploy/migrate_from_railway.sh
  2) Ishga tushirish:     sudo -u $ERP_USER $APP_DIR/deploy/deploy.sh
  3) .env ni tekshirish:  sudo -u $ERP_USER nano $ENV_FILE
EOF
