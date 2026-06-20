# interfaz/graficos.py
# Generación de los tres gráficos del simulador mediante matplotlib.
# Cada función recibe los datos que necesita y devuelve una cadena base64
# lista para incrustar en el HTML con <img src="data:image/png;base64,...">
# Las vistas (views.py) solo llaman a estas funciones; no manejan matplotlib.

import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")   # renderizar sin ventana de escritorio (modo servidor)
import matplotlib.pyplot as plt


# Paleta institucional UCR — consistente en los tres gráficos
COLOR_PESIMISTA = "#D32F2F"
COLOR_ESPERADO  = "#006699"
COLOR_OPTIMISTA = "#2E7D32"
COLOR_UMBRAL    = "#00ABE8"


def _figura_a_base64(fig) -> str:
    """Serializa una figura matplotlib a PNG en memoria y la codifica en base64."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    imagen = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return imagen


def _estilo_ax(ax) -> None:
    """Aplica el estilo visual UCR a un eje: fondo claro, cuadrícula sutil,
    sin bordes superior ni derecho."""
    ax.set_facecolor("#FAFCFF")
    ax.grid(axis="y", color="#DDE3ED", linewidth=0.7, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDE3ED")
    ax.spines["bottom"].set_color("#DDE3ED")
    ax.tick_params(colors="#5E7391", labelsize=10)


def generar_preview(S: np.ndarray, meses: int) -> str:
    """
    Gráfico pequeño de vista previa que se muestra mientras la simulación
    espera el redireccionamiento automático a la pantalla de resultados.

    Muestra 25 trayectorias de muestra (en azul tenue) y encima las tres
    líneas de referencia P5 / P50 / P95 calculadas sobre las 10 000.
    El eje X se convierte de índice de mes a año calendario (base 2026).

    Parámetros
    ----------
    S     : matriz de simulación completa (n, meses+1)
    meses : horizonte total en meses, necesario para etiquetar el eje X

    Retorna cadena base64 del PNG.
    """
    # Seleccionar 25 trayectorias al azar para que el gráfico sea ligero
    idx_prev = np.random.choice(S.shape[0], min(25, S.shape[0]), replace=False)

    fig, ax = plt.subplots(figsize=(4.5, 2.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFCFF")

    # Trayectorias individuales en azul muy tenue para no dominar visualmente
    for i in idx_prev:
        ax.plot(S[i, :] / 1e6, color="#B0C8DC", alpha=0.4, linewidth=0.7, zorder=1)

    # Los percentiles se calculan sobre la simulación completa (no solo la muestra),
    # para que las líneas de referencia sean estadísticamente representativas
    p5_t  = np.percentile(S, 5,  axis=0)
    p50_t = np.percentile(S, 50, axis=0)
    p95_t = np.percentile(S, 95, axis=0)

    ax.plot(p5_t  / 1e6, color=COLOR_PESIMISTA, linewidth=1.5, zorder=3)
    ax.plot(p50_t / 1e6, color=COLOR_ESPERADO,  linewidth=2.2, zorder=4)
    ax.plot(p95_t / 1e6, color=COLOR_OPTIMISTA, linewidth=1.5, zorder=3)

    # Convertir índice de mes (0…meses) a año calendario en el eje X
    x_ticks = [0, meses // 4, meses // 2, 3 * meses // 4, meses]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([str(2026 + t // 12) for t in x_ticks], fontsize=8, color="#5E7391")

    # Eje Y en millones: "45M" en lugar de "45000000"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}M"))
    ax.tick_params(axis="y", labelsize=8, colors="#5E7391")
    ax.grid(axis="y", color="#DDE3ED", linewidth=0.7, zorder=0)

    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#DDE3ED")

    fig.tight_layout(pad=0.5)
    return _figura_a_base64(fig)


def generar_histograma(saldos: np.ndarray, resultados: dict,
                       umbral: float) -> str:
    """
    Histograma de la distribución de los 10 000 saldos finales al retiro.

    Sobre las barras se trazan líneas verticales para P5, P50 y P95
    (y el umbral del usuario si lo definió), cada una con una etiqueta
    "chip" flotante que muestra el valor en millones de CRC.

    Parámetros
    ----------
    saldos     : array 1-D con los saldos finales de cada escenario (CRC)
    resultados : dict con p5, p50, p95 (salida de calcular_estadisticos)
    umbral     : monto mínimo deseado al retiro (0 si el usuario no lo definió)

    Retorna cadena base64 del PNG.
    """
    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.patch.set_facecolor("white")

    # hist() retorna (frecuencias, bordes de bins, parches); guardamos las frecuencias
    # para calcular cuánto espacio vertical reservar para las etiquetas flotantes
    n_arr, _, _ = ax.hist(saldos / 1e6, bins=60, color="#1A6FA0", edgecolor="white",
                          linewidth=0.4, alpha=0.88, zorder=3)

    y_data_max = float(max(n_arr))
    ax.set_ylim(0, y_data_max * 1.40)   # 40% de margen superior para los chips
    annot_y = y_data_max * 1.23          # altura fija donde se anclan las etiquetas

    # Líneas verticales: P5 y P95 punteadas, P50 sólida y más gruesa
    ax.axvline(resultados["p5"]  / 1e6, color=COLOR_PESIMISTA, linewidth=2, linestyle="--", zorder=4)
    ax.axvline(resultados["p50"] / 1e6, color=COLOR_ESPERADO,  linewidth=2.5, zorder=5)
    ax.axvline(resultados["p95"] / 1e6, color=COLOR_OPTIMISTA, linewidth=2, linestyle="--", zorder=4)
    if umbral > 0:
        ax.axvline(umbral / 1e6, color=COLOR_UMBRAL, linewidth=2, linestyle=":", zorder=4)

    def _chip(x_m, label, color):
        """Etiqueta redondeada centrada sobre la línea vertical correspondiente."""
        ax.text(x_m, annot_y, label, color=color,
                fontsize=8.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                          edgecolor=color, linewidth=1.2, alpha=0.95),
                ha="center", va="center", zorder=7)

    _chip(resultados["p5"]  / 1e6, f'P5  CRC {resultados["p5"] /1e6:.0f} M', COLOR_PESIMISTA)
    _chip(resultados["p50"] / 1e6, f'P50  CRC {resultados["p50"]/1e6:.0f} M', COLOR_ESPERADO)
    _chip(resultados["p95"] / 1e6, f'P95  CRC {resultados["p95"]/1e6:.0f} M', COLOR_OPTIMISTA)
    if umbral > 0:
        _chip(umbral / 1e6, f'Umbral  CRC {umbral/1e6:.0f} M', COLOR_UMBRAL)

    ax.set_xlabel("Saldo al retiro (millones CRC)", fontsize=11, color="#5E7391")
    ax.set_ylabel("Frecuencia", fontsize=11, color="#5E7391")
    _estilo_ax(ax)
    fig.tight_layout()
    return _figura_a_base64(fig)


def generar_trayectorias(trayectorias: np.ndarray, meses_sim: int) -> str:
    """
    Gráfico de evolución temporal: cómo crece el saldo año a año en cada escenario.

    Se grafican hasta 100 trayectorias de fondo con alta transparencia para
    visualizar la dispersión posible ("nube de futuros"), y encima se traza
    la mediana en azul UCR como referencia del escenario central.

    Parámetros
    ----------
    trayectorias : submatriz con las trayectorias de muestra (100, meses+1)
    meses_sim    : horizonte total en meses, para etiquetar el eje X como años

    Retorna cadena base64 del PNG.
    """
    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.patch.set_facecolor("white")

    # Alpha muy bajo (0.12) para que la superposición de 100 líneas forme
    # una "nube" que transmite visualmente el rango de posibilidades
    for tray in trayectorias:
        ax.plot(tray / 1e6, color="#90ABC0", alpha=0.12, linewidth=0.7, zorder=1)

    # La mediana sobre las 100 trayectorias de muestra como línea de referencia
    mediana = np.median(trayectorias, axis=0)
    ax.plot(mediana / 1e6, color=COLOR_ESPERADO, linewidth=2.8, label="Mediana (P50)", zorder=5)

    # Eje X: 5 puntos equidistantes del horizonte convertidos a año calendario
    x_ticks = [0, meses_sim // 4, meses_sim // 2, 3 * meses_sim // 4, meses_sim]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([str(2026 + t // 12) for t in x_ticks])

    ax.set_xlabel("Año", fontsize=11, color="#5E7391")
    ax.set_ylabel("Saldo (millones CRC)", fontsize=11, color="#5E7391")
    ax.legend(fontsize=10, framealpha=0.95, edgecolor="#DDE3ED")
    _estilo_ax(ax)
    fig.tight_layout()
    return _figura_a_base64(fig)