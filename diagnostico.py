# diagnostico.py — Ejecutar con: python diagnostico.py
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sistema_pensiones.settings")
django.setup()

import pandas as pd
from pathlib import Path

RUTA = Path("datos/data")

# ── 1. Revisar valores únicos de columnas clave en Rendimientos ──────────────
df_r = pd.read_excel(RUTA / "Rendimientos_Datos.xlsx")

print("=== RENDIMIENTOS ===")
print("Columnas:", list(df_r.columns))
print("\nValores únicos de 'tipo':", df_r["tipo"].unique())
print("Valores únicos de 'periodicidad':", df_r["periodicidad"].unique())
print("Valores únicos de 'codigoregimen':", df_r["codigoregimen"].unique())
print("Valores únicos de 'régimen':", df_r["régimen"].unique() if "régimen" in df_r.columns else "columna no encontrada")
print("Valores únicos de 'entidad':", df_r["entidad"].unique())

# ── 2. Probar el filtro actual y ver cuántas filas retorna ───────────────────
print("\n=== CONTEO DE FILAS POR FILTRO ===")
for tipo in df_r["tipo"].unique():
    for per in df_r["periodicidad"].unique():
        for cod in df_r["codigoregimen"].unique():
            n = len(df_r[
                (df_r["tipo"] == tipo) &
                (df_r["periodicidad"] == per) &
                (df_r["codigoregimen"] == cod) &
                (df_r["entidad"] != "TOTAL")
            ])
            if n > 0:
                print(f"  tipo={tipo!r} | periodicidad={per!r} | codigoregimen={cod} -> {n} filas")

# ── 3. Revisar Comisiones ────────────────────────────────────────────────────
df_c = pd.read_excel(RUTA / "Comisión_datos.xlsx")

print("\n=== COMISIONES ===")
print("Valores únicos de 'tipo':", df_c["tipo"].unique())
print("Valores únicos de 'codigoregimen':", df_c["codigoregimen"].unique())
print("\nNaN por tipo de comisión:")
print(df_c.groupby("tipo")["comisión"].apply(lambda x: x.isna().sum()))
print("\nValores no-NaN por tipo de comisión:")
print(df_c.groupby("tipo")["comisión"].apply(lambda x: x.notna().sum()))

# ── 4. Mostrar una muestra de comisiones válidas por tipo ────────────────────
for tipo in df_c["tipo"].unique():
    muestra = df_c[df_c["tipo"] == tipo].dropna(subset=["comisión"]).head(3)
    print(f"\nMuestra tipo='{tipo}':")
    print(muestra[["entidad", "tipo", "comisión", "codigoregimen", "fecha"]].to_string())