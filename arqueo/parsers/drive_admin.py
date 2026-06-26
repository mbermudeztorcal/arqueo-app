"""Parser del Excel Drive de Administración / Caja Responsable.

Sirve para cruzar las retiradas que las cajas de cada sección envían a Administración
contra los ingresos que esta recibe. Se espera estructura tabular con:
- fecha de la operación
- concepto / descripción
- importe (ingreso > 0)
- sección de origen (opcional)
"""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd


def parse(path: str | Path) -> pd.DataFrame:
    """Lee el Excel Drive de Administración y devuelve filas de ingresos."""
    p = Path(path)
    sheets = pd.read_excel(p, sheet_name=None, engine="calamine", header=None)
    # Tomar la primera hoja con una fila de cabecera reconocible
    for sn in sheets:
        df = sheets[sn]
        if df.empty:
            continue
        # Buscar la fila con cabeceras (contiene 'fecha' o 'importe')
        header_row = None
        for i in range(min(20, len(df))):
            row = df.iloc[i].astype(str).str.lower()
            if any("fecha" in v for v in row):
                header_row = i
                break
        if header_row is None:
            continue
        df.columns = df.iloc[header_row]
        df = df[header_row + 1:].reset_index(drop=True)

        col_fecha = next((c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()), None)
        col_concepto = next((c for c in df.columns if isinstance(c, str) and "concepto" in c.lower()), None)
        col_ingreso = next((c for c in df.columns if isinstance(c, str) and ("ingreso" in c.lower() or "importe" in c.lower())), None)
        col_seccion = next((c for c in df.columns if isinstance(c, str) and ("seccion" in c.lower() or "sección" in c.lower() or "origen" in c.lower())), None)
        if not col_fecha or not col_ingreso:
            continue

        rows = []
        for _, row in df.iterrows():
            f = row[col_fecha]
            if not isinstance(f, (dt.datetime, pd.Timestamp)):
                continue
            try:
                imp = float(row[col_ingreso]) if pd.notna(row[col_ingreso]) else 0.0
            except (TypeError, ValueError):
                imp = 0.0
            if imp <= 0:
                continue
            sec_raw = row[col_seccion] if col_seccion else ""
            sec = _extract_seccion(str(sec_raw)) if sec_raw else None
            rows.append({
                "fecha": f.date(),
                "concepto": row[col_concepto] if col_concepto else None,
                "importe": imp,
                "seccion": sec,
                "seccion_raw": sec_raw if col_seccion else None,
            })
        return pd.DataFrame(rows)
    return pd.DataFrame()


def _extract_seccion(s: str) -> str | None:
    m = re.search(r"S\.?\s*(\d{2})", s, re.IGNORECASE)
    if m: return f"S{m.group(1)}"
    return None
