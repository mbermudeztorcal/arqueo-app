"""Parser de los Excel Drive Otros Permisos (hoja CAJA TORCAL)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd


def detect_seccion(filename: str) -> str | None:
    m = re.search(r"S(\d{2})", filename)
    if m: return f"S{m.group(1)}"
    m2 = re.search(r"SEC\.?\s*(\d{2})", filename, re.IGNORECASE)
    if m2: return f"S{m2.group(1)}"
    return None


def parse(path: str | Path) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="calamine", header=None)
    torcal_sheet = next((s for s in sheets if "TORCAL" in s.upper()), None)
    if not torcal_sheet:
        return pd.DataFrame()
    df = sheets[torcal_sheet]
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    use_positional = (
        len([c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()]) == 0
    )

    rows = []
    for _, row in df.iterrows():
        if use_positional:
            f = row.iloc[0]
            c_cobro = row.iloc[3] if len(row) > 3 else None
            saldo = row.iloc[4] if len(row) > 4 else None
            obs = row.iloc[5] if len(row) > 5 else None
        else:
            col_fecha = next((c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()), None)
            col_cobro = next((c for c in df.columns if isinstance(c, str) and "cobro" in c.lower() and "efect" in c.lower()), None)
            col_saldo = next((c for c in df.columns if isinstance(c, str) and "saldo" in c.lower() and "efect" in c.lower()), None)
            col_obs = next((c for c in df.columns if isinstance(c, str) and "observ" in c.lower()), None)
            if not col_fecha or not col_cobro:
                continue
            f = row[col_fecha]; c_cobro = row[col_cobro]
            saldo = row[col_saldo] if col_saldo else None
            obs = row[col_obs] if col_obs else None
        if not isinstance(f, (dt.datetime, pd.Timestamp)):
            continue
        try: c_cobro = float(c_cobro) if pd.notna(c_cobro) else 0.0
        except (TypeError, ValueError): c_cobro = 0.0
        try: saldo_f = float(saldo) if saldo is not None and pd.notna(saldo) else None
        except (TypeError, ValueError): saldo_f = None
        rows.append({
            "fecha": f.date(),
            "cobro_efectivo": c_cobro,
            "saldo": saldo_f,
            "observaciones": obs,
        })
    return pd.DataFrame(rows)


def saldos_por_dia(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "saldo" not in df.columns:
        return pd.DataFrame(columns=["fecha","saldo_cierre"])
    df_clean = df[df["saldo"].notna()]
    if df_clean.empty:
        return pd.DataFrame(columns=["fecha","saldo_cierre"])
    return df_clean.groupby("fecha").agg(saldo_cierre=("saldo","last")).reset_index()
