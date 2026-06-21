import os
import matplotlib
matplotlib.use('Agg')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pensiones.settings')

application = get_wsgi_application()