"""Detecta retiradas y pagos de las hojas Drive Permiso B."""
from __future__ import annotations
import datetime as dt
import pandas as pd
from . import config as cfg


def extraer(drive_pb_map: dict[str, pd.DataFrame], fechas: list[dt.date]) -> pd.DataFrame:
    """Devuelve todas las filas de Drive PB con pago>0 en las fechas dadas."""
    rows = []
    for sec, df in drive_pb_map.items():
        if df is None or df.empty: continue
        sub = df[(df["fecha"].isin(fechas)) & (df["pago"] > 0)]
        for _, r in sub.iterrows():
            rows.append({
                "seccion": sec,
                "fecha": r["fecha"],
                "concepto": r.get("concepto"),
                "cliente": r.get("cliente"),
                "notas": r.get("notas"),
                "importe": r["pago"],
                "estado": "pendiente_validar",
                "comentario": "",
            })
    return pd.DataFrame(rows)
