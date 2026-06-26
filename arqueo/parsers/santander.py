"""Parser de extractos Santander (.xlsx). Sirve tanto para cuenta corriente como para Bizum."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd


def _to_date(s):
    if isinstance(s, str):
        try: return dt.datetime.strptime(s, "%d/%m/%Y").date()
        except ValueError: pass
    if isinstance(s, (dt.datetime, pd.Timestamp)):
        return s.date()
    return None


def parse(path: str | Path) -> pd.DataFrame:
    """Lee un extracto Santander estándar (movimientos con cabeceras en fila 7)."""
    sheets = pd.read_excel(path, sheet_name=None, engine="calamine", header=None)
    sn = next((s for s in sheets if "movimiento" in s.lower()), list(sheets.keys())[0])
    df = sheets[sn]
    # Encuentra la fila de cabeceras (la primera con "Fecha Operación")
    header_row = None
    for i in range(min(20, len(df))):
        row = df.iloc[i]
        if any(isinstance(v, str) and "Fecha" in v and "Operación" in v for v in row):
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()
    df.columns = df.iloc[header_row]
    df = df[header_row + 1:].reset_index(drop=True)
    df = df[df["Fecha Operación"].notna()].copy()

    df["fecha_op"] = df["Fecha Operación"].apply(_to_date)
    df["fecha_val"] = df["Fecha Valor"].apply(_to_date) if "Fecha Valor" in df.columns else df["fecha_op"]
    df["importe"] = pd.to_numeric(df["Importe"], errors="coerce")
    df["concepto"] = df["Concepto"].astype(str)

    return df[["fecha_op", "fecha_val", "concepto", "importe"]].rename(columns={"fecha_op":"fecha"})


def filtrar_bizum_abonos(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra solo los Abono Bizum entrantes."""
    if df.empty:
        return df
    return df[df["concepto"].str.startswith("Abono Bizum", na=False)].copy()


def extraer_alumno_bizum(concepto):
    if not isinstance(concepto, str): return ""
    m = re.search(r"Para ([\w\sÁÉÍÓÚÑáéíóúñ]+?)\s+\d{1,2}/\d{1,2}/\d{4}", concepto)
    return m.group(1).strip().upper() if m else ""
