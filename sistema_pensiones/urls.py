# sistema_pensiones/urls.py
# Tabla de rutas del proyecto. Las tres URLs corresponden al flujo de
# tres pantallas del simulador: configuración → ejecución → resultados.

from django.urls import path
from interfaz import views

urlpatterns = [
    path('',                    views.configurar_perfil,    name='configurar_perfil'),
    path('ejecutar_simulacion/', views.ejecutar_simulacion, name='ejecutar_simulacion'),
    path('mostrar_resultados/',  views.mostrar_resultados,  name='mostrar_resultados'),
]
