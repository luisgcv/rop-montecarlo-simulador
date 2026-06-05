"""
URL configuration for sistema_pensiones project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from interfaz import views

urlpatterns = [
    path('',views.configurar_perfil,name="configurar_perfil"),
    path('ejecutar_simulacion/',views.ejecutar_simulacion,name="ejecutar_simulacion"),
    path('mostrar_resultados/',views.mostrar_resultados,name="mostrar_resultados"),
]
