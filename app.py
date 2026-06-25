"""Arqueo App — Spike Streamlit.

Ejecutar local:
    streamlit run app.py

Despliegue en Render: ver README.md.
"""
from __future__ import annotations
import datetime as dt
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from arqueo import config as cfg
from arqueo import db
from arqueo.parsers import erp as erp_p
from arqueo.parsers import bbva as bbva_p
from arqueo.parsers import cajamar as caj_p
from arqueo.parsers import drive_pb as pb_p
from arqueo.parsers import drive_otros as ot_p
from arqueo.cuadre import cuadrar_dia, diferencias_a_df

st.set_page_config(
    page_title="Arqueo Iveralso",
    page_icon="📊",
    layout="wide",
)

DATA_DIR = db.get_data_dir()
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)


def upload_dir(empresa: str, fecha: dt.date, fuente: str) -> Path:
    p = UPLOADS / empresa.lower() / fecha.isoformat() / fuente
    p.mkdir(parents=True, exist_ok=True)
    return p


def listar_archivos(empresa: str, fecha: dt.date, fuente: str) -> list[Path]:
    return sorted(upload_dir(empresa, fecha, fuente).glob("*"))


def save_uploaded(empresa: str, fecha: dt.date, fuente: str, uploaded_file) -> Path:
    target = upload_dir(empresa, fecha, fuente) / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return target


# ── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("⚖️ Arqueo")
empresa = st.sidebar.selectbox("Empresa", cfg.EMPRESAS, index=0)
fecha = st.sidebar.date_input("Día del arqueo", dt.date(2026, 5, 25))
st.sidebar.markdown("---")
st.sidebar.caption("Spike técnico • SQLite local")
st.sidebar.code(f"DATA_DIR\n{DATA_DIR}")

# ── Header ──────────────────────────────────────────────────────────────────
st.title(f"📊 {empresa} • {fecha.strftime('%d/%m/%Y')}")

tab_upload, tab_arqueo, tab_inc = st.tabs(
    ["📤 Subir archivos", "⚖️ Arquear", "📋 Incidencias"]
)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: SUBIR ARCHIVOS
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("Fuentes del día")
    st.caption(
        "Arrastra los archivos a cada apartado. Detectamos los que faltan."
    )

    cols = st.columns(3)
    fuentes_estado: dict[str, list[Path]] = {}
    for i, (key, label, hint) in enumerate(cfg.FUENTES):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(hint)
                existing = listar_archivos(empresa, fecha, key)
                fuentes_estado[key] = existing
                up = st.file_uploader(
                    "Subir",
                    accept_multiple_files=(key in ("bbva", "drive_pb", "drive_otros")),
                    key=f"up_{key}",
                    label_visibility="collapsed",
                )
                if up:
                    if isinstance(up, list):
                        for f in up:
                            save_uploaded(empresa, fecha, key, f)
                    else:
                        save_uploaded(empresa, fecha, key, up)
                    st.rerun()
                if existing:
                    for f in existing:
                        c1, c2 = st.columns([5, 1])
                        c1.text(f.name)
                        if c2.button("🗑", key=f"del_{key}_{f.name}"):
                            f.unlink(missing_ok=True)
                            st.rerun()
                else:
                    st.markdown("⚠️ _Sin archivos_")

    st.markdown("---")
    st.subheader("Revisión previa al arqueo")
    huecos = []
    if not fuentes_estado.get("erp"):
        huecos.append("Falta el listado del ERP")
    if not fuentes_estado.get("cajamar"):
        huecos.append("Falta el extracto Cajamar")
    bbva_files = fuentes_estado.get("bbva", [])
    pb_files = fuentes_estado.get("drive_pb", [])
    ot_files = fuentes_estado.get("drive_otros", [])
    if len(bbva_files) < 11:
        huecos.append(
            f"Sólo {len(bbva_files)} archivos BBVA (esperados ≥12: 11 secciones + Web Conjunta)"
        )
    secciones_pb = {pb_p.detect_seccion(f.name) for f in pb_files} - {None}
    sec_falta_pb = set(cfg.IVERALSO_SECS) - secciones_pb
    if sec_falta_pb:
        huecos.append(
            f"Faltan Drive Permiso B de: {', '.join(sorted(sec_falta_pb))}"
        )
    secciones_ot = {ot_p.detect_seccion(f.name) for f in ot_files} - {None}
    sec_falta_ot = set(cfg.IVERALSO_SECS) - secciones_ot
    if sec_falta_ot:
        huecos.append(
            f"Faltan Drive Otros Permisos de: {', '.join(sorted(sec_falta_ot))}"
        )

    if huecos:
        for h in huecos:
            st.warning(h, icon="⚠️")
        st.info(
            "Puedes pulsar **Arquear de todas formas** en la pestaña siguiente "
            "si confirmas que ese día no hubo movimiento.",
            icon="ℹ️",
        )
    else:
        st.success("Todos los archivos esperados están presentes.", icon="✅")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2: ARQUEAR
