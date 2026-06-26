"""Genera el informe resumen diario (sección × permiso × FP, con saldos y continuidad)."""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from . import config as cfg

TOL = 0.01


@dataclass
class CeldaResumen:
    fecha: dt.date
    seccion: str
    permiso: str
    fp: str
    erp: float
    externo: float
    delta: float
    estado: str   # ok | warn | error | pendiente
    detalle: str  # texto descriptivo para tooltip / drilldown


def _agg_erp(df_erp: pd.DataFrame, fechas: Iterable[dt.date]) -> dict:
    """Devuelve un dict[(fecha, sec, permiso, fp)] = importe sumado del ERP."""
    if df_erp.empty: return {}
    df = df_erp[df_erp["FECHA"].dt.date.isin(fechas) & df_erp["SEC"].isin(cfg.IVERALSO_SECS)]
    out: dict = defaultdict(float)
    for _, row in df.iterrows():
        sec = row["SEC"]
        tp = row["TIPO_PERMISO"]; tc = row["TIPO_CONCEPTO"]; fp_raw = row["FP"] or ""
        ing = row["ING"] or 0.0
        # Normalizar FP
        if "EFECTIVO" in fp_raw.upper(): fp = "Efectivo"
        elif "TARJETA" in fp_raw.upper() and "TASAS" not in fp_raw.upper(): fp = "Tarjeta"
        elif "BIZUM" in fp_raw.upper(): fp = "Bizum"
        elif "TRANSFEREN" in fp_raw.upper(): fp = "Transferencia"
        elif "WEB" in fp_raw or "Página We" in fp_raw: fp = "Web"
        else: fp = fp_raw
        if tc == "Tasa":
            permiso = "Tasas"
        elif tp == "B":
            permiso = "Permiso B"
        else:
            permiso = "Otros Permisos"
        out[(row["FECHA"].date(), sec, permiso, fp)] += ing
    return out


