# simulador/motor.py
# Núcleo matemático de la simulación: estima los parámetros históricos de cada
# operadora del ROP y proyecta el saldo futuro usando Movimiento Browniano
# Geométrico (GBM). Base teórica: Glasserman (2004), ec. 3.22.

import numpy as np


def estimar_parametros(rentabilidades_anuales: np.ndarray) -> dict:
    """
    A partir del historial de rendimientos anuales de una operadora, calcula
    los dos parámetros que alimentan el modelo GBM: la deriva (mu) y la
    volatilidad (sigma).

    La corrección de Itô (+ 0,5·σ²) transforma la media aritmética de los
    log-retornos en la deriva del proceso continuo, tal como requiere la
    ecuación diferencial estocástica del GBM. Sin esta corrección, las
    proyecciones resultarían sesgadas hacia la baja.

    Parámetros
    ----------
    rentabilidades_anuales : np.ndarray
        Retornos históricos en decimal (0.085 representa 8,5% anual).

    Retorna
    -------
    dict con: mu (deriva anualizada), sigma (volatilidad anualizada),
              n_obs (cantidad de observaciones usadas en la estimación).
    """
    r = np.array(rentabilidades_anuales, dtype=float)
    r = r[~np.isnan(r)]

    if len(r) == 0:
        raise ValueError(
            "No hay datos de rentabilidad para esta operadora con los filtros aplicados. "
            "Verifica que la operadora tenga datos en el archivo Rendimientos_OPC.xlsx."
        )

    sigma = float(np.std(r, ddof=1))
    mu    = float(np.mean(r)) + 0.5 * sigma ** 2   # corrección de Itô

    if not np.isfinite(mu) or not np.isfinite(sigma):
        raise ValueError(
            f"Los parámetros estimados no son finitos: mu={mu}, sigma={sigma}. "
            f"Revisar los datos de rentabilidad (n={len(r)})."
        )

    return {"mu": mu, "sigma": sigma, "n_obs": len(r)}


def simular(saldo_inicial, salario_bruto, meses, mu, sigma,
            comision_anual, densidad=1.0, n=10_000, semilla=None):
    """
    Genera N trayectorias independientes del saldo ROP mediante GBM discreto.

    En cada paso mensual, el saldo crece según el rendimiento aleatorio del
    mercado y recibe el aporte obligatorio del 4,25% del salario. La comisión
    administrativa de la operadora se descuenta directamente del drift, de modo
    que el afiliado solo ve el rendimiento neto: mu_neta = mu - comision_anual.

    Enfoque vectorizado: se generan los N×T shocks aleatorios de una sola vez
    como una matriz de NumPy, evitando cualquier iteración sobre escenarios.
    El único bucle restante es sobre los pasos de tiempo (T meses), que es
    matemáticamente ineludible porque S(t+1) depende del valor de S(t).

    Parámetros
    ----------
    saldo_inicial  : float — saldo actual del afiliado reportado por SUPEN (CRC)
    salario_bruto  : float — salario bruto mensual (CRC); base del 4,25% ROP
    meses          : int   — horizonte de proyección en meses
    mu             : float — deriva anualizada del GBM, estimada con datos históricos
    sigma          : float — volatilidad anualizada del GBM, estimada con datos históricos
    comision_anual : float — comisión sobre saldo cobrada por la operadora (decimal)
    densidad       : float — proporción de meses en que el afiliado cotiza (0,5–1,0)
    n              : int   — número de escenarios simulados (por defecto 10 000)
    semilla        : int   — semilla aleatoria para resultados reproducibles (opcional)

    Retorna
    -------
    Matriz numpy (n, meses+1):
      columna 0     = saldo_inicial, igual para todos los escenarios
      columna meses = saldo final de cada escenario al momento del retiro
    """
    if not np.isfinite(mu):
        raise ValueError(f"mu no es finito: {mu}")
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError(f"sigma no es válido: {sigma}")
    if meses <= 0:
        raise ValueError(f"meses debe ser positivo: {meses}")

    if semilla is not None:
        np.random.seed(semilla)

    dt = 1 / 12   # cada paso equivale a un mes calendario

    mu_neta = mu - comision_anual               # rendimiento efectivo, neto de comisión
    aporte  = salario_bruto * 0.0425 * densidad # aporte mensual obligatorio al ROP

    Z     = np.random.standard_normal((n, meses))  # matriz de shocks: un valor por escenario y mes
    drift = (mu_neta - 0.5 * sigma ** 2) * dt
    shock = sigma * np.sqrt(dt) * Z
    R     = np.exp(drift + shock)                   # factor de crecimiento mensual por escenario

    S       = np.zeros((n, meses + 1))
    S[:, 0] = saldo_inicial

    for t in range(meses):   # avanza mes a mes; todos los escenarios se actualizan en paralelo
        S[:, t + 1] = S[:, t] * R[:, t] + aporte

    return S


def calcular_estadisticos(S: np.ndarray, umbral: float = 0,
                           anios: int = 0, inflacion: float = 0.03) -> dict:
    """
    Resume la distribución de saldos finales en los estadísticos que
    se presentan al afiliado en la pantalla de resultados.

    Los percentiles P5/P50/P95 delimitan los escenarios pesimista, esperado
    y optimista. El P50 real convierte la mediana nominal a colones de hoy
    usando la inflación proyectada del BCCR (3% anual por defecto), para que
    el afiliado pueda comparar el resultado con su poder adquisitivo actual.

    Si el afiliado definió un umbral de suficiencia, se calcula la probabilidad
    de alcanzarlo como la fracción de escenarios que lo superan.

    Parámetros
    ----------
    S         : matriz de simulación (n, meses+1), salida de simular()
    umbral    : monto mínimo deseado al retiro en CRC nominales (0 = sin umbral)
    anios     : años de proyección, necesario para calcular el factor de deflactación
    inflacion : inflación anual asumida para deflactar (por defecto 3%, estimación BCCR)

    Retorna
    -------
    dict con: p5, p25, p50, p75, p95 (nominales), p50_real (deflactado),
              prob_exito (% que supera el umbral, None si no hay umbral),
              saldos_finales (array con los n saldos finales).
    """
    saldos = S[:, -1]
    saldos = saldos[np.isfinite(saldos)]   # descartar cualquier NaN o Inf residual

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
        "p5":             round(float(p5), 0),
        "p25":            round(float(p25), 0),
        "p50":            round(float(p50), 0),
        "p75":            round(float(p75), 0),
        "p95":            round(float(p95), 0),
        "p50_real":       round(float(p50_real), 0),
        "prob_exito":     round(prob_exito, 1) if prob_exito is not None else None,
        "saldos_finales": saldos,
    }