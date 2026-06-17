# datos/cargador.py
# Funciones para leer y limpiar los 4 archivos Excel del proyecto.

import pandas as pd
import numpy as np
from pathlib import Path

RUTA_DATOS = Path(__file__).parent / "data"


def cargar_rendimientos():
    """
    Lee Rendimientos_OPC.xlsx.
    Filtra: tipo == 'REAL', periodicidad == 'ANUAL', excluye entidad 'TOTAL'.
    NO filtra por codigoregimen — usar todos los regímenes disponibles por operadora.

    Si para una operadora no hay datos con esos filtros exactos, el llamador
    recibirá un array vacío y debe manejar el caso.
    """
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_OPC.xlsx")

    # Normalizar texto para evitar problemas de mayúsculas o espacios
    df["tipo"]         = df["tipo"].str.strip().str.upper()
    df["periodicidad"] = df["periodicidad"].str.strip().str.upper()
    df["entidad"]      = df["entidad"].str.strip()

    mask = (
        (df["tipo"] == "REAL") &
        (df["periodicidad"] == "ANUAL") &
        (df["entidad"].str.upper() != "TOTAL")
    )
    df = df[mask].copy()

    df["fecha"]        = pd.to_datetime(df["fecha"])
    df["rentabilidad"] = df["rentabilidad"] / 100   # % → decimal

    return df[["fecha", "entidad", "rentabilidad"]].sort_values("fecha").reset_index(drop=True)


def cargar_comisiones():
    """
    Lee Comisión_datos.xlsx y retorna comisión anual sobre el SALDO por operadora.

    El ROP cobra comisión sobre SALDO (porcentaje anual del fondo acumulado).
    Esta comisión se descuenta del drift en el GBM: mu_neta = mu - comision_anual.

    Retorna dict: { 'POPULAR': 0.015, 'BCR-PENSION': 0.010, ... }
    Si una operadora no tiene dato, usa 0.01 (1% anual como valor conservador).
    """
    df = pd.read_excel(RUTA_DATOS / "Comisiones_OPC.xlsx")

    # Normalizar
    df["tipo"]    = df["tipo"].str.strip().str.upper()
    df["entidad"] = df["entidad"].str.strip()

    # Usar tipo SALDO (único con datos no-NaN según diagnóstico)
    df_saldo = df[df["tipo"] == "SALDO"].dropna(subset=["comisión"]).copy()

    if df_saldo.empty:
        # Si no hay ningún dato, retornar comisión por defecto para todas
        operadoras = df["entidad"].unique().tolist()
        return {op: 0.01 for op in operadoras}

    df_saldo["fecha"]    = pd.to_datetime(df_saldo["fecha"])
    df_saldo["comisión"] = df_saldo["comisión"] / 100   # % → decimal

    # Tomar el valor más reciente por operadora
    df_saldo = (
        df_saldo.sort_values("fecha")
        .groupby("entidad")
        .last()
        .reset_index()
    )

    return dict(zip(df_saldo["entidad"], df_saldo["comisión"]))


def cargar_ipc():
    """
    Lee IPC.xlsx (tiene 4 filas de encabezado BCCR → skiprows=4).

    Columnas reales del Excel (después de skiprows):
      Fecha | Nivel | IPC, variación mensual (%) | IPC, variación interanual (%) | Variación acumulada (%)

    Retorna DataFrame con columnas: fecha (datetime), var_mensual (float, decimal)
    Nota: variación mensual viene en % → dividir entre 100
    """
    df = pd.read_excel(
        RUTA_DATOS / "IPC.xlsx",
        skiprows=4
    )

    # Renombrar columnas a nombres simples
    df.columns = ["fecha", "nivel", "var_mensual", "var_interanual", "var_acumulada"]

    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["var_mensual"] = df["var_mensual"] / 100   # % → decimal

    return df[["fecha", "var_mensual"]].sort_values("fecha").reset_index(drop=True)


def cargar_tbp():
    """
    Lee 'Tasa Básica Pasiva (TBP).xlsx' (tiene 4 filas de encabezado BCCR → skiprows=4).
    Frecuencia diaria → promediar a mensual para alinear con los demás datos.

    Columnas reales del Excel (después de skiprows):
      Fecha | Tasa básica pasiva calculada por el BCCR

    Retorna DataFrame con columnas: fecha (datetime, fin de mes), tbp (float, decimal)
    Nota: tasa viene en % → dividir entre 100
    """
    df = pd.read_excel(
        RUTA_DATOS / "TBP.xlsx",
        skiprows=4
    )

    df.columns = ["fecha", "tbp"]
    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["tbp"] = df["tbp"] / 100   # % → decimal

    # Colapsar de diario a mensual (promedio)
    df = (
        df.set_index("fecha")
        .resample("ME")["tbp"]
        .mean()
        .reset_index()
    )

    return df


def listar_operadoras():
    """Retorna lista de operadoras disponibles en los datos de rendimientos."""
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_OPC.xlsx")
    operadoras = sorted(df[df["entidad"] != "TOTAL"]["entidad"].unique().tolist())
    return operadoras


def validar_operadora(entidad: str) -> dict:
    """
    Verifica si una operadora tiene datos suficientes para simular.
    Retorna un dict con el diagnóstico para mostrar en caso de error.
    """
    df = cargar_rendimientos()
    datos_op = df[df["entidad"] == entidad]["rentabilidad"].dropna()

    return {
        "tiene_datos":       len(datos_op) > 0,
        "n_obs":             len(datos_op),
        "entidad":           entidad,
        "todas_entidades":   sorted(df["entidad"].unique().tolist()),
    }
