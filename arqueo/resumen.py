"""Resumen diario sección × permiso × FP, con saldos y estado agregado por día."""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable
import pandas as pd
from . import config as cfg

TOL = 0.01


def _agg_erp(df_erp: pd.DataFrame, fechas: Iterable[dt.date]) -> dict:
    if df_erp is None or df_erp.empty: return {}
    fechas = list(fechas)
    df = df_erp[df_erp["FECHA"].dt.date.isin(fechas) & df_erp["SEC"].isin(cfg.IVERALSO_SECS)]
    out: dict = defaultdict(float)
    for _, row in df.iterrows():
        sec = row["SEC"]; tp = row["TIPO_PERMISO"]; tc = row["TIPO_CONCEPTO"]
        fp_raw = (row["FP"] or "")
        u = fp_raw.upper()
        if "EFECTIVO" in u: fp = "Efectivo"
        elif "TARJETA" in u: fp = "Tarjeta"
        elif "BIZUM" in u: fp = "Bizum"
        elif "TRANSFEREN" in u: fp = "Transferencia"
        elif "WEB" in u or "PÁGINA" in u: fp = "Web"
        else: fp = fp_raw
        if tc == "Tasa": permiso = "Tasas"
        elif tp == "B": permiso = "Permiso B"
        else: permiso = "Otros Permisos"
        out[(row["FECHA"].date(), sec, permiso, fp)] += row["ING"] or 0.0
    return out


def _bbva_por_dia_sec(bbva_remesas: list[dict]) -> dict:
    out: dict = defaultdict(float)
    counter: dict = defaultdict(int)
    for r in bbva_remesas:
        sec = r.get("sec"); movs = r.get("movimientos") or []
        if movs:
            for m in movs:
                if m.get("sec") and m.get("fecha") is not None:
                    out[(m["fecha"], m["sec"])] += m.get("importe", 0)
                    counter[(m["fecha"], m["sec"])] += 1
        else:
            fr = r.get("fecha_remesa")
            if fr and r.get("importe") and sec:
                f = fr - dt.timedelta(days=1)
                out[(f, sec)] += r["importe"]
                counter[(f, sec)] += 1
    return out, counter


def generar(
    fechas: list[dt.date], df_erp: pd.DataFrame, bbva_remesas: list[dict],
    cajamar_df: pd.DataFrame, drive_pb_map: dict[str, pd.DataFrame],
    drive_ot_map: dict[str, pd.DataFrame], santander_bizum_df=None,
) -> pd.DataFrame:
    erp = _agg_erp(df_erp, fechas)
    bbva_by, bbva_n = _bbva_por_dia_sec(bbva_remesas)

    caj_by: dict = defaultdict(float)
    if cajamar_df is not None and not cajamar_df.empty:
        for _, row in cajamar_df.iterrows():
            sec = row.get("sec"); fa = row.get("fecha")
            if sec and pd.notna(fa):
                caj_by[(fa - dt.timedelta(days=1), sec)] += row["importe"]

    pb_by: dict = defaultdict(float)
    for sec, df in (drive_pb_map or {}).items():
        if df is None or df.empty: continue
        for _, r in df.iterrows():
            pb_by[(r["fecha"], sec)] += r.get("ingreso", 0)

    ot_by: dict = defaultdict(float)
    for sec, df in (drive_ot_map or {}).items():
        if df is None or df.empty: continue
        for _, r in df.iterrows():
            ot_by[(r["fecha"], sec)] += r.get("cobro_efectivo", 0)

    rows = []
    for fecha in fechas:
        for sec in cfg.IVERALSO_SECS:
            erp_pb_tarj = erp.get((fecha, sec, "Permiso B", "Tarjeta"), 0.0)
            erp_pb_biz = erp.get((fecha, sec, "Permiso B", "Bizum"), 0.0)
            bbva_tot = bbva_by.get((fecha, sec), 0.0)
            n_remesa = bbva_n.get((fecha, sec), 0)
            n_fucs = sum(1 for s in cfg.FUC_TO_SEC.values() if s == sec)

            for permiso, fp in cfg.LINEAS_RESUMEN:
                erp_val = erp.get((fecha, sec, permiso, fp), 0.0)
                ext_val = 0.0; estado = "ok"; detalle = ""

                if permiso == "Permiso B" and fp == "Tarjeta":
                    suma = erp_pb_tarj + erp_pb_biz
                    if n_remesa == 0 and suma > TOL:
                        ext_val = 0; estado = "miss"
                        detalle = f"No se ha subido archivo TPV de {sec}"
                    else:
                        cuadra = abs(suma - bbva_tot) <= TOL
                        ext_val = max(0, bbva_tot - erp_pb_biz)
                        estado = "ok" if cuadra else "error"
                        if not cuadra:
                            detalle = f"Tarjeta+Bizum {suma:,.2f} ≠ BBVA {bbva_tot:,.2f}"
                            if n_fucs > 1 and n_remesa < n_fucs:
                                detalle += f" · {sec} tiene {n_fucs} FUC, recibidas {n_remesa}"
                elif permiso == "Permiso B" and fp == "Bizum":
                    suma = erp_pb_tarj + erp_pb_biz
                    if n_remesa == 0 and suma > TOL:
                        ext_val = 0; estado = "miss"
                        detalle = f"No se ha subido archivo TPV de {sec}"
                    else:
                        cuadra = abs(suma - bbva_tot) <= TOL
                        ext_val = max(0, bbva_tot - erp_pb_tarj)
                        estado = "ok" if cuadra else "error"
                        if not cuadra:
                            detalle = f"Tarjeta+Bizum {suma:,.2f} ≠ BBVA {bbva_tot:,.2f}"
                elif permiso == "Permiso B" and fp == "Efectivo":
                    ext_val = pb_by.get((fecha, sec), 0.0)
                    erp_ot = erp.get((fecha, sec, "Otros Permisos", "Efectivo"), 0.0)
                    drv_ot = ot_by.get((fecha, sec), 0.0)
                    delta = erp_val - ext_val
                    if abs((erp_val + erp_ot) - (ext_val + drv_ot)) <= TOL and abs(delta) > TOL:
                        estado = "warn"
                        detalle = f"Compensado: intensivos {ext_val-erp_val:+.2f}€"
                    else:
                        estado = "ok" if abs(delta) <= TOL else "error"
                        if estado == "error": detalle = f"Δ {delta:+,.2f} €"
                elif permiso == "Otros Permisos" and fp == "Efectivo":
                    ext_val = ot_by.get((fecha, sec), 0.0)
                    erp_b = erp.get((fecha, sec, "Permiso B", "Efectivo"), 0.0)
                    drv_b = pb_by.get((fecha, sec), 0.0)
                    delta = erp_val - ext_val
                    if abs((erp_b + erp_val) - (drv_b + ext_val)) <= TOL and abs(delta) > TOL:
                        estado = "warn"
                        detalle = f"Compensado: intensivos {ext_val-erp_val:+.2f}€"
                    else:
                        estado = "ok" if abs(delta) <= TOL else "error"
                        if estado == "error": detalle = f"Δ {delta:+,.2f} €"
                elif permiso == "Tasas" and fp == "Tarjeta":
                    ext_val = caj_by.get((fecha, sec), 0.0)
                    delta = erp_val - ext_val
                    estado = "ok" if abs(delta) <= TOL else "error"
                    if estado == "error": detalle = f"Δ {delta:+,.2f} €"
                elif fp == "Bizum":  # OP Bizum o Tasas Bizum
                    estado = "pendiente" if erp_val > TOL else "ok"
                    if estado == "pendiente":
                        detalle = "Pendiente cruzar con Bizum Santander"
                else:
                    estado = "ok" if abs(erp_val) <= TOL else "warn"

                delta = erp_val - ext_val
                rows.append({"fecha": fecha, "seccion": sec, "permiso": permiso,
                             "fp": fp, "erp": erp_val, "externo": ext_val,
                             "delta": delta, "estado": estado, "detalle": detalle})
    return pd.DataFrame(rows)


