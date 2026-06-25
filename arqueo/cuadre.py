"""Motor de cuadre. Cruza las 5 fuentes y devuelve incidencias."""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable
import pandas as pd

from . import config as cfg

TOL = 0.01


@dataclass
class Diferencia:
    fecha: dt.date
    seccion: str
    concepto: str
    esperado: float  # según ERP
    encontrado: float  # según fuente externa
    delta: float
    descripcion: str
    severity: str  # ok | warn | error


def _agg_erp(df_erp: pd.DataFrame, fecha: dt.date) -> dict:
    """Agrega importes del ERP por sección Iveralso y concepto del día."""
    if df_erp.empty:
        return {s: {} for s in cfg.IVERALSO_SECS}
    df = df_erp[(df_erp["FECHA"].dt.date == fecha) & (df_erp["SEC"].isin(cfg.IVERALSO_SECS))]
    agg: dict = defaultdict(lambda: defaultdict(float))
    for _, row in df.iterrows():
        sec = row["SEC"]
        tp = row["TIPO_PERMISO"]
        tc = row["TIPO_CONCEPTO"]
        fp = row["FP"] or ""
        ing = row["ING"] or 0.0
        if tp == "B" and tc != "Tasa":
            agg[sec][f"B/{fp}"] += ing
        if tp != "B" and tp is not None:
            agg[sec][f"OTROS/{fp}"] += ing
        if tc == "Tasa":
            agg[sec][f"TASA/{fp}"] += ing
    return {sec: dict(d) for sec, d in agg.items()}


