# interfaz/views.py
# Controladores del flujo de tres pantallas:
#   1. configurar_perfil   → el usuario ingresa su perfil
#   2. ejecutar_simulacion → se corre el Monte Carlo y se muestra el progreso
#   3. mostrar_resultados  → se presentan los estadísticos y gráficos
#
# El estado entre pantallas viaja en la sesión de Django (request.session),
# de modo que no es necesario guardar nada en base de datos.
# La generación de gráficos está delegada completamente a graficos.py.

import json
import numpy as np
from datetime import datetime

from django.shortcuts import render, redirect
from django.urls import reverse

from datos.cargador import cargar_rendimientos, cargar_comisiones, listar_operadoras
from simulador.motor import estimar_parametros, simular, calcular_estadisticos
from interfaz.graficos import generar_preview, generar_histograma, generar_trayectorias


# ── PANTALLA 1: Configuración del perfil ─────────────────────────────────────
# Muestra el formulario y, una vez recibido el POST, guarda el perfil en sesión
# y redirige a la pantalla de ejecución.
#
# También precalcula mu, sigma y comisión de cada operadora en JSON para que
# el resumen dinámico de la página se actualice en tiempo real con JavaScript,
# sin necesidad de hacer peticiones adicionales al servidor.

def configurar_perfil(request):
    operadoras = listar_operadoras()
    error      = request.session.pop("error", None)

    df_rend    = cargar_rendimientos()
    comisiones = cargar_comisiones()
    params_data = {}
    for op in operadoras:
        datos_op = df_rend[df_rend["entidad"] == op]["rentabilidad"].dropna().values
        if len(datos_op) > 0:
            try:
                p = estimar_parametros(datos_op)
                c = comisiones.get(op, 0.01)
                params_data[op] = {
                    "mu":       round(p["mu"] * 100, 2),
                    "sigma":    round(p["sigma"] * 100, 2),
                    "n_obs":    p["n_obs"],
                    "comision": round(c * 100, 2),
                }
            except ValueError:
                params_data[op] = None

    if request.method == "POST":
        request.session["perfil"] = {
            "salario":     float(request.POST["salario"]),
            "edad":        int(request.POST["edad"]),
            "edad_retiro": int(request.POST["edad_retiro"]),
            "saldo":       float(request.POST["saldo"]),
            "operadora":   request.POST["operadora"],
            "densidad":    float(request.POST["densidad"]) / 100,   # % → decimal
            "umbral":      float(request.POST.get("umbral", 0) or 0),
        }
        return redirect("ejecutar_simulacion")

    return render(request, "configurar_perfil.html", {
        "operadoras":  operadoras,
        "error":       error,
        "params_json": json.dumps(params_data),
    })


# ── PANTALLA 2: Ejecución de la simulación ───────────────────────────────────
# Corre el Monte Carlo completo (10 000 trayectorias), guarda los resultados en
# sesión, genera un gráfico de vista previa y redirige automáticamente a la
# pantalla de resultados con una meta-refresh de 2 segundos.

