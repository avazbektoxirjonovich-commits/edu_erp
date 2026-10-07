#!/usr/bin/env bash
# ERP'ni yangilash: kod → kutubxonalar → baza zaxirasi → migrate → static → qayta yuklash → tekshiruv.
# Serverda erp foydalanuvchisi sifatida:
#   sudo -u erp /srv/erp/app/deploy/deploy.sh             # origin/main
#   sudo -u erp /srv/erp/app/deploy/deploy.sh <commit>    # aniq commit (orqaga qaytarish ham shu)
# GitHub Actions bu skriptni SSH forced-command orqali chaqiradi: commit SSH_ORIGINAL_COMMAND da keladi.
set -euo pipefail

ERP_HOME=/srv/erp
APP_DIR=$ERP_HOME/app
VENV=$ERP_HOME/venv
ENV_FILE=$ERP_HOME/.env
BACKUP_DIR=$ERP_HOME/backups
SOCKET=/run/erp/gunicorn.sock
KEEP_DUMPS=20

step() { printf '\n==> %s\n' "$*"; }

health_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 --unix-socket "$SOCKET" \
    -H "Host: $1" -H 'X-Forwarded-Proto: https' http://localhost/login/ || true
}

# Butun mantiq funksiya ichida: git reset shu faylni almashtirsa ham bash eski nusxani bajaradi.
main() {
  local ref="${1:-${SSH_ORIGINAL_COMMAND:-}}"
  ref="${ref:-origin/main}"
  if [[ ! $ref =~ ^([0-9a-f]{7,40}|origin/main)$ ]]; then
    echo "Noto'g'ri ref: '$ref' (commit hash yoki origin/main bo'lishi kerak)" >&2
    exit 2
  fi
  [[ $(id -un) == erp ]] || { echo "erp sifatida ishga tushiring: sudo -u erp $0" >&2; exit 1; }

  exec 9>"$ERP_HOME/.deploy.lock"
  flock -n 9 || { echo "Boshqa deploy ketyapti" >&2; exit 1; }

  set -a; . "$ENV_FILE"; set +a
  local host=${ALLOWED_HOSTS%%,*}
  cd "$APP_DIR"

  local old new
  old=$(git rev-parse HEAD)
  git fetch --quiet --prune origin
  new=$(git rev-parse --verify --quiet "${ref}^{commit}") || { echo "Commit topilmadi: $ref" >&2; exit 2; }
  git merge-base --is-ancestor "$new" origin/main || { echo "$new main tarixida yo'q" >&2; exit 2; }
  step "Kod: ${old:0:7} → ${new:0:7}"
  git reset --hard --quiet "$new"

  if ! sha256sum --status -c "$VENV/.req.sha" 2>/dev/null; then
    step "Kutubxonalar (requirements.txt o'zgargan)"
    "$VENV/bin/pip" install --quiet --disable-pip-version-check -r requirements.txt
    sha256sum requirements.txt > "$VENV/.req.sha"
  fi

  step "Baza zaxirasi"
  local dump="$BACKUP_DIR/pre-deploy-$(date +%Y%m%d-%H%M%S)-${new:0:7}.dump"
  pg_dump --format=custom --file="$dump" "$DATABASE_URL"
  echo "   $dump"
  ls -1t "$BACKUP_DIR"/pre-deploy-*.dump | tail -n +$((KEEP_DUMPS + 1)) | xargs -r rm --

  step "Migratsiya"
  "$VENV/bin/python" manage.py migrate --noinput

  step "Static fayllar"
  "$VENV/bin/python" manage.py collectstatic --noinput --verbosity 0
  "$VENV/bin/python" manage.py check

  step "Qayta yuklash"
  if systemctl is-active --quiet erp; then sudo /usr/bin/systemctl reload erp; else sudo /usr/bin/systemctl restart erp; fi

  step "Tekshiruv: https://$host/login/"
  local code=""
  for _ in $(seq 1 20); do
    sleep 2
    code=$(health_code "$host")
    [[ $code == 200 ]] && break
  done
  if [[ $code != 200 ]]; then
    echo "XATO: /login/ javobi $code" >&2
    journalctl -u erp -n 40 --no-pager >&2 || true
    echo "Orqaga qaytarish: sudo -u erp $APP_DIR/deploy/deploy.sh $old" >&2
    echo "Baza zaxirasi:    $dump" >&2
    exit 1
  fi
  echo "OK — ${new:0:7} ishlayapti"
}

main "$@"
