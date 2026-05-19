# ============================================================
#  WSGI - Web Server Gateway Interface
#  Nginx + Gunicorn uchun kirish nuqtasi
# ============================================================

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_wsgi_application()
