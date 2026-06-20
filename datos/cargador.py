# datos/cargador.py
# Lectura y limpieza de los cuatro archivos Excel que alimentan la simulación.
# Todos los datos provienen de fuentes oficiales: BCCR (Banco Central de Costa
# Rica) y SUPEN (Superintendencia de Pensiones). Los archivos residen en datos/data/.

import pandas as pd
import numpy as np
from pathlib import Path

RUTA_DATOS = Path(__file__).parent / "data"

def cargar_rendimientos():
    """
    Lee los rendimientos históricos del ROP desde Rendimientos_OPC.xlsx (SUPEN).

    El archivo contiene varias combinaciones de tipo y periodicidad. Solo se
    usan los registros con tipo='REAL' (deflactados por inflación) y
    periodicidad='ANUAL', que son los comparables entre operadoras y los que
    tiene sentido usar como insumo del GBM. La fila 'TOTAL' es un agregado
    del sistema, no una operadora, por lo que se excluye.

    Si una operadora no tiene registros que cumplan esos filtros, el llamador
    recibirá un array vacío y debe manejar ese caso mostrando un error claro
    al usuario (ver ejecutar_simulacion en views.py).

    Retorna DataFrame con columnas: fecha, entidad, rentabilidad (decimal).
    """
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_OPC.xlsx")

    # Normalizar texto para evitar problemas por mayúsculas o espacios al filtrar
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
    Lee las comisiones administrativas de cada operadora desde
    Comisiones_OPC.xlsx (SUPEN).

    En el ROP, las operadoras cobran su comisión como un porcentaje anual
    sobre el saldo acumulado del afiliado (no sobre el aporte mensual). Esto
    significa que reduce directamente el rendimiento neto que el fondo obtiene.
    En el modelo GBM se descuenta del drift: mu_neta = mu - comision_anual.

    El archivo registra distintos tipos de comisión, pero solo 'SALDO' tiene
    valores válidos según el diagnóstico de los datos. Se usa el dato más
    reciente disponible por operadora para reflejar la tarifa vigente.

    Retorna dict: { 'POPULAR': 0.015, 'BCR-PENSION': 0.010, ... }
    Si falta el dato de una operadora, se asume 1% anual como valor conservador.
    """
    df = pd.read_excel(RUTA_DATOS / "Comisiones_OPC.xlsx")

    df["tipo"]    = df["tipo"].str.strip().str.upper()
    df["entidad"] = df["entidad"].str.strip()

    df_saldo = df[df["tipo"] == "SALDO"].dropna(subset=["comisión"]).copy()

    if df_saldo.empty:
        operadoras = df["entidad"].unique().tolist()
        return {op: 0.01 for op in operadoras}

    df_saldo["fecha"]    = pd.to_datetime(df_saldo["fecha"])
    df_saldo["comisión"] = df_saldo["comisión"] / 100   # % → decimal

    # Quedarse con el registro más reciente por operadora
    df_saldo = (
        df_saldo.sort_values("fecha")
        .groupby("entidad")
        .last()
        .reset_index()
    )

    return dict(zip(df_saldo["entidad"], df_saldo["comisión"]))


def cargar_ipc():
    """
    Lee el Índice de Precios al Consumidor desde IPC.xlsx (BCCR).

    El archivo del BCCR incluye 4 filas de metadatos antes de los datos, por
    eso se omiten con skiprows=4. La variación mensual del IPC se usa como
    proxy de la inflación para convertir saldos nominales futuros a colones
    de hoy (poder adquisitivo constante).

    Retorna DataFrame con columnas: fecha (datetime), var_mensual (decimal).
    """
    df = pd.read_excel(
        RUTA_DATOS / "IPC.xlsx",
        skiprows=4
    )

    df.columns = ["fecha", "nivel", "var_mensual", "var_interanual", "var_acumulada"]

    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["var_mensual"] = df["var_mensual"] / 100   # % → decimal

    return df[["fecha", "var_mensual"]].sort_values("fecha").reset_index(drop=True)


def cargar_tbp():
    """
    Lee la Tasa Básica Pasiva desde TBP.xlsx (BCCR).

    La TBP es la tasa de referencia del sistema financiero costarricense,
    publicada diariamente por el BCCR. El archivo tiene 4 filas de metadatos
    al inicio (skiprows=4) y frecuencia diaria, por lo que se promedia a
    frecuencia mensual para alinearla con los demás datos de la simulación.

    Retorna DataFrame con columnas: fecha (fin de mes), tbp (decimal).
    """
    df = pd.read_excel(
        RUTA_DATOS / "TBP.xlsx",
        skiprows=4
    )

    df.columns = ["fecha", "tbp"]
    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["tbp"] = df["tbp"] / 100   # % → decimal

    # Colapsar de frecuencia diaria a mensual tomando el promedio de cada mes
    df = (
        df.set_index("fecha")
        .resample("ME")["tbp"]
        .mean()
        .reset_index()
    )

    return df


def listar_operadoras():
    """Retorna la lista de operadoras con datos disponibles en Rendimientos_OPC.xlsx."""
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_OPC.xlsx")
    operadoras = sorted(df[df["entidad"] != "TOTAL"]["entidad"].unique().tolist())
    return operadoras


def validar_operadora(entidad: str) -> dict:
    """
    Verifica si una operadora tiene datos suficientes para ejecutar la simulación.
    Útil para dar mensajes de error descriptivos cuando el filtro de
    cargar_rendimientos() no retorna nada para la operadora seleccionada.
    """
    df = cargar_rendimientos()
    datos_op = df[df["entidad"] == entidad]["rentabilidad"].dropna()

    return {
        "tiene_datos":     len(datos_op) > 0,
        "n_obs":           len(datos_op),
        "entidad":         entidad,
        "todas_entidades": sorted(df["entidad"].unique().tolist()),
    }