def cuadrar_dia(
    fecha: dt.date,
    df_erp: pd.DataFrame,
    bbva_remesas: list[dict],
    cajamar: pd.DataFrame,
    drive_pb: dict[str, pd.DataFrame],
    drive_otros: dict[str, pd.DataFrame],
) -> list[Diferencia]:
    """Compara ERP vs fuentes externas y devuelve lista de diferencias del día."""
    diff: list[Diferencia] = []
    erp = _agg_erp(df_erp, fecha)

    bbva_by_sec: dict[str, float] = defaultdict(float)
    for r in bbva_remesas:
        if r.get("importe"):
            bbva_by_sec[r["sec"] or "?"] += r["importe"]
        for mov in r.get("movimientos", []):
            if mov.get("sec"):
                bbva_by_sec[mov["sec"]] += mov.get("importe", 0)

    cajamar_by_sec: dict[str, float] = defaultdict(float)
    if cajamar is not None and not cajamar.empty:
        # Cajamar abona D+1: filtramos por fecha del día siguiente al arqueado
        fecha_abono = fecha + dt.timedelta(days=1)
        for _, row in cajamar.iterrows():
            if row.get("fecha") == fecha_abono and row.get("sec"):
                cajamar_by_sec[row["sec"]] += row["importe"]

    for sec in cfg.IVERALSO_SECS:
        ag = erp.get(sec, {})
        erp_b_efect = ag.get("B/EFECTIVO", 0.0)
        erp_b_tarj = ag.get("B/TARJETA", 0.0)
        erp_b_bizum = ag.get("B/BIZUM", 0.0)
        erp_b_web = ag.get("B/Web", 0.0)
        erp_b_trans = ag.get("B/TRANSFEREN", 0.0)
        erp_ot_efect = ag.get("OTROS/EFECTIVO", 0.0)
        erp_tasa_tarj = ag.get("TASA/TARJETA", 0.0)
        erp_tasa_trans = ag.get("TASA/TRANSFEREN", 0.0)
        bbva = bbva_by_sec.get(sec, 0.0)
        cajm = cajamar_by_sec.get(sec, 0.0)

        df_pb = drive_pb.get(sec)
        d_pb_ing = 0.0
        if df_pb is not None and not df_pb.empty:
            d_pb_ing = float(df_pb[df_pb["fecha"] == fecha]["ingreso"].sum())

        df_ot = drive_otros.get(sec)
        d_ot = 0.0
        if df_ot is not None and not df_ot.empty:
            d_ot = float(df_ot[df_ot["fecha"] == fecha]["cobro_efectivo"].sum())

        # Tarjeta Permiso B vs BBVA
        delta = erp_b_tarj - bbva
        diff.append(Diferencia(fecha, sec, "Permiso B - Tarjeta (BBVA)",
                               erp_b_tarj, bbva, delta,
                               "" if abs(delta) <= TOL else "Tarjeta no cuadra con remesas BBVA",
                               "ok" if abs(delta) <= TOL else "error"))

        # Efectivo Permiso B vs Drive PB — aplicar regla intensivos
        total_efect_erp = erp_b_efect + erp_ot_efect
        total_efect_drive = d_pb_ing + d_ot
        if abs(total_efect_erp - total_efect_drive) <= TOL and abs(erp_b_efect - d_pb_ing) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Efectivo (Drive)",
                                   erp_b_efect, d_pb_ing, erp_b_efect - d_pb_ing,
                                   "Diferencia compensada con intensivos cobrados en caja B",
                                   "warn"))
        else:
            d = erp_b_efect - d_pb_ing
            diff.append(Diferencia(fecha, sec, "Permiso B - Efectivo (Drive)",
                                   erp_b_efect, d_pb_ing, d,
                                   "" if abs(d) <= TOL else "Efectivo Permiso B no cuadra",
                                   "ok" if abs(d) <= TOL else "error"))

        # Efectivo Otros Permisos
        if abs(total_efect_erp - total_efect_drive) <= TOL and abs(erp_ot_efect - d_ot) > TOL:
            diff.append(Diferencia(fecha, sec, "Otros Permisos - Efectivo (Drive)",
                                   erp_ot_efect, d_ot, erp_ot_efect - d_ot,
                                   "Diferencia compensada con intensivos cobrados en caja B",
                                   "warn"))
        else:
            d = erp_ot_efect - d_ot
            diff.append(Diferencia(fecha, sec, "Otros Permisos - Efectivo (Drive)",
                                   erp_ot_efect, d_ot, d,
                                   "" if abs(d) <= TOL else "Efectivo Otros Permisos no cuadra",
                                   "ok" if abs(d) <= TOL else "error"))

        # Tasas Tarjeta vs Cajamar
        d = erp_tasa_tarj - cajm
        diff.append(Diferencia(fecha, sec, "Tasas - Tarjeta (Cajamar)",
                               erp_tasa_tarj, cajm, d,
                               "" if abs(d) <= TOL else "Tasa Tarjeta no cuadra con Cajamar",
                               "ok" if abs(d) <= TOL else "error"))

        # Transferencias prohibidas
        if abs(erp_b_trans) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Transferencia",
                                   0.0, erp_b_trans, erp_b_trans,
                                   "No debería haber transferencias en Permiso B",
                                   "error"))
        if abs(erp_tasa_trans) > TOL:
            diff.append(Diferencia(fecha, sec, "Tasas - Transferencia",
                                   0.0, erp_tasa_trans, erp_tasa_trans,
                                   "No debería haber transferencias en Tasas",
                                   "error"))

        # Bizum y Web Conjunta sólo se reportan como avisos por sección
        if abs(erp_b_bizum) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Bizum",
                                   erp_b_bizum, 0.0, erp_b_bizum,
                                   "Pendiente verificación contra Santander (sin FUC)",
                                   "warn"))
        if abs(erp_b_web) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Web Conjunta",
                                   erp_b_web, 0.0, erp_b_web,
                                   "Se verifica en email resumen (datáfono único)",
                                   "warn"))

    return diff


def diferencias_a_df(difs: Iterable[Diferencia]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Fecha": d.fecha,
        "Sección": d.seccion,
        "Concepto": d.concepto,
        "ERP": d.esperado,
        "Externo": d.encontrado,
        "Δ": d.delta,
        "Comentario": d.descripcion,
        "Severidad": d.severity,
    } for d in difs])
