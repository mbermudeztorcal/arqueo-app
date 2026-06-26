"""Arqueo App — v0.2 — Streamlit con resumen diario, retiradas y saldos."""
from __future__ import annotations
import datetime as dt
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from arqueo import config as cfg
from arqueo import db, resumen, retiradas
from arqueo.parsers import erp as erp_p
from arqueo.parsers import bbva as bbva_p
from arqueo.parsers import bbva_extracto as bbvaext_p
from arqueo.parsers import cajamar as caj_p
from arqueo.parsers import santander as sant_p
from arqueo.parsers import drive_pb as pb_p
from arqueo.parsers import drive_otros as ot_p
from arqueo.cuadre import cuadrar_dia, diferencias_a_df

st.set_page_config(page_title="Arqueo Iveralso", page_icon="📊", layout="wide")

DATA_DIR = db.get_data_dir()
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)


def upload_dir(empresa: str, fecha: dt.date, fuente: str) -> Path:
    p = UPLOADS / empresa.lower() / fecha.isoformat() / fuente
    p.mkdir(parents=True, exist_ok=True)
    return p


def listar(empresa: str, fecha: dt.date, fuente: str) -> list[Path]:
    return sorted(upload_dir(empresa, fecha, fuente).glob("*"))


def save_uploaded(empresa, fecha, fuente, uploaded_file) -> Path:
    target = upload_dir(empresa, fecha, fuente) / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return target


def cargar_fuentes(empresa: str, fechas: Iterable[dt.date]) -> dict:
    """Devuelve los DataFrames/listas de todas las fuentes para el rango de fechas."""
    df_erps = []
    bbva_remesas = []
    df_caj = pd.DataFrame()
    df_pb = {}
    df_ot = {}
    df_bbva_ext = pd.DataFrame()
    df_sant = pd.DataFrame()
    df_bizum = pd.DataFrame()

    for fecha in fechas:
        for f in listar(empresa, fecha, "erp"):
            try: df_erps.append(erp_p.parse(f))
            except Exception as e: st.warning(f"ERP {fecha} {f.name}: {e}")
        for f in listar(empresa, fecha, "bbva_remesas"):
            try:
                if f.suffix.lower() == ".xlsx":
                    bbva_remesas.append(bbva_p.parse_remesa_xlsx(f))
            except Exception as e: st.warning(f"BBVA remesa {f.name}: {e}")
        for f in listar(empresa, fecha, "bbva_extracto"):
            try:
                tmp = bbvaext_p.parse(f)
                df_bbva_ext = pd.concat([df_bbva_ext, tmp], ignore_index=True)
            except Exception as e: st.warning(f"Extracto BBVA {f.name}: {e}")
        for f in listar(empresa, fecha, "cajamar"):
            try:
                tmp = caj_p.parse(f)
                df_caj = pd.concat([df_caj, tmp], ignore_index=True)
            except Exception as e: st.warning(f"Cajamar {f.name}: {e}")
        for f in listar(empresa, fecha, "santander_ext"):
            try:
                tmp = sant_p.parse(f)
                df_sant = pd.concat([df_sant, tmp], ignore_index=True)
            except Exception as e: st.warning(f"Santander {f.name}: {e}")
        for f in listar(empresa, fecha, "santander_bizum"):
            try:
                tmp = bbva_p.parse_bizum_santander(f)
                df_bizum = pd.concat([df_bizum, tmp], ignore_index=True)
            except Exception as e: st.warning(f"Santander Bizum {f.name}: {e}")
        for f in listar(empresa, fecha, "drive_pb"):
            sec = pb_p.detect_seccion(f.name)
            if sec:
                try: df_pb[sec] = pb_p.parse(f)
                except Exception as e: st.warning(f"Drive PB {f.name}: {e}")
        for f in listar(empresa, fecha, "drive_otros"):
            sec = ot_p.detect_seccion(f.name)
            if sec:
                try: df_ot[sec] = ot_p.parse(f)
                except Exception as e: st.warning(f"Drive Otros {f.name}: {e}")

    df_erp = pd.concat(df_erps, ignore_index=True) if df_erps else pd.DataFrame()
    return {
        "erp": df_erp,
        "bbva_remesas": bbva_remesas,
        "cajamar": df_caj,
        "drive_pb": df_pb,
        "drive_otros": df_ot,
        "bbva_extracto": df_bbva_ext,
        "santander": df_sant,
        "bizum": df_bizum,
    }


# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("⚖️ Arqueo")
empresa = st.sidebar.selectbox("Empresa", cfg.EMPRESAS, index=0)
fecha = st.sidebar.date_input("Día del arqueo", dt.date(2026, 5, 25))
st.sidebar.caption(f"v0.2 · {len(cfg.FUENTES)} fuentes · {len(cfg.IVERALSO_SECS)} secciones")