# ════════════════════════════════════════════════════════════════════════════
with tab_arqueo:
    st.subheader("Ejecutar arqueo")
    st.caption("Lee los archivos subidos del día y compara contra el ERP.")
    skip = st.checkbox("Arquear aunque falten archivos (asumir 0)")
    if st.button("⚖️ Arquear", type="primary"):
        df_erp = pd.DataFrame()
        if fuentes_estado.get("erp"):
            df_erp = erp_p.parse(fuentes_estado["erp"][0])
        elif not skip:
            st.error("No hay ERP. Sube uno o marca 'Arquear aunque falten archivos'.")
            st.stop()

        bbva_remesas = []
        for f in fuentes_estado.get("bbva", []):
            if f.suffix.lower() == ".xlsx":
                try:
                    bbva_remesas.append(bbva_p.parse_remesa_xlsx(f))
                except Exception as e:
                    st.warning(f"Error parseando {f.name}: {e}")

        df_caj = pd.DataFrame()
        if fuentes_estado.get("cajamar"):
            try:
                df_caj = caj_p.parse(fuentes_estado["cajamar"][0])
            except Exception as e:
                st.warning(f"Error Cajamar: {e}")

        drive_pb_map: dict[str, pd.DataFrame] = {}
        for f in fuentes_estado.get("drive_pb", []):
            sec = pb_p.detect_seccion(f.name)
            if sec:
                try:
                    drive_pb_map[sec] = pb_p.parse(f)
                except Exception as e:
                    st.warning(f"Error Drive PB {f.name}: {e}")

        drive_ot_map: dict[str, pd.DataFrame] = {}
        for f in fuentes_estado.get("drive_otros", []):
            sec = ot_p.detect_seccion(f.name)
            if sec:
                try:
                    drive_ot_map[sec] = ot_p.parse(f)
                except Exception as e:
                    st.warning(f"Error Drive Otros {f.name}: {e}")

        with st.spinner("Calculando cuadre..."):
            difs = cuadrar_dia(
                fecha=fecha,
                df_erp=df_erp,
                bbva_remesas=bbva_remesas,
                cajamar=df_caj,
                drive_pb=drive_pb_map,
                drive_otros=drive_ot_map,
            )

        df_difs = diferencias_a_df(difs)

        n_err = (df_difs["Severidad"] == "error").sum()
        n_warn = (df_difs["Severidad"] == "warn").sum()
        n_ok = (df_difs["Severidad"] == "ok").sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Cuadran", n_ok)
        c2.metric("⚠️ Avisos", n_warn)
        c3.metric("❌ Errores", n_err)

        if n_err == 0:
            st.success("Día cuadrado", icon="✅")
        else:
            st.error(f"{n_err} líneas con descuadre. Revisa abajo.", icon="❌")

        def color_sev(val):
            if val == "error":
                return "background-color: #ffd6d6"
            if val == "warn":
                return "background-color: #fff5cc"
            return "background-color: #e8f5e9"

        st.dataframe(
            df_difs.style.format(
                {"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"}
            ).applymap(color_sev, subset=["Severidad"]),
            use_container_width=True,
            height=600,
        )

        # Guardar en BD
        with db.session() as s:
            from arqueo.models import Arqueo, Incidencia, Empresa

            empresa_row = s.query(Empresa).filter_by(nombre=empresa).one()
            arq = Arqueo(
                empresa_id=empresa_row.id,
                fecha_desde=fecha,
                fecha_hasta=fecha,
                estado="ok" if n_err == 0 else "con_incidencias",
            )
            s.add(arq)
            s.flush()
            for d in difs:
                if d.severity == "error":
                    s.add(Incidencia(
                        arqueo_id=arq.id,
                        empresa_id=empresa_row.id,
                        fecha=d.fecha,
                        seccion=d.seccion,
                        concepto=d.concepto,
                        esperado=d.esperado,
                        encontrado=d.encontrado,
                        delta=d.delta,
                        descripcion=d.descripcion,
                        estado="abierta",
                    ))
            s.commit()
            st.caption(f"Guardado en BD: arqueo #{arq.id}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: INCIDENCIAS
# ════════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.subheader("Incidencias")
    with db.session() as s:
        from arqueo.models import Incidencia
        rows = s.query(Incidencia).order_by(Incidencia.fecha.desc(), Incidencia.id.desc()).limit(200).all()
    if not rows:
        st.info("Aún no hay incidencias registradas.", icon="ℹ️")
    else:
        df_inc = pd.DataFrame([{
            "ID": r.id,
            "Fecha": r.fecha,
            "Sección": r.seccion,
            "Concepto": r.concepto,
            "ERP": r.esperado,
            "Externo": r.encontrado,
            "Δ": r.delta,
            "Estado": r.estado,
            "Descripción": r.descripcion,
        } for r in rows])
        st.dataframe(
            df_inc.style.format({"ERP": "{:,.2f} €", "Externo": "{:,.2f} €", "Δ": "{:,.2f} €"}),
            use_container_width=True,
            height=600,
        )
