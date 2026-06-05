from django.shortcuts import render


# Create your views here.


## Vista para configurar el perfil del usuario
def configurar_perfil(request):
    return render(request, 'configurar_perfil.html');

## Vista para ejecutar la simulación
def ejecutar_simulacion(request):
    return render(request, 'ejecucion_simulacion.html');


## Vista para mostrar los resultados de la simulación
def mostrar_resultados(request):
    return render(request, 'resultados.html');


