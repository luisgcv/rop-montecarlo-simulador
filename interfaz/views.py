# interfaz/views.py
import io
import json
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

from django.shortcuts import render, redirect
from django.urls import reverse
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
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    imagen = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return imagen


# ── PANTALLA 1: Configuración de perfil ──────────────────────────────────────

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
            "densidad":    float(request.POST["densidad"]) / 100,
            "umbral":      float(request.POST.get("umbral", 0) or 0),
        }
        return redirect("ejecutar_simulacion")

    return render(request, "configurar_perfil.html", {
        "operadoras":  operadoras,
        "error":       error,
        "params_json": json.dumps(params_data),
    })


# ── PANTALLA 2: Ejecución de la simulación ───────────────────────────────────

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

    # ── Mini preview chart ────────────────────────────────────────────────────
    idx_prev = np.random.choice(S.shape[0], min(25, S.shape[0]), replace=False)
    fig_prev, ax_prev = plt.subplots(figsize=(4.5, 2.5))
    fig_prev.patch.set_facecolor("white")
    ax_prev.set_facecolor("#FAFCFF")
    for i in idx_prev:
        ax_prev.plot(S[i, :] / 1e6, color="#B0C8DC", alpha=0.4, linewidth=0.7, zorder=1)
    p5_t  = np.percentile(S, 5,  axis=0)
    p50_t = np.percentile(S, 50, axis=0)
    p95_t = np.percentile(S, 95, axis=0)
    ax_prev.plot(p5_t  / 1e6, color=COLOR_PESIMISTA, linewidth=1.5, zorder=3)
    ax_prev.plot(p50_t / 1e6, color=COLOR_ESPERADO,  linewidth=2.2, zorder=4)
    ax_prev.plot(p95_t / 1e6, color=COLOR_OPTIMISTA, linewidth=1.5, zorder=3)
    x_ticks = [0, meses // 4, meses // 2, 3 * meses // 4, meses]
    ax_prev.set_xticks(x_ticks)
    ax_prev.set_xticklabels([str(2026 + t // 12) for t in x_ticks], fontsize=8, color="#5E7391")
    ax_prev.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}M"))
    ax_prev.tick_params(axis="y", labelsize=8, colors="#5E7391")
    ax_prev.grid(axis="y", color="#DDE3ED", linewidth=0.7, zorder=0)
    for sp in ["top", "right"]:
        ax_prev.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax_prev.spines[sp].set_color("#DDE3ED")
    fig_prev.tight_layout(pad=0.5)
    grafico_preview = _figura_a_base64(fig_prev)

    return render(request, "ejecucion_simulacion.html", {
        "perfil":          perfil,
        "mu":              round(params["mu"] * 100, 2),
        "sigma":           round(params["sigma"] * 100, 2),
        "comision":        round(comision * 100, 2),
        "meses":           meses,
        "n_obs":           params["n_obs"],
        "grafico_preview": grafico_preview,
        "redirect_url":    reverse("mostrar_resultados"),
    })


# ── PANTALLA 3: Análisis de resultados ───────────────────────────────────────

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
    meses_sim    = resultados["meses"]

    def _estilo_ax(ax):
        ax.set_facecolor("#FAFCFF")
        ax.grid(axis="y", color="#DDE3ED", linewidth=0.7, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#DDE3ED")
        ax.spines["bottom"].set_color("#DDE3ED")
        ax.tick_params(colors="#5E7391", labelsize=10)

    # ── Gráfico 1: Histograma ────────────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(9, 4.5))
    fig1.patch.set_facecolor("white")
    n_arr, _, _ = ax1.hist(saldos / 1e6, bins=60, color="#1A6FA0", edgecolor="white",
                           linewidth=0.4, alpha=0.88, zorder=3)
    y_data_max = float(max(n_arr))
    ax1.set_ylim(0, y_data_max * 1.40)
    annot_y = y_data_max * 1.23

    ax1.axvline(resultados["p5"]  / 1e6, color=COLOR_PESIMISTA, linewidth=2, linestyle="--", zorder=4)
    ax1.axvline(resultados["p50"] / 1e6, color=COLOR_ESPERADO,  linewidth=2.5, zorder=5)
    ax1.axvline(resultados["p95"] / 1e6, color=COLOR_OPTIMISTA, linewidth=2, linestyle="--", zorder=4)
    if perfil["umbral"] > 0:
        ax1.axvline(perfil["umbral"] / 1e6, color=COLOR_UMBRAL, linewidth=2, linestyle=":", zorder=4)

    def _chip(x_m, label, color):
        ax1.text(x_m, annot_y, label, color=color,
                 fontsize=8.5, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                           edgecolor=color, linewidth=1.2, alpha=0.95),
                 ha="center", va="center", zorder=7)

    _chip(resultados["p5"]  / 1e6, f'P5  CRC {resultados["p5"] /1e6:.0f} M', COLOR_PESIMISTA)
    _chip(resultados["p50"] / 1e6, f'P50  CRC {resultados["p50"]/1e6:.0f} M', COLOR_ESPERADO)
    _chip(resultados["p95"] / 1e6, f'P95  CRC {resultados["p95"]/1e6:.0f} M', COLOR_OPTIMISTA)
    if perfil["umbral"] > 0:
        _chip(perfil["umbral"] / 1e6, f'Umbral  CRC {perfil["umbral"]/1e6:.0f} M', COLOR_UMBRAL)

    ax1.set_xlabel("Saldo al retiro (millones CRC)", fontsize=11, color="#5E7391")
    ax1.set_ylabel("Frecuencia", fontsize=11, color="#5E7391")
    _estilo_ax(ax1)
    fig1.tight_layout()
    grafico_histograma = _figura_a_base64(fig1)

    # ── Gráfico 2: Trayectorias ───────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(9, 4.2))
    fig2.patch.set_facecolor("white")
    for tray in trayectorias:
        ax2.plot(tray / 1e6, color="#90ABC0", alpha=0.12, linewidth=0.7, zorder=1)
    mediana = np.median(trayectorias, axis=0)
    ax2.plot(mediana / 1e6, color=COLOR_ESPERADO, linewidth=2.8, label="Mediana (P50)", zorder=5)
    x_ticks = [0, meses_sim // 4, meses_sim // 2, 3 * meses_sim // 4, meses_sim]
    ax2.set_xticks(x_ticks)
    ax2.set_xticklabels([str(2026 + t // 12) for t in x_ticks])
    ax2.set_xlabel("Año", fontsize=11, color="#5E7391")
    ax2.set_ylabel("Saldo (millones CRC)", fontsize=11, color="#5E7391")
    ax2.legend(fontsize=10, framealpha=0.95, edgecolor="#DDE3ED")
    _estilo_ax(ax2)
    fig2.tight_layout()
    grafico_trayectorias = _figura_a_base64(fig2)

    def _m(val): return f"{val/1e6:.1f}".replace(".", ",")

    _meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                 7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    now = datetime.now()
    ultima_simulacion = f"{now.day} {_meses_es[now.month]} {now.year} – {now.strftime('%H:%M')}"

    return render(request, "resultados.html", {
        "perfil":               perfil,
        "r":                    resultados,
        "grafico_histograma":   grafico_histograma,
        "grafico_trayectorias": grafico_trayectorias,
        "p5_m":              _m(resultados["p5"]),
        "p25_m":             _m(resultados["p25"]),
        "p50_m":             _m(resultados["p50"]),
        "p75_m":             _m(resultados["p75"]),
        "p95_m":             _m(resultados["p95"]),
        "p50_real_m":        _m(resultados["p50_real"]),
        "umbral_m":          _m(perfil["umbral"]) if perfil["umbral"] > 0 else None,
        "anio_retiro":       perfil["edad_retiro"],
        "densidad_pct":      round(perfil["densidad"] * 100),
        "ultima_simulacion": ultima_simulacion,
    })
