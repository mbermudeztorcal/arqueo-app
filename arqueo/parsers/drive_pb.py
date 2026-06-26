"""Parser de los Excel Drive Permiso B (1 por sección)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd

_VALID_SECS = {"05","07","10","12","15","17","25","28","31","42","47"}


def detect_seccion(filename: str) -> str | None:
    nombre = filename.upper()
    for m in re.finditer(r"\b(\d{2})\b", nombre):
        codigo = m.group(1)
        if codigo in _VALID_SECS:
            return f"S{codigo}"
    return None


def parse(path: str | Path) -> pd.DataFrame:
    """Devuelve filas con fecha, ingreso, pago y saldo (efectivo)."""
    sheets = pd.read_excel(path, sheet_name=None, engine="calamine", header=None)
    caja_sheet = None
    for sn in sheets:
        if "CAJA" in sn.upper() and "CONFIG" not in sn.upper():
            caja_sheet = sn
            break
    if not caja_sheet:
        return pd.DataFrame()
    df = sheets[caja_sheet]
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    col_fecha = [c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()]
    col_ing = [c for c in df.columns if isinstance(c, str) and "ingreso" in c.lower() and "efect" in c.lower()]
    col_pag = [c for c in df.columns if isinstance(c, str) and "pago" in c.lower() and "efect" in c.lower()]
    col_saldo = [c for c in df.columns if isinstance(c, str) and "saldo" in c.lower() and "efect" in c.lower()]
    col_concepto = [c for c in df.columns if isinstance(c, str) and c.lower() == "concepto"]
    col_cliente = [c for c in df.columns if isinstance(c, str) and "cliente" in c.lower()]
    col_notas = [c for c in df.columns if isinstance(c, str) and "nota" in c.lower()]

    if not col_fecha or not col_ing:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        f = row[col_fecha[0]]
        if not isinstance(f, (dt.datetime, pd.Timestamp)):
            continue
        try: ingreso = float(row[col_ing[0]]) if pd.notna(row[col_ing[0]]) else 0.0
        except (TypeError, ValueError): ingreso = 0.0
        try: pago = float(row[col_pag[0]]) if col_pag and pd.notna(row[col_pag[0]]) else 0.0
        except (TypeError, ValueError): pago = 0.0
        try: saldo = float(row[col_saldo[0]]) if col_saldo and pd.notna(row[col_saldo[0]]) else None
        except (TypeError, ValueError): saldo = None
        rows.append({
            "fecha": f.date(),
            "ingreso": ingreso,
            "pago": pago,
            "saldo": saldo,
            "concepto": row[col_concepto[0]] if col_concepto else None,
            "cliente": row[col_cliente[0]] if col_cliente else None,
            "notas": row[col_notas[0]] if col_notas else None,
        })
    return pd.DataFrame(rows)


def saldos_por_dia(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve, por cada fecha presente, el saldo de cierre (último valor)."""
    if df.empty or "saldo" not in df.columns:
        return pd.DataFrame(columns=["fecha","saldo_cierre"])
    df_clean = df[df["saldo"].notna()]
    if df_clean.empty:
        return pd.DataFrame(columns=["fecha","saldo_cierre"])
    out = df_clean.groupby("fecha").agg(saldo_cierre=("saldo","last")).reset_index()
    return out
