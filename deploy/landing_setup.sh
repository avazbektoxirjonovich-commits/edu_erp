#!/usr/bin/env bash
# Landing sayt (qorakolilmziyo-musobaqa repo) shu serverda: qorakolilmziyo.uz, www → asosiy domen.
# Root sifatida, server_setup.sh dan keyin:
#   bash landing_setup.sh             # tayyorlash: clone, avtomat yangilash, nginx sozlamasi
#   ENABLE=1 bash landing_setup.sh    # nginx'ni landing'ga o'tkazish
# Talab: /srv/erp/.ssh/config da `github-site` (repo'ga read-only deploy key).
set -euo pipefail

DOMAIN="${DOMAIN:-qorakolilmziyo.uz}"
ERP_DOMAIN="${ERP_DOMAIN:-erp.qorakolilmziyo.uz}"
REPO="${REPO:-git@github-site:avazbektoxirjonovich-commits/qorakolilmziyo-musobaqa.git}"
SITE_DIR=/srv/erp/site
CERT=/etc/letsencrypt/live/$DOMAIN

[[ $EUID -eq 0 ]] || { echo "root sifatida ishga tushiring" >&2; exit 1; }

echo "==> Repo: $SITE_DIR"
[[ -d $SITE_DIR/.git ]] || sudo -u erp -H git clone --quiet "$REPO" "$SITE_DIR"
sudo -u erp -H git -C "$SITE_DIR" log --oneline -1

echo "==> Avtomat yangilash (har daqiqa origin/main)"
cat > /etc/systemd/system/erp-site-pull.service <<EOF
[Unit]
Description=Landing saytni GitHub'dan yangilash

[Service]
Type=oneshot
User=erp
WorkingDirectory=$SITE_DIR
ExecStart=/bin/sh -c 'git fetch --quiet origin main && git reset --quiet --hard origin/main'
EOF
cat > /etc/systemd/system/erp-site-pull.timer <<'EOF'
[Unit]
Description=Landing saytni har daqiqa yangilash

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now erp-site-pull.timer >/dev/null

echo "==> nginx sozlamasi"
# _headers (Cloudflare) bilan bir xil; add_header location ichida meros olinmaydi, shuning uchun snippet
cat > /etc/nginx/snippets/landing-headers.conf <<EOF
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-Frame-Options "DENY" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://$ERP_DOMAIN; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" always;
EOF
cat > /etc/nginx/sites-available/landing <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;
    # location ichida: certbot yangilashda acme-challenge location qo'sha olishi uchun
    location / {
        return 301 https://$DOMAIN\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.$DOMAIN;
    ssl_certificate $CERT/fullchain.pem;
    ssl_certificate_key $CERT/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    return 301 https://$DOMAIN\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;
    ssl_certificate $CERT/fullchain.pem;
    ssl_certificate_key $CERT/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root $SITE_DIR;

    # Faqat index.html va assets/ chiqadi (README, .git va b. emas)
    location = / {
        include snippets/landing-headers.conf;
        add_header Cache-Control "no-cache" always;
        try_files /index.html =404;
    }
    location = /index.html {
        include snippets/landing-headers.conf;
        add_header Cache-Control "no-cache" always;
    }
    location /assets/ {
        include snippets/landing-headers.conf;
        add_header Cache-Control "public, max-age=86400" always;
        try_files \$uri =404;
    }
    # Qolgan yo'llar — eski www havolalari (Railway davridagi ERP): /login/, /students/ ...
    location / {
        return 302 https://$ERP_DOMAIN\$request_uri;
    }
}
EOF

if [[ ${ENABLE:-} == 1 ]]; then
  echo "==> nginx landing'ga o'tkazilmoqda"
  rm -f /etc/nginx/sites-enabled/erp-redirect
  ln -sf /etc/nginx/sites-available/landing /etc/nginx/sites-enabled/landing
  nginx -t -q
  systemctl reload nginx
  echo "Tayyor: https://$DOMAIN"
else
  echo "Tayyorlandi. Yoqish: ENABLE=1 bash $0"
fi