def ejecutar_simulacion(request):
    perfil = request.session.get("perfil")
    if not perfil:
        return redirect("configurar_perfil")

    try:
        df_rend    = cargar_rendimientos()
        comisiones = cargar_comisiones()

        datos_op = df_rend[df_rend["entidad"] == perfil["operadora"]]["rentabilidad"].dropna().values

        if len(datos_op) == 0:
            entidades_disponibles = sorted(df_rend["entidad"].unique().tolist())
            request.session["error"] = (
                f"No se encontraron datos para '{perfil['operadora']}'. "
                f"Operadoras disponibles: {', '.join(entidades_disponibles)}"
            )
            return redirect("configurar_perfil")

        params   = estimar_parametros(datos_op)
        comision = comisiones.get(perfil["operadora"], 0.01)
        meses    = (perfil["edad_retiro"] - perfil["edad"]) * 12

        S = simular(
            saldo_inicial  = perfil["saldo"],
            salario_bruto  = perfil["salario"],
            meses          = meses,
            mu             = params["mu"],
            sigma          = params["sigma"],
            comision_anual = comision,
            densidad       = perfil["densidad"],
            n              = 10_000,
        )

        anios = perfil["edad_retiro"] - perfil["edad"]
        stats = calcular_estadisticos(S, umbral=perfil["umbral"], anios=anios)

        # Serializar solo los datos que necesita la pantalla de resultados
        saldos_limpios = [float(x) for x in stats["saldos_finales"] if np.isfinite(x)]
        idx_muestra    = np.random.choice(S.shape[0], min(100, S.shape[0]), replace=False)
        trayectorias   = [[float(v) for v in fila] for fila in S[idx_muestra, :]]

        request.session["resultados"] = {
            "p5":             stats["p5"],
            "p25":            stats["p25"],
            "p50":            stats["p50"],
            "p75":            stats["p75"],
            "p95":            stats["p95"],
            "p50_real":       stats["p50_real"],
            "prob_exito":     stats["prob_exito"],
            "mu":             round(params["mu"] * 100, 2),
            "sigma":          round(params["sigma"] * 100, 2),
            "n_obs":          params["n_obs"],
            "meses":          meses,
            "comision":       round(comision * 100, 2),
            "saldos_finales": saldos_limpios,
            "trayectorias":   trayectorias,
        }

    except ValueError as e:
        request.session["error"] = str(e)
        return redirect("configurar_perfil")

    return render(request, "ejecucion_simulacion.html", {
        "perfil":          perfil,
        "mu":              round(params["mu"] * 100, 2),
        "sigma":           round(params["sigma"] * 100, 2),
        "comision":        round(comision * 100, 2),
        "meses":           meses,
        "anios":           meses // 12,   # los templates muestran años, no meses
        "n_obs":           params["n_obs"],
        "grafico_preview": generar_preview(S, meses),
        "redirect_url":    reverse("mostrar_resultados"),
    })


# ── PANTALLA 3: Análisis de resultados ───────────────────────────────────────
# Recupera los resultados de la sesión y genera los dos gráficos finales
# llamando a graficos.py. Los gráficos llegan al template como cadenas base64.

def mostrar_resultados(request):
    resultados = request.session.get("resultados")
    perfil     = request.session.get("perfil")

    if not resultados or not perfil:
        return redirect("configurar_perfil")

    saldos_raw = np.array(resultados["saldos_finales"], dtype=float)
    saldos     = saldos_raw[np.isfinite(saldos_raw)]

    if len(saldos) == 0:
        request.session["error"] = "Los resultados de la simulación no son válidos. Intente nuevamente."
        return redirect("configurar_perfil")

    trayectorias = np.array(resultados["trayectorias"], dtype=float)

    _meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                 7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    now = datetime.now()
    ultima_simulacion = f"{now.day} {_meses_es[now.month]} {now.year} – {now.strftime('%H:%M')}"

    def _m(val):
        return f"{val/1e6:.1f}".replace(".", ",")

    return render(request, "resultados.html", {
        "perfil":               perfil,
        "r":                    resultados,
        "grafico_histograma":   generar_histograma(saldos, resultados, perfil["umbral"]),
        "grafico_trayectorias": generar_trayectorias(trayectorias, resultados["meses"]),
        "p5_m":              _m(resultados["p5"]),
        "p25_m":             _m(resultados["p25"]),
        "p50_m":             _m(resultados["p50"]),
        "p75_m":             _m(resultados["p75"]),
        "p95_m":             _m(resultados["p95"]),
        "p50_real_m":        _m(resultados["p50_real"]),
        "umbral_m":          _m(perfil["umbral"]) if perfil["umbral"] > 0 else None,
        "anio_retiro":       perfil["edad_retiro"],
        "anios_retiro":      perfil["edad_retiro"] - perfil["edad"],
        "densidad_pct":      round(perfil["densidad"] * 100),
        "ultima_simulacion": ultima_simulacion,
    })
