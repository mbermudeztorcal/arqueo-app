"""Detecta retiradas (pago>0) tanto en Drive Permiso B como en Drive Otros Permisos."""
from __future__ import annotations
import datetime as dt
import pandas as pd
from . import config as cfg


def extraer(
    drive_pb_map: dict[str, pd.DataFrame] | None,
    drive_ot_map: dict[str, pd.DataFrame] | None = None,
    fechas: list[dt.date] | None = None,
) -> pd.DataFrame:
    """Devuelve todas las retiradas de Caja PB y Caja Otros para las fechas dadas
    (o todas si fechas es None)."""
    rows = []
    fechas_set = set(fechas) if fechas else None

    if drive_pb_map:
        for sec, df in drive_pb_map.items():
            if df is None or df.empty or "pago" not in df.columns: continue
            sub = df[df["pago"] > 0]
            if fechas_set is not None:
                sub = sub[sub["fecha"].isin(fechas_set)]
            for _, r in sub.iterrows():
                rows.append({
                    "fecha": r["fecha"], "seccion": sec, "caja": "Permiso B",
                    "concepto": r.get("concepto"), "cliente": r.get("cliente"),
                    "notas": r.get("notas"), "importe": float(r["pago"]),
                    "estado": "pendiente_validar",
                })

    if drive_ot_map:
        for sec, df in drive_ot_map.items():
            if df is None or df.empty: continue
            col_pago = "pago" if "pago" in df.columns else None
            if not col_pago: continue
            sub = df[df[col_pago] > 0]
            if fechas_set is not None:
                sub = sub[sub["fecha"].isin(fechas_set)]
            for _, r in sub.iterrows():
                rows.append({
                    "fecha": r["fecha"], "seccion": sec, "caja": "Otros Permisos",
                    "concepto": r.get("concepto") or r.get("observaciones"),
                    "cliente": None, "notas": r.get("observaciones"),
                    "importe": float(r[col_pago]),
                    "estado": "pendiente_validar",
                })

    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(["fecha", "seccion", "caja"]).reset_index(drop=True)
    return df
