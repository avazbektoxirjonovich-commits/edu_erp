#!/usr/bin/env bash
# Kunlik zaxira (cron, erp foydalanuvchisi, 03:30): baza + media, KEEP_DAYS kun saqlanadi.
# Qo'lda: sudo -u erp /srv/erp/app/deploy/backup.sh
set -euo pipefail

ERP_HOME=/srv/erp
BACKUP_DIR=$ERP_HOME/backups
MEDIA_DIR=$ERP_HOME/app/media
KEEP_DAYS=${KEEP_DAYS:-14}

set -a; . "$ERP_HOME/.env"; set +a
ts=$(date +%Y%m%d-%H%M)

pg_dump --format=custom --file="$BACKUP_DIR/daily-$ts.dump" "$DATABASE_URL"
if [[ -d $MEDIA_DIR && -n $(ls -A "$MEDIA_DIR") ]]; then
  tar -czf "$BACKUP_DIR/media-$ts.tar.gz" -C "$ERP_HOME/app" media
fi
find "$BACKUP_DIR" -maxdepth 1 \( -name 'daily-*.dump' -o -name 'media-*.tar.gz' \) -mtime "+$KEEP_DAYS" -delete

echo "$(date -Is) ok daily-$ts"
