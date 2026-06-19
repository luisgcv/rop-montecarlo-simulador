# sistema_pensiones/wsgi.py
# Punto de entrada WSGI para servidores de producción (Gunicorn, uWSGI, etc.).
# En desarrollo se usa "python manage.py runserver" y este archivo no se invoca.

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pensiones.settings')

application = get_wsgi_application()
