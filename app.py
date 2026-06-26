"""Arqueo App — v0.3 — UI mejorada, drive unificado, drive admin."""
from __future__ import annotations
import datetime as dt
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from arqueo import config as cfg
from arqueo import db, resumen, retiradas, ui
from arqueo.parsers import erp as erp_p
from arqueo.parsers import bbva as bbva_p
from arqueo.parsers import bbva_extracto as bbvaext_p
from arqueo.parsers import cajamar as caj_p
from arqueo.parsers import santander as sant_p
from arqueo.parsers import drive_caja as caja_p
from arqueo.parsers import drive_pb as pb_p
from arqueo.parsers import drive_otros as ot_p
from arqueo.parsers import drive_admin as adm_p
from arqueo.cuadre import cuadrar_dia, diferencias_a_df

st.set_page_config(
    page_title="Arqueo · Iveralso",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    df_erps = []
    bbva_remesas = []
    df_caj = pd.DataFrame()
    df_pb = {}
    df_ot = {}
    df_bbva_ext = pd.DataFrame()
    df_sant = pd.DataFrame()
    df_bizum = pd.DataFrame()
    df_admin = pd.DataFrame()

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
        # Drive Caja: un archivo, dos hojas (PB + Otros)
        for f in listar(empresa, fecha, "drive_caja"):
            sec = caja_p.detect_seccion(f.name)
            if not sec: continue
            try:
                parsed = caja_p.parse(f)
                if not parsed["pb"].empty: df_pb[sec] = parsed["pb"]
                if not parsed["otros"].empty: df_ot[sec] = parsed["otros"]
            except Exception as e: st.warning(f"Drive Caja {sec} {f.name}: {e}")
        for f in listar(empresa, fecha, "drive_admin"):
            try:
                tmp = adm_p.parse(f)
                df_admin = pd.concat([df_admin, tmp], ignore_index=True)
            except Exception as e: st.warning(f"Drive Admin {f.name}: {e}")

    df_erp = pd.concat(df_erps, ignore_index=True) if df_erps else pd.DataFrame()
    return {
        "erp": df_erp, "bbva_remesas": bbva_remesas, "cajamar": df_caj,
        "drive_pb": df_pb, "drive_otros": df_ot,
        "bbva_extracto": df_bbva_ext, "santander": df_sant, "bizum": df_bizum,
        "admin": df_admin,
    }


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Workspace")
    empresa = st.selectbox("Empresa", cfg.EMPRESAS, index=0)
    st.markdown("---")
    st.markdown("### Día de trabajo")
    fecha = st.date_input("Fecha", dt.date(2026, 5, 25))
    st.markdown("---")
    with st.expander("Mapeos cargados"):
        st.caption(f"**Secciones:** {len(cfg.IVERALSO_SECS)}")
        st.caption(f"**FUC BBVA:** {len(cfg.FUC_TO_SEC)} (incluye Web Conjunta)")
        st.caption(f"**Códigos Cajamar:** {len(cfg.CAJ_TO_SEC)}")
        st.caption(f"**Terminales Norma43:** {len(cfg.TERMINAL_TO_SEC)}")
    st.caption("v0.3 spike · Render Free")

# ── Cabecera ────────────────────────────────────────────────────────────────
ui.render_header(empresa, "Arqueo automático multi-fuente")

tab_upload, tab_arqueo, tab_resumen, tab_ret, tab_inc = st.tabs([
    "📤 Subir archivos", "⚖️ Arquear", "📅 Resumen diario", "💸 Retiradas", "📋 Incidencias",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB: SUBIR ARCHIVOS
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown(f"#### Fuentes del día **{fecha.strftime('%d/%m/%Y')}**")
    st.caption("Sube los archivos del día. Detectamos automáticamente qué falta antes de arquear.")
    estado = {}
    rows = [cfg.FUENTES[i:i+2] for i in range(0, len(cfg.FUENTES), 2)]
    for fila in rows:
        cols = st.columns(2)
        for col, (key, label, hint, icon, multi) in zip(cols, fila):
            with col:
                with st.container(border=True):
                    existing = listar(empresa, fecha, key)
                    estado[key] = existing
                    n = len(existing)
                    badge = ui.status_badge("ok" if n > 0 else "miss")
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<div style="font-weight:600;font-size:16px;">{icon} {label}</div>'
                        f'{badge}</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(hint)
                    up = st.file_uploader(
                        "Subir", accept_multiple_files=multi,
                        key=f"up_{key}", label_visibility="collapsed",
                    )
                    if up:
                        files = up if isinstance(up, list) else [up]
                        for f in files: save_uploaded(empresa, fecha, key, f)
                        st.rerun()
                    if existing:
                        for f in existing:
                            c1, c2 = st.columns([5, 1])
                            c1.text(f"📄 {f.name}")
                            if c2.button("🗑", key=f"del_{key}_{f.name}"):
                                f.unlink(missing_ok=True)
                                st.rerun()

    # Resumen previo
    ui.section_title("Previo al arqueo")
    huecos = []
    if not estado.get("erp"): huecos.append(("error", "Falta el listado del ERP"))
    bbva_files = estado.get("bbva_remesas", [])
    if len(bbva_files) < 11:
        huecos.append(("warn", f"Solo {len(bbva_files)} remesas BBVA (esperadas ≥12 con Web Conjunta)"))
    secs_caja = {caja_p.detect_seccion(f.name) for f in estado.get("drive_caja", [])} - {None}
    falta_caja = set(cfg.IVERALSO_SECS) - secs_caja
    if falta_caja:
        huecos.append(("warn", f"Faltan Drive Caja de: {', '.join(sorted(falta_caja))}"))

    if huecos:
        for sev, msg in huecos:
            if sev == "error": st.error(msg)
            else: st.warning(msg)
    else:
        st.success("Todos los archivos esperados están presentes. Puedes pasar a Arquear.")

# ════════════════════════════════════════════════════════════════════════════
# TAB: ARQUEAR
# ════════════════════════════════════════════════════════════════════════════
with tab_arqueo:
    st.markdown(f"#### Cuadre del **{fecha.strftime('%d/%m/%Y')}**")
    if st.button("⚖️ Arquear día", type="primary", use_container_width=False):
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
        c1.metric("Cuadradas", n_ok)
        c2.metric("Avisos", n_warn)
        c3.metric("Errores", n_err)
        ui.section_title("Detalle por línea")
        def color_sev(v):
            return {"error": "background-color:#ffd6d6", "warn": "background-color:#fff5cc",
                    "ok": "background-color:#dcf5e3"}.get(v, "")
        st.dataframe(
            df_d.style.format({"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"})
                 .applymap(color_sev, subset=["Severidad"]),
            use_container_width=True, height=500,
        )

# ════════════════════════════════════════════════════════════════════════════
# TAB: RESUMEN DIARIO
# ════════════════════════════════════════════════════════════════════════════
with tab_resumen:
    st.markdown("#### Resumen diario · sección × permiso × forma de pago")
    col_a, col_b, col_btn = st.columns([2, 2, 1])
    fecha_desde = col_a.date_input("Desde", fecha, key="rd_desde")
    fecha_hasta = col_b.date_input("Hasta", fecha, key="rd_hasta")
    go = col_btn.button("Calcular", type="primary")
    if fecha_hasta < fecha_desde:
        st.error("La fecha Hasta es anterior a Desde.")
    elif go:
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

        n_ok = (df_res["estado"] == "ok").sum()
        n_w = (df_res["estado"] == "warn").sum()
        n_e = (df_res["estado"] == "error").sum()
        n_p = (df_res["estado"] == "pendiente").sum()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cuadradas", n_ok); m2.metric("Avisos", n_w)
        m3.metric("Errores", n_e); m4.metric("Pendientes", n_p)

        ui.section_title("Por sección")
        for sec in cfg.IVERALSO_SECS:
            sub = df_res[df_res["seccion"] == sec]
            if sub.empty: continue
            with st.expander(f"**{sec}** · {cfg.SEC_TO_NOMBRE[sec]}", expanded=(len(fechas) <= 3)):
                sub2 = sub.copy()
                sub2["fila"] = sub2["permiso"] + " · " + sub2["fp"]
                pivot = sub2.pivot_table(index="fila", columns="fecha", values="erp",
                                          aggfunc="sum", fill_value=0)
                estado_map = sub2.set_index(["fila","fecha"])["estado"].to_dict()
                styler = pivot.style.format("{:,.2f} €")
                for (fila, fch), est in estado_map.items():
                    if fila in pivot.index and fch in pivot.columns:
                        bg = {"error":"#ffd6d6","warn":"#fff5cc","ok":"#dcf5e3","pendiente":"#dde3ff"}.get(est,"#fff")
                        styler = styler.set_properties(
                            subset=pd.IndexSlice[[fila],[fch]],
                            **{"background-color": bg, "color":"#1a1a1a"}
                        )
                st.dataframe(styler, use_container_width=True)

                ss = df_saldos[df_saldos["seccion"] == sec]
                if not ss.empty:
                    st.markdown("**💰 Saldos**")
                    sp = ss.pivot_table(index="tipo", columns="fecha", values="saldo_cierre", aggfunc="first")
                    st.dataframe(sp.style.format("{:,.2f} €"), use_container_width=True)
                    alertas = ss[ss["alerta"] != ""]
                    if not alertas.empty:
                        for _, a in alertas.iterrows():
                            st.error(f"{sec} {a['tipo']} {a['fecha']}: {a['alerta']}")

# ════════════════════════════════════════════════════════════════════════════
# TAB: RETIRADAS
# ════════════════════════════════════════════════════════════════════════════
with tab_ret:
    st.markdown("#### Retiradas y pagos del Drive Permiso B")
    c1, c2, cb = st.columns([2, 2, 1])
    f1 = c1.date_input("Desde", fecha, key="rt_desde")
    f2 = c2.date_input("Hasta", fecha, key="rt_hasta")
    go = cb.button("Buscar", type="primary", key="rt_go")
    if go:
        fechas = [f1 + dt.timedelta(days=i) for i in range((f2 - f1).days + 1)]
        with st.spinner("Cargando..."):
            data = cargar_fuentes(empresa, fechas)
        df_r = retiradas.extraer(data["drive_pb"], fechas)
        df_admin = data.get("admin", pd.DataFrame())

        c1, c2, c3 = st.columns(3)
        c1.metric("Retiradas detectadas", len(df_r))
        c2.metric("Total retirado", f"{df_r['importe'].sum():,.2f} €" if not df_r.empty else "0,00 €")
        c3.metric("Ingresos en Admin", f"{df_admin['importe'].sum():,.2f} €" if not df_admin.empty else "—")

        ui.section_title("Detalle de retiradas")
        if df_r.empty:
            st.info("No hay retiradas registradas en ese rango.")
        else:
            st.caption(
                "Cada retirada queda **pendiente_validar** hasta que: "
                "(a) se detecte el ingreso correspondiente en el Drive de Caja Administración "
                "y (b) un validador (Manuel/Dani) la apruebe."
            )
            st.dataframe(
                df_r.style.format({"importe": "{:,.2f} €"}),
                use_container_width=True, height=400,
            )

        if not df_admin.empty:
            ui.section_title("Movimientos en Caja Administración")
            st.dataframe(
                df_admin.style.format({"importe": "{:,.2f} €"}),
                use_container_width=True, height=300,
            )

# ════════════════════════════════════════════════════════════════════════════
# TAB: INCIDENCIAS
# ════════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.markdown("#### Incidencias")
    with db.session() as s:
        from arqueo.models import Incidencia
        rows = s.query(Incidencia).order_by(Incidencia.fecha.desc(), Incidencia.id.desc()).limit(200).all()
    if not rows:
        st.info("Aún no hay incidencias registradas. Al ejecutar un arqueo con errores, se guardarán aquí.")
    else:
        df_inc = pd.DataFrame([{
            "ID": r.id, "Fecha": r.fecha, "Sección": r.seccion, "Concepto": r.concepto,
            "ERP": r.esperado, "Externo": r.encontrado, "Δ": r.delta,
            "Estado": r.estado, "Descripción": r.descripcion,
        } for r in rows])
        c1, c2, c3 = st.columns(3)
        c1.metric("Abiertas", (df_inc["Estado"] == "abierta").sum())
        c2.metric("Pdte validación", (df_inc["Estado"] == "pendiente_validar").sum())
        c3.metric("Resueltas", (df_inc["Estado"] == "resuelta").sum())
        st.dataframe(
            df_inc.style.format({"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"}),
            use_container_width=True, height=500,
        )
