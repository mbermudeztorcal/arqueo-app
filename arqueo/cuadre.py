"""Motor de cuadre. Cruza ERP con fuentes externas y devuelve diferencias por línea."""
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
    esperado: float
    encontrado: float
    delta: float
    descripcion: str
    severity: str   # ok | warn | error | pendiente | miss


def _agg_erp(df_erp: pd.DataFrame, fecha: dt.date) -> dict:
    if df_erp.empty:
        return {s: {} for s in cfg.IVERALSO_SECS}
    df = df_erp[(df_erp["FECHA"].dt.date == fecha) & (df_erp["SEC"].isin(cfg.IVERALSO_SECS))]
    agg: dict = defaultdict(lambda: defaultdict(float))
    for _, row in df.iterrows():
        sec = row["SEC"]; tp = row["TIPO_PERMISO"]; tc = row["TIPO_CONCEPTO"]
        fp = (row["FP"] or "").upper(); ing = row["ING"] or 0.0
        if tc == "Tasa":
            if "TARJETA" in fp: agg[sec]["TASA/TARJETA"] += ing
            elif "BIZUM" in fp: agg[sec]["TASA/BIZUM"] += ing
            elif "TRANSFEREN" in fp: agg[sec]["TASA/TRANSFEREN"] += ing
            else: agg[sec]["TASA/OTROS"] += ing
        elif tp == "B":
            if "EFECTIVO" in fp: agg[sec]["B/EFECTIVO"] += ing
            elif "TARJETA" in fp: agg[sec]["B/TARJETA"] += ing
            elif "BIZUM" in fp: agg[sec]["B/BIZUM"] += ing
            elif "TRANSFEREN" in fp: agg[sec]["B/TRANSFEREN"] += ing
            elif "WEB" in fp or "PÁGINA" in fp: agg[sec]["B/WEB"] += ing
        elif tp is not None:
            if "EFECTIVO" in fp: agg[sec]["OTROS/EFECTIVO"] += ing
            elif "BIZUM" in fp: agg[sec]["OTROS/BIZUM"] += ing
            elif "TARJETA" in fp: agg[sec]["OTROS/TARJETA"] += ing
    return {sec: dict(d) for sec, d in agg.items()}


def _bbva_por_seccion(bbva_remesas: list[dict], fecha: dt.date) -> tuple[dict, dict]:
    """Devuelve (totales_por_seccion, num_remesas_por_seccion) para el día indicado."""
    totales: dict = defaultdict(float)
    n_remesas: dict = defaultdict(int)
    for r in bbva_remesas:
        sec = r.get("sec")
        movs = r.get("movimientos") or []
        if movs:
            for m in movs:
                if m.get("fecha") == fecha and m.get("sec"):
                    totales[m["sec"]] += m.get("importe", 0)
                    n_remesas[m["sec"]] += 1
        else:
            fr = r.get("fecha_remesa")
            if fr and r.get("importe") and sec and (fr - dt.timedelta(days=1)) == fecha:
                totales[sec] += r["importe"]
                n_remesas[sec] += 1
    return dict(totales), dict(n_remesas)


def _fucs_por_sec(sec: str) -> list[str]:
    return [f for f, s in cfg.FUC_TO_SEC.items() if s == sec]


