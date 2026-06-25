"""Parser del ERP de Torcal: HTML con extensión .xls."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
from typing import Iterable
import pandas as pd
from bs4 import BeautifulSoup

COLS = ["FECHA", "US", "SEC", "TIPO_PERMISO", "CONCEPTO", "TIPO_CONCEPTO", "DOCUMENTO",
        "BASE", "PCT", "IMP", "FP", "ING", "GASTOS", "SALDO", "ALUMNO", "NIF", "CIF"]


def _to_num(s):
    if s is None or s == "":
        return None
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse(path: str | Path) -> pd.DataFrame:
    """Lee el archivo del ERP (HTML disfrazado de .xls) y devuelve un DataFrame."""
    p = Path(path)
    # Probamos UTF-8 primero, fallback a latin1
    for enc in ("utf-8", "latin1"):
        try:
            with open(p, "r", encoding=enc, errors="replace") as f:
                content = f.read()
            break
        except Exception:
            continue
    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return pd.DataFrame(columns=COLS)
    main = max(tables, key=lambda t: len(t.find_all("tr")))
    rows = main.find_all("tr")
    data = []
    for row in rows[2:]:
        cells = row.find_all(["td", "th"])
        if len(cells) == 18:
            row_data = [cells[i].get_text(strip=True) for i in [0,1,2,3,4,5,6,8,9,10,11,12,13,14,15,16,17]]
            data.append(row_data)
    df = pd.DataFrame(data, columns=COLS)
    for c in ("BASE", "IMP", "ING", "GASTOS", "SALDO"):
        df[c] = df[c].apply(_to_num)
    df["PCT"] = df["PCT"].apply(_to_num)
    df["FECHA"] = pd.to_datetime(df["FECHA"], format="%d-%m-%Y", errors="coerce")
    df = df[df["FECHA"].notna()].reset_index(drop=True)
    return df


def filtrar(df: pd.DataFrame, fecha: dt.date | None = None, secciones: Iterable[str] | None = None) -> pd.DataFrame:
    out = df
    if fecha is not None:
        out = out[out["FECHA"].dt.date == fecha]
    if secciones is not None:
        secs = set(secciones)
        out = out[out["SEC"].isin(secs)]
    return out.reset_index(drop=True)
