#!/usr/bin/env bash
# GitHub Actions → server deploy ulanishini sozlaydi. O'z kompyuteringizdan (Git Bash), bir marta:
#   bash deploy/local/connect_github.sh 159.65.113.126
# Talab: server_setup.sh bajarilgan, `gh auth status` muvaffaqiyatli.
#
# Alohida deploy kaliti yaratiladi. Serverda u faqat deploy.sh ni ishga tushira oladi
# (forced command + restrict): shell, port forwarding va boshqa buyruqlar yopiq.
set -euo pipefail

HOST="${1:?Server IP manzilini bering}"
REPO="${REPO:-avazbektoxirjonovich-commits/edu_erp}"
ADMIN_KEY="${ADMIN_KEY:-$HOME/.ssh/id_ed25519}"
KEY="$HOME/.ssh/erp_github_deploy"

[[ -f $KEY ]] || ssh-keygen -q -t ed25519 -N '' -C 'github-actions-erp-deploy' -f "$KEY"
pub=$(cat "$KEY.pub")

echo "==> Deploy kaliti serverga (erp foydalanuvchisi, faqat deploy.sh)"
ssh -i "$ADMIN_KEY" -o BatchMode=yes "root@$HOST" "bash -s -- '$pub'" <<'REMOTE'
set -euo pipefail
pub="$1"
f=/srv/erp/.ssh/authorized_keys
install -d -o erp -g erp -m 700 /srv/erp/.ssh
touch "$f"
chown erp:erp "$f"
chmod 600 "$f"
body=$(awk '{print $2}' <<<"$pub")
grep -qF "$body" "$f" || echo "command=\"/srv/erp/app/deploy/deploy.sh\",restrict $pub" >> "$f"
echo "   o'rnatildi"
REMOTE

known=$(ssh-keygen -F "$HOST" | grep -v '^#' || true)
[[ -n $known ]] || known=$(ssh-keyscan -t ed25519 "$HOST" 2>/dev/null)

echo "==> GitHub secrets ($REPO)"
gh secret set DEPLOY_HOST --repo "$REPO" --body "$HOST"
gh secret set DEPLOY_KNOWN_HOSTS --repo "$REPO" --body "$known"
gh secret set DEPLOY_SSH_KEY --repo "$REPO" < "$KEY"

echo "Tayyor. Endi main'ga har push serverga chiqadi (Actions → Deploy)."
