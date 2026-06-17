# simulador/motor.py
# Motor de simulación Monte Carlo usando Movimiento Browniano Geométrico.
# Referencia matemática: Glasserman (2004), p. 94, ec. 3.18-3.22

import numpy as np


def estimar_parametros(rentabilidades_anuales: np.ndarray) -> dict:
    """
    Estima mu y sigma. Lanza ValueError si el array está vacío o tiene NaN.

    Entrada: array de retornos anuales en decimal (ej: 0.085 para 8.5%)
    Salida:  dict con mu y sigma anualizados

    Fórmulas (Glasserman, 2004, p. 94):
      sigma = std(retornos)
      mu    = mean(retornos) + 0.5*sigma^2   <- corrección de Itô
    """
    # Limpiar NaN antes de procesar
    r = np.array(rentabilidades_anuales, dtype=float)
    r = r[~np.isnan(r)]

    if len(r) == 0:
        raise ValueError(
            "No hay datos de rentabilidad para esta operadora con los filtros aplicados. "
            "Verifica que la operadora tenga datos en el archivo Rendimientos_OPC.xlsx."
        )

    sigma = float(np.std(r, ddof=1))
    mu    = float(np.mean(r)) + 0.5 * sigma ** 2

    # Guardia final: si por alguna razón salen NaN, lanzar error claro
    if not np.isfinite(mu) or not np.isfinite(sigma):
        raise ValueError(
            f"Los parámetros estimados no son finitos: mu={mu}, sigma={sigma}. "
            f"Revisar los datos de rentabilidad (n={len(r)})."
        )

    return {"mu": mu, "sigma": sigma, "n_obs": len(r)}


def simular(saldo_inicial, salario_bruto, meses, mu, sigma,
            comision_anual, densidad=1.0, n=10_000, semilla=None):
    """
    Genera N trayectorias del saldo ROP mes a mes (vectorizado con NumPy).

    Fórmula exacta (Glasserman, 2004, p. 94, ec. 3.22):
      S(t+1) = S(t) * exp[(mu_neta - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z]
      donde Z ~ N(0,1), dt = 1/12, mu_neta = mu - comision_anual

    Parámetros:
      saldo_inicial  : float  — saldo actual en colones
      salario_bruto  : float  — salario bruto mensual en colones
      meses          : int    — horizonte de simulación (meses)
      mu             : float  — drift anualizado (decimal)
      sigma          : float  — volatilidad anualizada (decimal)
      comision_anual : float  — comisión anual sobre saldo (decimal, ej: 0.015)
      densidad       : float  — fracción de meses que cotiza (0.5–1.0)
      n              : int    — número de trayectorias
      semilla        : int    — semilla aleatoria (opcional)

    Retorna: matriz numpy de forma (n, meses+1)
      Columna 0      = saldo_inicial (igual en todas las filas)
      Columna meses  = saldo final de cada escenario
    """
    # ── Validaciones de entrada ──────────────────────────────────────────────
    if not np.isfinite(mu):
        raise ValueError(f"mu no es finito: {mu}")
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError(f"sigma no es válido: {sigma}")
    if meses <= 0:
        raise ValueError(f"meses debe ser positivo: {meses}")

    if semilla is not None:
        np.random.seed(semilla)

    dt = 1 / 12

    # Descontar comisión anual del drift (comisión sobre saldo)
    mu_neta = mu - comision_anual
    aporte  = salario_bruto * 0.0425 * densidad   # aporte bruto sin descuento

    Z     = np.random.standard_normal((n, meses))
    drift = (mu_neta - 0.5 * sigma ** 2) * dt
    shock = sigma * np.sqrt(dt) * Z
    R     = np.exp(drift + shock)   # shape: (n, meses)

    S       = np.zeros((n, meses + 1))
    S[:, 0] = saldo_inicial

    for t in range(meses):   # loop sobre tiempo, no sobre escenarios
        S[:, t + 1] = S[:, t] * R[:, t] + aporte

    return S


def calcular_estadisticos(S: np.ndarray, umbral: float = 0,
                           anios: int = 0, inflacion: float = 0.03) -> dict:
    """
    Resume la distribución de saldos finales en estadísticos clave.

    Parámetros:
      S        : matriz de simulación (n, meses+1)
      umbral   : monto mínimo deseado al retiro (en colones nominales)
      anios    : años de proyección (para deflactar)
      inflacion: inflación anual asumida para deflactar (default 3% BCCR)

    Retorna dict con:
      p5, p25, p50, p75, p95    -> percentiles en colones nominales
      p50_real                   -> P50 deflactado a colones de hoy
      prob_exito                 -> % de escenarios que superan el umbral
      saldos_finales             -> array con los n saldos finales (ya sin NaN)
    """
    saldos = S[:, -1]

    # Eliminar NaN e Inf antes de calcular estadísticos
    saldos = saldos[np.isfinite(saldos)]

    if len(saldos) == 0:
        raise ValueError(
            "La simulación produjo solo valores NaN o Inf. "
            "Verifica los parámetros mu y sigma."
        )

    p5, p25, p50, p75, p95 = np.percentile(saldos, [5, 25, 50, 75, 95])

    factor_deflactor = (1 + inflacion) ** anios if anios > 0 else 1.0
    p50_real = p50 / factor_deflactor

    prob_exito = float(np.mean(saldos >= umbral) * 100) if umbral > 0 else None

    return {
        "p5":           round(float(p5), 0),
        "p25":          round(float(p25), 0),
        "p50":          round(float(p50), 0),
        "p75":          round(float(p75), 0),
        "p95":          round(float(p95), 0),
        "p50_real":     round(float(p50_real), 0),
        "prob_exito":   round(prob_exito, 1) if prob_exito is not None else None,
        "saldos_finales": saldos,   # ya sin NaN
    }
