"""Parser de los Excel Drive Otros Permisos (1 por sección)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd


def detect_seccion(filename: str) -> str | None:
    m = re.search(r"S(\d{2})", filename)
    if m:
        return f"S{m.group(1)}"
    m2 = re.search(r"SEC\.?\s*(\d{2})", filename, re.IGNORECASE)
    if m2:
        return f"S{m2.group(1)}"
    return None


def parse(path: str | Path) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="calamine", header=None)
    torcal_sheet = next((s for s in sheets if "TORCAL" in s.upper()), None)
    if not torcal_sheet:
        return pd.DataFrame()
    df = sheets[torcal_sheet]
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    # Caso especial S31: primera columna es ' '
    use_positional = (
        len([c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()]) == 0
    )

    rows = []
    for _, row in df.iterrows():
        if use_positional:
            f = row.iloc[0]
            c_cobro = row.iloc[3] if len(row) > 3 else None
            obs = row.iloc[5] if len(row) > 5 else None
        else:
            col_fecha = next((c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()), None)
            col_cobro = next((c for c in df.columns if isinstance(c, str) and "cobro" in c.lower() and "efect" in c.lower()), None)
            col_obs = next((c for c in df.columns if isinstance(c, str) and "observ" in c.lower()), None)
            if not col_fecha or not col_cobro:
                continue
            f = row[col_fecha]
            c_cobro = row[col_cobro]
            obs = row[col_obs] if col_obs else None
        if not isinstance(f, (dt.datetime, pd.Timestamp)):
            continue
        try:
            c_cobro = float(c_cobro) if pd.notna(c_cobro) else 0.0
        except (TypeError, ValueError):
            c_cobro = 0.0
        rows.append({
            "fecha": f.date(),
            "cobro_efectivo": c_cobro,
            "observaciones": obs,
        })
    return pd.DataFrame(rows)