def estado_por_dia_permiso(df_resumen: pd.DataFrame) -> pd.DataFrame:
    """Devuelve, por (fecha, sección, permiso), el estado agregado: ok/warn/error/pendiente/miss.
    Regla: si hay algún error o miss → error; si hay warn/pendiente → warn; si todo ok → ok."""
    if df_resumen is None or df_resumen.empty: return pd.DataFrame()
    rows = []
    grp = df_resumen.groupby(["fecha", "seccion", "permiso"])
    for (f, sec, perm), sub in grp:
        estados = set(sub["estado"])
        if "error" in estados or "miss" in estados: ag = "error"
        elif "warn" in estados or "pendiente" in estados: ag = "warn"
        else: ag = "ok"
        rows.append({"fecha": f, "seccion": sec, "permiso": perm, "estado": ag,
                     "total_erp": float(sub["erp"].sum())})
    return pd.DataFrame(rows)


def saldos_continuidad(fechas, drive_pb_map, drive_ot_map):
    from .parsers.drive_pb import saldos_por_dia as sp_pb
    from .parsers.drive_otros import saldos_por_dia as sp_ot
    out = []
    for sec in cfg.IVERALSO_SECS:
        for tipo, m, fn in (("PB", drive_pb_map or {}, sp_pb), ("OT", drive_ot_map or {}, sp_ot)):
            df = m.get(sec)
            if df is None or df.empty: continue
            saldos = fn(df).sort_values("fecha")
            saldos_map = dict(zip(saldos["fecha"], saldos["saldo_cierre"]))
            for f in fechas:
                cierre = saldos_map.get(f)
                inicio = saldos_map.get(f - dt.timedelta(days=1))
                alerta = ""
                if inicio is not None and cierre is not None:
                    movs = 0.0
                    if "ingreso" in df.columns:
                        movs = float(df[df["fecha"]==f]["ingreso"].sum()) - float(df[df["fecha"]==f]["pago"].sum())
                    elif "cobro_efectivo" in df.columns:
                        movs = float(df[df["fecha"]==f]["cobro_efectivo"].sum())
                    if abs(inicio + movs - cierre) > TOL:
                        alerta = f"Apertura {inicio:.2f}€ + mov {movs:+.2f}€ ≠ cierre {cierre:.2f}€"
                out.append({"seccion": sec, "tipo": tipo, "fecha": f,
                            "saldo_inicio": inicio, "saldo_cierre": cierre, "alerta": alerta})
    return pd.DataFrame(out)