def generar(
    fechas: list[dt.date],
    df_erp: pd.DataFrame,
    bbva_remesas: list[dict],
    cajamar_df: pd.DataFrame,
    drive_pb_map: dict[str, pd.DataFrame],
    drive_ot_map: dict[str, pd.DataFrame],
    santander_bizum_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Devuelve un DataFrame con todas las celdas del informe resumen diario."""
    erp_agg = _agg_erp(df_erp, fechas)

    # BBVA por sección por día. Si hay movimientos, usar SOLO los movimientos (tienen fecha individual).
    # Si no hay movimientos, usar el total con fecha = fecha_remesa - 1 día.
    bbva_by_day_sec: dict = defaultdict(float)
    for r in bbva_remesas:
        sec = r.get("sec")
        movs = r.get("movimientos") or []
        if movs:
            for mov in movs:
                sec_m = mov.get("sec") or sec
                f = mov.get("fecha")
                if f and sec_m and mov.get("importe") is not None:
                    bbva_by_day_sec[(f, sec_m)] += mov["importe"]
        else:
            fecha_remesa = r.get("fecha_remesa")
            if fecha_remesa and r.get("importe") and sec:
                fcobro = fecha_remesa - dt.timedelta(days=1)
                bbva_by_day_sec[(fcobro, sec)] += r["importe"]

    # Cajamar por sección por día (filtrando por fecha cobro = D-1 abono)
    caj_by_day_sec: dict = defaultdict(float)
    if cajamar_df is not None and not cajamar_df.empty:
        for _, row in cajamar_df.iterrows():
            f_abono = row["fecha"]
            sec = row.get("sec")
            if not sec or pd.isna(f_abono): continue
            fcobro = f_abono - dt.timedelta(days=1)
            caj_by_day_sec[(fcobro, sec)] += row["importe"]

    # Drive PB y Otros por sección por día
    drive_pb_day: dict = defaultdict(float)
    for sec, df in drive_pb_map.items():
        if df is None or df.empty: continue
        for _, row in df.iterrows():
            drive_pb_day[(row["fecha"], sec)] += row.get("ingreso", 0)

    drive_ot_day: dict = defaultdict(float)
    for sec, df in drive_ot_map.items():
        if df is None or df.empty: continue
        for _, row in df.iterrows():
            drive_ot_day[(row["fecha"], sec)] += row.get("cobro_efectivo", 0)

    rows: list[CeldaResumen] = []
    for fecha in fechas:
        for sec in cfg.IVERALSO_SECS:
            for permiso, fp in cfg.LINEAS_RESUMEN:
                # ERP esperado
                erp_val = erp_agg.get((fecha, sec, permiso, fp), 0.0)
                # Si es Tarjeta + Tasas, mover concepto a "Tasas"
                ext_val = 0.0
                detalle = ""
                if permiso == "Permiso B" and fp == "Tarjeta":
                    ext_val = bbva_by_day_sec.get((fecha, sec), 0.0)
                elif permiso == "Permiso B" and fp == "Efectivo":
                    ext_val = drive_pb_day.get((fecha, sec), 0.0)
                    # Regla intensivos: si total efectivo (B + Otros) cuadra, dif es por intensivos
                    erp_ot = erp_agg.get((fecha, sec, "Otros Permisos", "Efectivo"), 0.0)
                    drv_ot = drive_ot_day.get((fecha, sec), 0.0)
                    if abs((erp_val + erp_ot) - (ext_val + drv_ot)) <= TOL and abs(erp_val - ext_val) > TOL:
                        detalle = f"Compensado con caja Permiso B (intensivos {ext_val-erp_val:+.2f}€)"
                elif permiso == "Otros Permisos" and fp == "Efectivo":
                    ext_val = drive_ot_day.get((fecha, sec), 0.0)
                    erp_b = erp_agg.get((fecha, sec, "Permiso B", "Efectivo"), 0.0)
                    drv_b = drive_pb_day.get((fecha, sec), 0.0)
                    if abs((erp_b + erp_val) - (drv_b + ext_val)) <= TOL and abs(erp_val - ext_val) > TOL:
                        detalle = f"Compensado con caja Permiso B (intensivos {ext_val-erp_val:+.2f}€)"
                elif permiso == "Tasas" and fp == "Tarjeta":
                    ext_val = caj_by_day_sec.get((fecha, sec), 0.0)
                elif fp == "Bizum":
                    ext_val = 0.0
                    detalle = "Bizum pendiente (sin FUC todavía)"

                delta = erp_val - ext_val
                if fp == "Bizum":
                    estado = "pendiente" if abs(erp_val) > TOL else "ok"
                elif abs(delta) <= TOL:
                    estado = "ok"
                elif "Compensado" in detalle:
                    estado = "warn"
                else:
                    estado = "error"
                    if not detalle: detalle = f"Δ {delta:+,.2f} €"
                rows.append(CeldaResumen(fecha, sec, permiso, fp, erp_val, ext_val, delta, estado, detalle))

    return pd.DataFrame([r.__dict__ for r in rows])


def saldos_continuidad(
    fechas: list[dt.date],
    drive_pb_map: dict[str, pd.DataFrame],
    drive_ot_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Devuelve, por sección y día, el saldo de cierre y si rompe continuidad."""
    from .parsers.drive_pb import saldos_por_dia as sp_pb
    from .parsers.drive_otros import saldos_por_dia as sp_ot

    out = []
    for sec in cfg.IVERALSO_SECS:
        for tipo, m, fn in (("PB", drive_pb_map, sp_pb), ("OT", drive_ot_map, sp_ot)):
            df = m.get(sec)
            if df is None or df.empty:
                continue
            saldos = fn(df).sort_values("fecha")
            saldos_map = dict(zip(saldos["fecha"], saldos["saldo_cierre"]))
            for f in fechas:
                cierre = saldos_map.get(f)
                cierre_ayer = saldos_map.get(f - dt.timedelta(days=1))
                inicio = cierre_ayer
                rompe = (inicio is not None and cierre is not None and
                         abs((cierre - (sum(df[df["fecha"]==f]["ingreso"]) if "ingreso" in df.columns else sum(df[df["fecha"]==f]["cobro_efectivo"])) +
                              (sum(df[df["fecha"]==f]["pago"]) if "pago" in df.columns else 0)) - inicio) > TOL) if False else False
                # Simplificación: alerta solo cuando hay cierre ayer y cierre hoy y la diferencia entre ambos
                # no encaja con movimientos del día
                alerta = ""
                if inicio is not None and cierre is not None:
                    movs = 0.0
                    if "ingreso" in df.columns:
                        movs = float(df[df["fecha"]==f]["ingreso"].sum()) - float(df[df["fecha"]==f]["pago"].sum())
                    elif "cobro_efectivo" in df.columns:
                        movs = float(df[df["fecha"]==f]["cobro_efectivo"].sum())
                    esperado = inicio + movs
                    if abs(esperado - cierre) > TOL:
                        alerta = f"Saldo no encaja: {inicio:.2f}€ +mov {movs:+.2f}€ → esperado {esperado:.2f}€, real {cierre:.2f}€"
                out.append({
                    "seccion": sec, "tipo": tipo, "fecha": f,
                    "saldo_inicio": inicio, "saldo_cierre": cierre, "alerta": alerta,
                })
    return pd.DataFrame(out)
