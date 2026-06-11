# simulador/motor.py
# Motor de simulación Monte Carlo usando Movimiento Browniano Geométrico.
# Referencia matemática: Glasserman (2004), p. 94, ec. 3.18-3.22

import numpy as np


def estimar_parametros(rentabilidades_anuales: np.ndarray) -> dict:
    """
    Estima mu (drift) y sigma (volatilidad) a partir de retornos anuales reales.

    Entrada: array de retornos anuales en decimal (ej: 0.085 para 8.5%)
    Salida:  dict con mu y sigma anualizados

    Fórmulas (Glasserman, 2004, p. 94):
      σ̂  = std(retornos)
      μ̂  = mean(retornos) + ½σ̂²   ← corrección de Itô
    """
    sigma = float(np.std(rentabilidades_anuales, ddof=1))
    mu    = float(np.mean(rentabilidades_anuales)) + 0.5 * sigma ** 2

    return {"mu": mu, "sigma": sigma, "n_obs": len(rentabilidades_anuales)}


def simular(saldo_inicial, salario_bruto, meses, mu, sigma,
            comision, densidad=1.0, n=10_000, semilla=None):
    """
    Genera N trayectorias del saldo ROP mes a mes (vectorizado con NumPy).

    Fórmula exacta (Glasserman, 2004, p. 94, ec. 3.22):
      S(t+1) = S(t) · exp[(μ̂ - ½σ̂²)Δt  +  σ̂·√Δt·Z]
      donde Z ~ N(0,1),  Δt = 1/12

    Parámetros:
      saldo_inicial : float  — saldo actual en colones
      salario_bruto : float  — salario bruto mensual en colones
      meses         : int    — horizonte de simulación (meses)
      mu            : float  — drift anualizado (decimal)
      sigma         : float  — volatilidad anualizada (decimal)
      comision      : float  — comisión anual sobre saldo (decimal, ej: 0.015)
      densidad      : float  — fracción de meses que cotiza (0.5–1.0)
      n             : int    — número de trayectorias
      semilla       : int    — semilla aleatoria (opcional)

    Retorna: matriz numpy de forma (n, meses+1)
      Columna 0      = saldo_inicial (igual en todas las filas)
      Columna meses  = saldo final de cada escenario
    """
    if semilla is not None:
        np.random.seed(semilla)

    dt = 1 / 12

    # Aporte mensual bruto (4.25% del salario, escalado por densidad)
    aporte = salario_bruto * 0.0425 * densidad

    # Generar todos los shocks aleatorios de una vez (matriz N × meses)
    Z = np.random.standard_normal((n, meses))

    # Comisión anual sobre saldo → se descuenta del drift (retorno efectivo neto)
    # exp[(μ - c - ½σ²)Δt + σ√Δt·Z]
    drift = (mu - comision - 0.5 * sigma ** 2) * dt
    shock = sigma * np.sqrt(dt) * Z
    R = np.exp(drift + shock)   # shape: (n, meses)

    # Propagar el saldo mes a mes
    S = np.zeros((n, meses + 1))
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
      p5, p25, p50, p75, p95    → percentiles en colones nominales
      p50_real                   → P50 deflactado a colones de hoy
      prob_exito                 → % de escenarios que superan el umbral
      saldos_finales             → array con los n saldos finales (para graficar)
    """
    saldos = S[:, -1]

    p5, p25, p50, p75, p95 = np.percentile(saldos, [5, 25, 50, 75, 95])

    # Deflactar el escenario esperado a poder adquisitivo de hoy
    factor_deflactor = (1 + inflacion) ** anios
    p50_real = p50 / factor_deflactor if factor_deflactor > 0 else p50

    # Probabilidad de superar el umbral de suficiencia
    prob_exito = float(np.mean(saldos >= umbral) * 100) if umbral > 0 else None

    return {
        "p5":           round(float(p5), 0),
        "p25":          round(float(p25), 0),
        "p50":          round(float(p50), 0),
        "p75":          round(float(p75), 0),
        "p95":          round(float(p95), 0),
        "p50_real":     round(float(p50_real), 0),
        "prob_exito":   round(prob_exito, 1) if prob_exito is not None else None,
        "saldos_finales": saldos,
    }