st.title(f"📊 {empresa} • {fecha.strftime('%d/%m/%Y')}")

tab_upload, tab_arqueo, tab_resumen, tab_ret, tab_inc = st.tabs([
    "📤 Subir archivos", "⚖️ Arquear", "📅 Resumen diario", "💸 Retiradas", "📋 Incidencias",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: SUBIR ARCHIVOS
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("Subir archivos del día")
    estado = {}
    for key, label, hint in cfg.FUENTES:
        with st.container(border=True):
            existing = listar(empresa, fecha, key)
            estado[key] = existing
            badge = "✅" if existing else "⚠️"
            st.markdown(f"### {badge} {label}")
            st.caption(hint)
            multi = key in ("bbva_remesas", "drive_pb", "drive_otros")
            up = st.file_uploader(
                "Subir", accept_multiple_files=multi, key=f"up_{key}",
                label_visibility="collapsed"
            )
            if up:
                files = up if isinstance(up, list) else [up]
                for f in files: save_uploaded(empresa, fecha, key, f)
                st.rerun()
            if existing:
                cols = st.columns(min(3, len(existing)))
                for i, f in enumerate(existing):
                    c = cols[i % len(cols)]
                    if c.button(f"🗑 {f.name}", key=f"del_{key}_{f.name}"):
                        f.unlink(missing_ok=True)
                        st.rerun()

    # Detector huecos
    st.markdown("---")
    huecos = []
    if not estado.get("erp"): huecos.append("❌ Falta el listado del ERP")
    bbva_files = estado.get("bbva_remesas", [])
    if len(bbva_files) < 11:
        huecos.append(f"⚠️ Solo {len(bbva_files)} remesas BBVA (esperadas ≥11 + Web Conjunta)")
    secs_pb = {pb_p.detect_seccion(f.name) for f in estado.get("drive_pb", [])} - {None}
    falta_pb = set(cfg.IVERALSO_SECS) - secs_pb
    if falta_pb: huecos.append(f"⚠️ Faltan Drive PB de: {', '.join(sorted(falta_pb))}")
    secs_ot = {ot_p.detect_seccion(f.name) for f in estado.get("drive_otros", [])} - {None}
    falta_ot = set(cfg.IVERALSO_SECS) - secs_ot
    if falta_ot: huecos.append(f"⚠️ Faltan Drive Otros de: {', '.join(sorted(falta_ot))}")

    if huecos:
        for h in huecos: st.warning(h)
    else:
        st.success("Todos los archivos esperados están presentes.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: ARQUEAR (motor original, conserva igual)
# ════════════════════════════════════════════════════════════════════════════
with tab_arqueo:
    st.subheader("Cuadre del día")
    if st.button("⚖️ Arquear día seleccionado", type="primary"):
        with st.spinner("Cargando archivos..."):
            data = cargar_fuentes(empresa, [fecha])
        with st.spinner("Cuadrando..."):
            difs = cuadrar_dia(
                fecha=fecha,
                df_erp=data["erp"],
                bbva_remesas=data["bbva_remesas"],
                cajamar=data["cajamar"],
                drive_pb=data["drive_pb"],
                drive_otros=data["drive_otros"],
            )
        df_d = diferencias_a_df(difs)
        n_err = (df_d["Severidad"] == "error").sum()
        n_warn = (df_d["Severidad"] == "warn").sum()
        n_ok = (df_d["Severidad"] == "ok").sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ OK", n_ok); c2.metric("⚠️ Avisos", n_warn); c3.metric("❌ Errores", n_err)
        def color_sev(v):
            return {"error": "background-color:#ffd6d6", "warn": "background-color:#fff5cc",
                    "ok": "background-color:#e8f5e9"}.get(v, "")
        st.dataframe(
            df_d.style.format({"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"})
                 .applymap(color_sev, subset=["Severidad"]),
            use_container_width=True, height=600,
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: RESUMEN DIARIO (nuevo)
# ════════════════════════════════════════════════════════════════════════════
with tab_resumen:
    st.subheader("📅 Resumen diario · sección × permiso × FP")
    col_a, col_b = st.columns([2, 1])
    fecha_desde = col_a.date_input("Desde", fecha, key="rd_desde")
    fecha_hasta = col_b.date_input("Hasta", fecha, key="rd_hasta")
    if fecha_hasta < fecha_desde:
        st.error("La fecha Hasta es anterior a Desde.")
    else:
        if st.button("Calcular resumen"):
            fechas = [fecha_desde + dt.timedelta(days=i) for i in range((fecha_hasta - fecha_desde).days + 1)]
            with st.spinner("Cargando datos..."):
                data = cargar_fuentes(empresa, fechas)
            with st.spinner("Generando resumen..."):
                df_res = resumen.generar(
                    fechas=fechas,
                    df_erp=data["erp"],
                    bbva_remesas=data["bbva_remesas"],
                    cajamar_df=data["cajamar"],
                    drive_pb_map=data["drive_pb"],
                    drive_ot_map=data["drive_otros"],
                    santander_bizum_df=data.get("bizum"),
                )
                df_saldos = resumen.saldos_continuidad(fechas, data["drive_pb"], data["drive_otros"])

            for sec in cfg.IVERALSO_SECS:
                sub = df_res[df_res["seccion"] == sec]
                if sub.empty: continue
                st.markdown(f"### {sec} · {cfg.SEC_TO_NOMBRE[sec]}")
                # Pivotar: filas = (permiso, fp), columnas = fecha
                sub["fila"] = sub["permiso"] + " · " + sub["fp"]
                pivot = sub.pivot_table(
                    index="fila", columns="fecha", values="erp", aggfunc="sum", fill_value=0
                )
                # Colorizar según estado
                estado_map = sub.set_index(["fila","fecha"])["estado"].to_dict()
                def _style(v, row, col):
                    e = estado_map.get((row, col), "ok")
                    return {"error":"background-color:#ffd6d6","warn":"background-color:#fff5cc",
                            "ok":"background-color:#e8f5e9","pendiente":"background-color:#e0e0ff"}.get(e,"")
                styler = pivot.style.format("{:,.2f} €")
                # Aplicar color por celda
                for (fila, fch), est in estado_map.items():
                    if fila in pivot.index and fch in pivot.columns:
                        bg = {"error":"#ffd6d6","warn":"#fff5cc","ok":"#e8f5e9","pendiente":"#e0e0ff"}.get(est,"#fff")
                        styler = styler.set_properties(
                            subset=pd.IndexSlice[[fila],[fch]],
                            **{"background-color": bg}
                        )
                st.dataframe(styler, use_container_width=True)

                # Saldos
                ss = df_saldos[df_saldos["seccion"] == sec]
                if not ss.empty:
                    with st.expander(f"💰 Saldos cierre {sec}"):
                        sp = ss.pivot_table(index="tipo", columns="fecha", values="saldo_cierre", aggfunc="first")
                        st.dataframe(sp.style.format("{:,.2f} €"), use_container_width=True)
                        alertas = ss[ss["alerta"] != ""]
                        if not alertas.empty:
                            for _, a in alertas.iterrows():
                                st.error(f"{sec} {a['tipo']} {a['fecha']}: {a['alerta']}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 4: RETIRADAS
# ════════════════════════════════════════════════════════════════════════════
with tab_ret:
    st.subheader("💸 Retiradas y pagos del Drive Permiso B")
    c1, c2 = st.columns(2)
    f1 = c1.date_input("Desde", fecha, key="rt_desde")
    f2 = c2.date_input("Hasta", fecha, key="rt_hasta")
    if st.button("Buscar retiradas"):
        fechas = [f1 + dt.timedelta(days=i) for i in range((f2 - f1).days + 1)]
        with st.spinner("Cargando..."):
            data = cargar_fuentes(empresa, fechas)
        df_r = retiradas.extraer(data["drive_pb"], fechas)
        if df_r.empty:
            st.success("No hay retiradas registradas en ese rango.")
        else:
            st.caption(
                "Cada fila estará en rojo hasta que se detecte la entrada correspondiente "
                "en Caja Administración/Responsable (pendiente para v0.3) y un validador "
                "(Manuel/Dani) la apruebe."
            )
            st.dataframe(
                df_r.style.format({"importe": "{:,.2f} €"}),
                use_container_width=True, height=500,
            )

# ════════════════════════════════════════════════════════════════════════════
# TAB 5: INCIDENCIAS (igual que v0.1)
# ════════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.subheader("📋 Incidencias")
    with db.session() as s:
        from arqueo.models import Incidencia
        rows = s.query(Incidencia).order_by(Incidencia.fecha.desc(), Incidencia.id.desc()).limit(200).all()
    if not rows:
        st.info("Aún no hay incidencias registradas.")
    else:
        df_inc = pd.DataFrame([{
            "ID": r.id, "Fecha": r.fecha, "Sección": r.seccion, "Concepto": r.concepto,
            "ERP": r.esperado, "Externo": r.encontrado, "Δ": r.delta,
            "Estado": r.estado, "Descripción": r.descripcion,
        } for r in rows])
        st.dataframe(
            df_inc.style.format({"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"}),
            use_container_width=True, height=600,
        )
