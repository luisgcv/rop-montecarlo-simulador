# interfaz/views.py
import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")   # sin interfaz gráfica (servidor)
import matplotlib.pyplot as plt

from django.shortcuts import render, redirect
from datos.cargador import (
    cargar_rendimientos, cargar_comisiones, listar_operadoras
)
from simulador.motor import estimar_parametros, simular, calcular_estadisticos


# ── Colores institucionales UCR ──────────────────────────────────────────────
COLOR_PESIMISTA = "#D32F2F"
COLOR_ESPERADO  = "#006699"
COLOR_OPTIMISTA = "#2E7D32"
COLOR_UMBRAL    = "#00ABE8"


def _figura_a_base64(fig):
    """Convierte una figura Matplotlib a string base64 para incrustar en HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    imagen = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return imagen


# ── PANTALLA 1: Configuración de perfil ──────────────────────────────────────

def configurar_perfil(request):
    operadoras = listar_operadoras()
    error      = request.session.pop("error", None)   # leer y limpiar el error

    if request.method == "POST":
        request.session["perfil"] = {
            "salario":     float(request.POST["salario"]),
            "edad":        int(request.POST["edad"]),
            "edad_retiro": int(request.POST["edad_retiro"]),
            "saldo":       float(request.POST["saldo"]),
            "operadora":   request.POST["operadora"],
            "densidad":    float(request.POST["densidad"]) / 100,
            "umbral":      float(request.POST.get("umbral", 0) or 0),
        }
        return redirect("ejecutar_simulacion")

    return render(request, "configurar_perfil.html", {
        "operadoras": operadoras,
        "error":      error,
    })


# ── PANTALLA 2: Ejecución de la simulación ───────────────────────────────────

def ejecutar_simulacion(request):
    perfil = request.session.get("perfil")
    if not perfil:
        return redirect("configurar_perfil")

    try:
        df_rend    = cargar_rendimientos()
        comisiones = cargar_comisiones()

        # Obtener rentabilidades de la operadora seleccionada
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

        # Saldos finales limpios de NaN/Inf para serializar a sesión
        saldos_limpios = [float(x) for x in stats["saldos_finales"] if np.isfinite(x)]

        # Muestra de 100 trayectorias (limpias de NaN para graficar)
        idx_muestra  = np.random.choice(S.shape[0], min(100, S.shape[0]), replace=False)
        trayectorias = [
            [float(v) for v in fila] for fila in S[idx_muestra, :]
        ]

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

    return redirect("mostrar_resultados")


# ── PANTALLA 3: Análisis de resultados ───────────────────────────────────────

def mostrar_resultados(request):
    resultados = request.session.get("resultados")
    perfil     = request.session.get("perfil")

    if not resultados or not perfil:
        return redirect("configurar_perfil")

    # Limpiar NaN del array de saldos antes de graficar
    saldos_raw = np.array(resultados["saldos_finales"], dtype=float)
    saldos     = saldos_raw[np.isfinite(saldos_raw)]

    if len(saldos) == 0:
        request.session["error"] = "Los resultados de la simulación no son válidos. Intente nuevamente."
        return redirect("configurar_perfil")

    trayectorias = np.array(resultados["trayectorias"], dtype=float)

    # ── Gráfico 1: Histograma de saldos finales ──────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.hist(saldos / 1e6, bins=60, color="#AECCE8", edgecolor="white", alpha=0.85)
    ax1.axvline(resultados["p5"]  / 1e6, color=COLOR_PESIMISTA, linewidth=2, label=f'P5  ₡{resultados["p5"]/1e6:.1f}M')
    ax1.axvline(resultados["p50"] / 1e6, color=COLOR_ESPERADO,  linewidth=2, label=f'P50 ₡{resultados["p50"]/1e6:.1f}M')
    ax1.axvline(resultados["p95"] / 1e6, color=COLOR_OPTIMISTA, linewidth=2, label=f'P95 ₡{resultados["p95"]/1e6:.1f}M')
    if perfil["umbral"] > 0:
        ax1.axvline(perfil["umbral"] / 1e6, color=COLOR_UMBRAL, linewidth=2, linestyle="--",
                    label=f'Umbral ₡{perfil["umbral"]/1e6:.1f}M')
    ax1.set_xlabel("Saldo al retiro (millones ₡)")
    ax1.set_ylabel("Frecuencia")
    ax1.set_title("Distribución de saldos finales — 10 000 escenarios")
    ax1.legend(fontsize=9)
    fig1.tight_layout()
    grafico_histograma = _figura_a_base64(fig1)

    # ── Gráfico 2: Trayectorias del fondo ────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    for tray in trayectorias:
        ax2.plot(tray / 1e6, color="gray", alpha=0.08, linewidth=0.7)
    mediana = np.median(trayectorias, axis=0)
    ax2.plot(mediana / 1e6, color=COLOR_ESPERADO, linewidth=2.5, label="Mediana (P50)")
    ax2.set_xlabel("Meses desde hoy")
    ax2.set_ylabel("Saldo (millones ₡)")
    ax2.set_title("Evolución del fondo — 100 trayectorias de muestra")
    ax2.legend(fontsize=9)
    fig2.tight_layout()
    grafico_trayectorias = _figura_a_base64(fig2)

    return render(request, "resultados.html", {
        "perfil":               perfil,
        "r":                    resultados,
        "grafico_histograma":   grafico_histograma,
        "grafico_trayectorias": grafico_trayectorias,
    })