def cuadrar_dia(
    fecha: dt.date,
    df_erp: pd.DataFrame,
    bbva_remesas: list[dict],
    cajamar: pd.DataFrame,
    drive_pb: dict[str, pd.DataFrame],
    drive_otros: dict[str, pd.DataFrame],
    santander_bizum: pd.DataFrame | None = None,
) -> list[Diferencia]:
    diff: list[Diferencia] = []
    erp = _agg_erp(df_erp, fecha)
    bbva_by_sec, bbva_n = _bbva_por_seccion(bbva_remesas, fecha)

    # Cajamar: abono D+1
    cajm_by_sec: dict = defaultdict(float)
    if cajamar is not None and not cajamar.empty:
        fabono = fecha + dt.timedelta(days=1)
        for _, row in cajamar.iterrows():
            if row.get("fecha") == fabono and row.get("sec"):
                cajm_by_sec[row["sec"]] += row["importe"]

    for sec in cfg.IVERALSO_SECS:
        ag = erp.get(sec, {})
        b_efect = ag.get("B/EFECTIVO", 0.0)
        b_tarj = ag.get("B/TARJETA", 0.0)
        b_bizum = ag.get("B/BIZUM", 0.0)
        b_web = ag.get("B/WEB", 0.0)
        b_trans = ag.get("B/TRANSFEREN", 0.0)
        ot_efect = ag.get("OTROS/EFECTIVO", 0.0)
        ot_bizum = ag.get("OTROS/BIZUM", 0.0)
        tas_tarj = ag.get("TASA/TARJETA", 0.0)
        tas_bizum = ag.get("TASA/BIZUM", 0.0)
        tas_trans = ag.get("TASA/TRANSFEREN", 0.0)

        bbva_tot = bbva_by_sec.get(sec, 0.0)
        n_remesa = bbva_n.get(sec, 0)
        n_fucs = len(_fucs_por_sec(sec))

        df_pb = drive_pb.get(sec); df_ot = drive_otros.get(sec)
        d_pb = float(df_pb[df_pb["fecha"] == fecha]["ingreso"].sum()) if df_pb is not None and not df_pb.empty else 0.0
        d_ot = float(df_ot[df_ot["fecha"] == fecha]["cobro_efectivo"].sum()) if df_ot is not None and not df_ot.empty else 0.0

        # ── Permiso B Tarjeta+Bizum vs BBVA TPV ────────────────────────────
        suma_pb_bbva = b_tarj + b_bizum
        if n_remesa == 0 and suma_pb_bbva > TOL:
            msg = f"No se ha subido archivo TPV de {sec} ({cfg.SEC_TO_NOMBRE.get(sec, '')})"
            diff.append(Diferencia(fecha, sec, "Permiso B - Tarjeta (BBVA)",
                                   b_tarj, 0.0, b_tarj, msg, "miss"))
            if b_bizum > TOL:
                diff.append(Diferencia(fecha, sec, "Permiso B - Bizum (BBVA)",
                                       b_bizum, 0.0, b_bizum, msg, "miss"))
        else:
            cuadra = abs(suma_pb_bbva - bbva_tot) <= TOL
            hint = ""
            if n_fucs > 1 and n_remesa < n_fucs:
                hint = f" · {sec} tiene {n_fucs} FUCs; solo se han subido {n_remesa} remesa(s)"
            atrib_tarj = max(0.0, bbva_tot - b_bizum) if not cuadra else b_tarj
            atrib_bizum = max(0.0, bbva_tot - b_tarj) if not cuadra else b_bizum
            estado = "ok" if cuadra else "error"
            detalle = "" if cuadra else f"Tarjeta+Bizum ERP {suma_pb_bbva:,.2f} ≠ BBVA TPV {bbva_tot:,.2f}{hint}"
            diff.append(Diferencia(fecha, sec, "Permiso B - Tarjeta (BBVA)",
                                   b_tarj, atrib_tarj, b_tarj - atrib_tarj, detalle, estado))
            if b_bizum > TOL or bbva_tot > b_tarj + TOL:
                diff.append(Diferencia(fecha, sec, "Permiso B - Bizum (BBVA)",
                                       b_bizum, atrib_bizum, b_bizum - atrib_bizum, detalle, estado))

        # ── Efectivo (con regla intensivos) ────────────────────────────────
        tot_ef_erp = b_efect + ot_efect; tot_ef_drv = d_pb + d_ot
        compensado = abs(tot_ef_erp - tot_ef_drv) <= TOL and abs(b_efect - d_pb) > TOL
        if compensado:
            diff.append(Diferencia(fecha, sec, "Permiso B - Efectivo (Drive)",
                                   b_efect, d_pb, b_efect - d_pb,
                                   "Compensado: intensivos OP cobrados en caja B", "warn"))
            diff.append(Diferencia(fecha, sec, "Otros Permisos - Efectivo (Drive)",
                                   ot_efect, d_ot, ot_efect - d_ot,
                                   "Compensado: intensivos OP cobrados en caja B", "warn"))
        else:
            d = b_efect - d_pb
            diff.append(Diferencia(fecha, sec, "Permiso B - Efectivo (Drive)",
                                   b_efect, d_pb, d,
                                   "" if abs(d) <= TOL else f"Δ {d:+,.2f} €",
                                   "ok" if abs(d) <= TOL else "error"))
            d = ot_efect - d_ot
            diff.append(Diferencia(fecha, sec, "Otros Permisos - Efectivo (Drive)",
                                   ot_efect, d_ot, d,
                                   "" if abs(d) <= TOL else f"Δ {d:+,.2f} €",
                                   "ok" if abs(d) <= TOL else "error"))

        # ── Tasas Tarjeta vs Cajamar ───────────────────────────────────────
        cajm = cajm_by_sec.get(sec, 0.0)
        d = tas_tarj - cajm
        diff.append(Diferencia(fecha, sec, "Tasas - Tarjeta (Cajamar)",
                               tas_tarj, cajm, d,
                               "" if abs(d) <= TOL else f"Δ {d:+,.2f} €",
                               "ok" if abs(d) <= TOL else "error"))

        # ── Bizum OP y Tasas Bizum: contra Santander (transitorio: pendiente) ──
        if ot_bizum > TOL:
            diff.append(Diferencia(fecha, sec, "Otros Permisos - Bizum (Santander)",
                                   ot_bizum, 0.0, ot_bizum,
                                   "Pendiente de cruzar con extracto Bizum Santander", "pendiente"))
        if tas_bizum > TOL:
            diff.append(Diferencia(fecha, sec, "Tasas - Bizum (Santander)",
                                   tas_bizum, 0.0, tas_bizum,
                                   "Pendiente de cruzar con extracto Bizum Santander", "pendiente"))

        # ── Líneas prohibidas / informativas ───────────────────────────────
        if abs(b_trans) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Transferencia",
                                   0.0, b_trans, b_trans,
                                   "No debería haber transferencias en Permiso B", "error"))
        if abs(tas_trans) > TOL:
            diff.append(Diferencia(fecha, sec, "Tasas - Transferencia",
                                   0.0, tas_trans, tas_trans,
                                   "No debería haber transferencias en Tasas", "error"))
        if abs(b_web) > TOL:
            diff.append(Diferencia(fecha, sec, "Permiso B - Web Conjunta",
                                   b_web, 0.0, b_web,
                                   "Se verifica en email resumen (datáfono único)", "warn"))

    return diff


def diferencias_a_df(difs: Iterable[Diferencia]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Fecha": d.fecha, "Sección": d.seccion, "Concepto": d.concepto,
        "ERP": d.esperado, "Externo": d.encontrado, "Δ": d.delta,
        "Comentario": d.descripcion, "Severidad": d.severity,
    } for d in difs])
