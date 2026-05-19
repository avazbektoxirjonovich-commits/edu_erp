# EduERP — Server o'rnatish (VPS)

## Talablar
- Ubuntu 22.04 LTS
- Python 3.11+
- PostgreSQL 15+
- Nginx
- Gunicorn

---

## 1. PostgreSQL

```bash
sudo apt install postgresql postgresql-contrib
sudo -u postgres psql

CREATE DATABASE erp_db;
CREATE USER erp_user WITH PASSWORD 'kuchli_parol';
GRANT ALL PRIVILEGES ON DATABASE erp_db TO erp_user;
ALTER DATABASE erp_db OWNER TO erp_user;
\q
```

---

## 2. Loyihani serverga ko'chirish

```bash
git clone https://github.com/yourname/erp_system.git /home/ubuntu/erp
cd /home/ubuntu/erp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Sozlamalarni kiriting
```

---

## 3. Django sozlash

```bash
python manage.py migrate --settings=config.settings.production
python manage.py createsuperuser --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production
```

---

## 4. Gunicorn systemd service

```bash
sudo nano /etc/systemd/system/erp.service
```

```ini
[Unit]
Description=EduERP Django Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/erp
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/home/ubuntu/erp/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/ubuntu/erp/erp.sock \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable erp
sudo systemctl start erp
```

---

## 5. Nginx sozlash

```bash
sudo nano /etc/nginx/sites-available/erp
```

```nginx
server {
    listen 80;
    server_name your-domain.uz;

    location /static/ {
        alias /home/ubuntu/erp/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/erp/media/;
    }

    location / {
        proxy_pass http://unix:/home/ubuntu/erp/erp.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 6. SSL (HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.uz
```
