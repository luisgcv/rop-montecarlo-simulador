# datos/cargador.py
# Funciones para leer y limpiar los 4 archivos Excel del proyecto.

import pandas as pd
import numpy as np
from pathlib import Path

RUTA_DATOS = Path(__file__).parent / "data"


def cargar_rendimientos():
    """
    Lee Rendimientos_Datos.xlsx y retorna DataFrame limpio.

    Filtros aplicados:
      - tipo         == 'REAL'        (retornos ya deflactados)
      - periodicidad == 'ANUAL'       (ventana de 12 meses)
      - entidad      != 'TOTAL'       (solo operadoras individuales)
      - codigoregimen == 1            (ROP)

    Retorna columnas: fecha (datetime), entidad (str), rentabilidad (float, decimal)
    Nota: rentabilidad viene en % → dividir entre 100
    """
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_Datos.xlsx")

    # Filtrar solo lo que el simulador necesita
    mask = (
        (df["tipo"] == "REAL") &
        (df["periodicidad"] == "ANUAL") &
        (df["entidad"] != "TOTAL") &
        (df["codigoregimen"] == 1)
    )
    df = df[mask].copy()

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["rentabilidad"] = df["rentabilidad"] / 100   # % → decimal

    return df[["fecha", "entidad", "rentabilidad"]].sort_values("fecha").reset_index(drop=True)


def cargar_comisiones():
    """
    Lee Comisión_datos.xlsx y retorna la comisión anual sobre SALDO por operadora.

    Filtros aplicados:
      - tipo          == 'SALDO'      (el ROP cobra sobre saldo administrado, no sobre aporte)
      - codigoregimen == 1            (ROP)
      - fecha más reciente disponible por entidad

    Retorna dict: { 'POPULAR': 0.015, 'BCR-PENSION': 0.010, ... }
    Nota: comisión viene en % → dividir entre 100
    """
    df = pd.read_excel(RUTA_DATOS / "Comisión_datos.xlsx")

    mask = (df["tipo"] == "SALDO") & (df["codigoregimen"] == 1)
    df = df[mask].dropna(subset=["comisión"]).copy()

    df["fecha"] = pd.to_datetime(df["fecha"])

    # Tomar el registro más reciente por operadora
    df = df.sort_values("fecha").groupby("entidad").last().reset_index()

    df["comisión"] = df["comisión"] / 100   # % → decimal

    return dict(zip(df["entidad"], df["comisión"]))


def cargar_ipc():
    """
    Lee IPC.xlsx (tiene 4 filas de encabezado BCCR → skiprows=4).

    Columnas reales del Excel (después de skiprows):
      Fecha | Nivel | IPC, variación mensual (%) | IPC, variación interanual (%) | Variación acumulada (%)

    Retorna DataFrame con columnas: fecha (datetime), var_mensual (float, decimal)
    Nota: variación mensual viene en % → dividir entre 100
    """
    df = pd.read_excel(
        RUTA_DATOS / "Índice de precios al consumidor (IPC).xlsx",
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
        RUTA_DATOS / "Tasa Básica Pasiva (TBP).xlsx",
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
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_Datos.xlsx")
    operadoras = sorted(df[df["entidad"] != "TOTAL"]["entidad"].unique().tolist())
    return operadoras
