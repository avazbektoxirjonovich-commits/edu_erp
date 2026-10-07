# DigitalOcean'ga deploy

Server: Ubuntu 24.04, `nginx → gunicorn (unix socket) → Django`, Postgres shu serverda.
`main`'ga push → GitHub Actions → SSH → `deploy/deploy.sh`.

| Fayl | Qayerda, kim | Vazifasi |
|---|---|---|
| `server_setup.sh` | server, root, bir marta | swap, paketlar, Postgres, firewall, `erp` foydalanuvchisi, venv, systemd, nginx, HTTPS, kunlik zaxira |
| `migrate_from_railway.sh` | server, root | Railway bazasini nusxalab tiklaydi va qatorlar sonini solishtiradi |
| `deploy.sh` | server, `erp` | kod → kutubxonalar → baza zaxirasi → migrate → static → reload → `/login/` tekshiruvi |
| `backup.sh` | server, cron 03:30 | baza + media, 14 kun |
| `local/connect_github.sh` | o'z kompyuteringiz | deploy kaliti + GitHub secrets |

## Birinchi o'rnatish

```bash
# 1. Server (root)
scp deploy/server_setup.sh root@SERVER:/root/
ssh root@SERVER 'DOMAIN=erp.example.uz EMAIL=siz@example.uz bash /root/server_setup.sh'

# 2. Baza (root, Railway DATABASE_PUBLIC_URL so'raladi)
ssh -t root@SERVER bash /srv/erp/app/deploy/migrate_from_railway.sh

# 3. Ishga tushirish
ssh root@SERVER sudo -u erp /srv/erp/app/deploy/deploy.sh

# 4. GitHub → server (o'z kompyuteringizdan, Git Bash)
bash deploy/local/connect_github.sh SERVER
```

Railway o'zgaruvchilari (SECRET_KEY, ANTHROPIC_API_KEY, CLOUDINARY_*, PUBLIC_SITE_ORIGIN, ...):
Railway → Variables → Raw Editor matnini serverda `/root/railway.env` ga saqlab, `server_setup.sh` ni
qayta ishga tushiring — qiymatlar `/srv/erp/.env` ga qo'shiladi, fayl o'chiriladi.
`SECRET_KEY` Railway'dagi bilan bir xil bo'lsa, foydalanuvchilar qayta kirishi shart emas.

## Kundalik

- Deploy: `main`'ga push (yoki Actions → Deploy → Run workflow).
- Orqaga qaytarish: `ssh root@SERVER sudo -u erp /srv/erp/app/deploy/deploy.sh <eski-commit>`
- Loglar: `ssh root@SERVER journalctl -u erp -f`
- Zaxiralar: `/srv/erp/backups/` (`pre-deploy-*` — har deploydan oldin, `daily-*` — har kuni).
  Bazani zaxiradan tiklash: `pg_restore --clean --if-exists --no-owner -d "$DATABASE_URL" <fayl>.dump`
