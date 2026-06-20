#!/usr/bin/env python
# manage.py — Utilidad de línea de comandos de Django.
# Uso habitual: python manage.py runserver

import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_pensiones.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. Asegúrate de que esté instalado y de "
            "que el entorno virtual esté activado."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
