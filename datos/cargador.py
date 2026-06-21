import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache

RUTA_DATOS = Path(__file__).parent / "data"

@lru_cache(maxsize=None)
def cargar_rendimientos():
    df = pd.read_excel(RUTA_DATOS / "Rendimientos_OPC.xlsx")
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
    df["rentabilidad"] = df["rentabilidad"] / 100
    return df[["fecha", "entidad", "rentabilidad"]].sort_values("fecha").reset_index(drop=True)

@lru_cache(maxsize=None)
def cargar_comisiones():
    df = pd.read_excel(RUTA_DATOS / "Comisiones_OPC.xlsx")
    df["tipo"]    = df["tipo"].str.strip().str.upper()
    df["entidad"] = df["entidad"].str.strip()
    df_saldo = df[df["tipo"] == "SALDO"].dropna(subset=["comisión"]).copy()
    if df_saldo.empty:
        return {op: 0.01 for op in df["entidad"].unique().tolist()}
    df_saldo["fecha"]    = pd.to_datetime(df_saldo["fecha"])
    df_saldo["comisión"] = df_saldo["comisión"] / 100
    df_saldo = df_saldo.sort_values("fecha").groupby("entidad").last().reset_index()
    return dict(zip(df_saldo["entidad"], df_saldo["comisión"]))

@lru_cache(maxsize=None)
def cargar_ipc():
    df = pd.read_excel(RUTA_DATOS / "IPC.xlsx", skiprows=4)
    df.columns = ["fecha", "nivel", "var_mensual", "var_interanual", "var_acumulada"]
    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["var_mensual"] = df["var_mensual"] / 100
    return df[["fecha", "var_mensual"]].sort_values("fecha").reset_index(drop=True)

@lru_cache(maxsize=None)
def cargar_tbp():
    df = pd.read_excel(RUTA_DATOS / "TBP.xlsx", skiprows=4)
    df.columns = ["fecha", "tbp"]
    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["tbp"] = df["tbp"] / 100
    df = df.set_index("fecha").resample("ME")["tbp"].mean().reset_index()
    return df

@lru_cache(maxsize=None)
def listar_operadoras():
    df = cargar_rendimientos()
    return sorted(df["entidad"].unique().tolist())

def validar_operadora(entidad: str) -> dict:
    df = cargar_rendimientos()
    datos_op = df[df["entidad"] == entidad]["rentabilidad"].dropna()
    return {
        "tiene_datos":     len(datos_op) > 0,
        "n_obs":           len(datos_op),
        "entidad":         entidad,
        "todas_entidades": sorted(df["entidad"].unique().tolist()),
    }