"""Parser del extracto Cajamar (.xls)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd
from .. import config as cfg


def parse(path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, engine="calamine", header=None)
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    out = []
    for _, row in df.iterrows():
        fecha = row.get("Fecha")
        concepto = row.get("Concepto")
        importe = row.get("Importe")
        if pd.isna(fecha) or pd.isna(concepto) or not isinstance(concepto, str):
            continue
        if isinstance(fecha, dt.datetime):
            d = fecha.date()
        elif isinstance(fecha, pd.Timestamp):
            d = fecha.date()
        elif isinstance(fecha, str):
            try:
                d = dt.datetime.strptime(fecha.split()[0], "%Y-%m-%d").date()
            except ValueError:
                continue
        else:
            continue
        if "ABONO VENTAS" not in concepto:
            continue
        m = re.search(r"(\d{9})", concepto)
        if not m:
            continue
        codigo = m.group(1)
        sec = cfg.CAJ_TO_SEC.get(codigo)
        try:
            imp = float(importe)
        except (TypeError, ValueError):
            continue
        out.append({
            "fecha": d,
            "codigo_comercio": codigo,
            "sec": sec,
            "importe": imp,
            "concepto": concepto[:80],
        })
    return pd.DataFrame(out)
