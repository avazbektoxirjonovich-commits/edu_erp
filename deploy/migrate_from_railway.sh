#!/usr/bin/env bash
# Railway Postgres → shu serverdagi Postgres. Root sifatida:
#   bash /srv/erp/app/deploy/migrate_from_railway.sh
# Railway ulanish manzili (DATABASE_PUBLIC_URL) so'raladi: ekranda ko'rinmaydi, faylga yozilmaydi.
# Railway bazasi faqat o'qiladi, unga hech narsa yozilmaydi.
set -euo pipefail

ERP_HOME=/srv/erp
ENV_FILE=$ERP_HOME/.env
BACKUP_DIR=$ERP_HOME/backups

[[ $EUID -eq 0 ]] || { echo "root sifatida ishga tushiring" >&2; exit 1; }

# ASSUME_YES=1 — savollarsiz (masalan, manzil stdin orqali uzatilganda)
confirm() {
  [[ ${ASSUME_YES:-} == 1 ]] && return 0
  local ans; read -rp "$1 (ha/yo'q): " ans < /dev/tty; [[ $ans == ha ]]
}

DST_URL=$(sudo -u erp bash -c "set -a; . '$ENV_FILE'; printf %s \"\$DATABASE_URL\"")
[[ -n $DST_URL ]] || { echo "$ENV_FILE da DATABASE_URL yo'q — avval server_setup.sh" >&2; exit 1; }

SRC_URL="${RAILWAY_DATABASE_URL:-}"
if [[ -z $SRC_URL ]]; then
  read -rsp "Railway DATABASE_PUBLIC_URL (postgresql://...): " SRC_URL; echo
fi
[[ $SRC_URL =~ ^postgres(ql)?:// ]] || { echo "Manzil postgresql:// bilan boshlanishi kerak" >&2; exit 1; }

major() { psql "$1" -tAXc 'SHOW server_version_num' | awk '{print int($1/10000)}'; }
src_major=$(major "$SRC_URL")
dst_major=$(major "$DST_URL")
cli_major=$(pg_dump --version | grep -oE '[0-9]+' | head -1)
echo "Postgres versiyalari: Railway $src_major, server $dst_major, pg_dump $cli_major"
(( cli_major >= src_major )) || { echo "pg_dump ($cli_major) Railway'dan ($src_major) eski" >&2; exit 1; }
if (( src_major > dst_major )); then
  echo "DIQQAT: server Postgres'i Railway'dan eski. PG_VERSION=$src_major bilan server_setup.sh ni qayta ishga tushirish tavsiya qilinadi." >&2
  confirm "Baribir davom etilsinmi?" || exit 1
fi

tables=$(psql "$DST_URL" -tAXc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if (( tables > 0 )); then
  echo "Server bazasida $tables ta jadval bor — ular o'chirilib, Railway nusxasi bilan almashtiriladi."
  confirm "Davom etilsinmi?" || exit 1
fi

if systemctl is-active --quiet erp; then
  echo "erp xizmati to'xtatilmoqda (tiklash paytida yozuv bo'lmasin)"
  systemctl stop erp
fi

dump="$BACKUP_DIR/railway-$(date +%Y%m%d-%H%M%S).dump"
echo "==> Railway'dan nusxa olinmoqda → $dump"
pg_dump --format=custom --no-owner --no-acl --file="$dump" "$SRC_URL"
chown erp:erp "$dump"
chmod 600 "$dump"
ls -lh "$dump"

echo "==> Serverga tiklanmoqda"
pg_restore --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error \
  --dbname="$DST_URL" "$dump"

echo "==> Tekshiruv: har bir jadvaldagi qatorlar soni"
count_sql="SELECT table_name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text
FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"
src_counts=$(psql "$SRC_URL" -tAXF ' ' -c "$count_sql")
dst_counts=$(psql "$DST_URL" -tAXF ' ' -c "$count_sql")
if diff <(echo "$src_counts") <(echo "$dst_counts") >/dev/null; then
  echo "OK — $(echo "$dst_counts" | wc -l) ta jadval, qatorlar soni bir xil"
  echo "$dst_counts" | sort -k2 -nr | head -10 | awk '{printf "   %-40s %s\n", $1, $2}'
else
  echo "FARQ BOR (chap — Railway, o'ng — server):" >&2
  diff <(echo "$src_counts") <(echo "$dst_counts") >&2 || true
  exit 1
fi

echo
echo "Keyingi qadam: sudo -u erp $ERP_HOME/app/deploy/deploy.sh"
