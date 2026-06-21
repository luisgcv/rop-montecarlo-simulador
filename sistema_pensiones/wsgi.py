"""
WSGI config for sistema_pensiones project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

import matplotlib
matplotlib.use('Agg')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pensiones.settings')

application = get_wsgi_application()
