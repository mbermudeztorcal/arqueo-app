"""Arqueo App — v0.5 — cache de parsers, arquear todos los días detectados, progreso."""
from __future__ import annotations
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from arqueo import config as cfg
from arqueo import db, resumen, retiradas, ui, incidencias, loader
from arqueo.parsers import drive_caja as caja_p
from arqueo.cuadre import cuadrar_dia, diferencias_a_df

st.set_page_config(page_title="Arqueo · Iveralso", page_icon="⚖️",
                   layout="wide", initial_sidebar_state="expanded")

DATA_DIR = db.get_data_dir()
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)


def upload_dir(empresa, fecha, fuente):
    p = UPLOADS / empresa.lower() / fecha.isoformat() / fuente
    p.mkdir(parents=True, exist_ok=True); return p


def listar(empresa, fecha, fuente):
    return sorted(upload_dir(empresa, fecha, fuente).glob("*"))


def save_uploaded(empresa, fecha, fuente, uploaded_file):
    target = upload_dir(empresa, fecha, fuente) / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return target


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Workspace")
    empresa = st.selectbox("Empresa", cfg.EMPRESAS, index=0)
    st.markdown("---")
    st.markdown("### Día a subir / inspeccionar")
    fecha = st.date_input("Fecha", dt.date(2026, 5, 25))
    st.caption("Esta fecha controla en qué carpeta se guardan los archivos que subes "
               "y qué día se muestra en Resumen y Retiradas. Al **Arquear**, "
               "se procesan automáticamente todos los días con datos.")
    st.markdown("---")
    fechas_disco = loader.fechas_con_datos(UPLOADS, empresa)
    with st.expander(f"📅 Días con datos: {len(fechas_disco)}"):
        if fechas_disco:
            for f in fechas_disco[-12:]:
                st.caption(f"• {f.strftime('%d/%m/%Y')}")
        else:
            st.caption("Aún no se ha subido ningún archivo.")
    with st.expander("Mapeos cargados"):
        st.caption(f"**Secciones:** {len(cfg.IVERALSO_SECS)}")
        st.caption(f"**FUC BBVA:** {len(cfg.FUC_TO_SEC)}")
        st.caption(f"**Códigos Cajamar:** {len(cfg.CAJ_TO_SEC)}")
    if st.button("♻️ Limpiar caché de parsers"):
        st.cache_data.clear()
        st.toast("Caché de parsers vaciada")
    st.caption("v0.5 spike · Render Free")

ui.render_header(empresa, "Arqueo automático multi-fuente")

tab_upload, tab_arqueo, tab_resumen, tab_ret, tab_inc = st.tabs([
    "📤 Subir archivos", "⚖️ Arquear", "📅 Resumen diario", "💸 Retiradas", "📋 Incidencias",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB: SUBIR
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown(f"#### Fuentes del día **{fecha.strftime('%d/%m/%Y')}**")
    st.caption("Arrastra varios archivos o selecciónalos a la vez. "
               "Los archivos se guardan en la carpeta del día seleccionado en la barra lateral.")
    estado = {}
    rows = [cfg.FUENTES[i:i+2] for i in range(0, len(cfg.FUENTES), 2)]
    for fila in rows:
        cols = st.columns(2)
        for col, (key, label, hint, icon, _orig_multi) in zip(cols, fila):
            with col:
                with st.container(border=True):
                    existing = listar(empresa, fecha, key)
                    estado[key] = existing
                    badge = ui.status_badge("ok" if existing else "miss")
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<div style="font-weight:600;font-size:16px;">{icon} {label}</div>'
                        f'{badge}</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(hint)
                    counter_key = f"upcnt_{key}_{fecha.isoformat()}"
                    counter = st.session_state.get(counter_key, 0)
                    upload_key = f"up_{key}_{fecha.isoformat()}_{counter}"
                    up = st.file_uploader(
                        "Arrastra o selecciona archivos", accept_multiple_files=True,
                        key=upload_key, label_visibility="collapsed",
                    )
                    if up:
                        for f in up: save_uploaded(empresa, fecha, key, f)
                        st.session_state[counter_key] = counter + 1
                        st.rerun()
                    if existing:
                        with st.expander(f"📂 Ver {len(existing)} archivo(s)"):
                            for f in existing:
                                c1, c2 = st.columns([5, 1])
                                c1.text(f"📄 {f.name}")
                                if c2.button("🗑", key=f"del_{key}_{fecha.isoformat()}_{f.name}"):
                                    f.unlink(missing_ok=True); st.rerun()

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
            (st.error if sev == "error" else st.warning)(msg)
    else:
        st.success("Todos los archivos esperados están presentes en este día.")

# ════════════════════════════════════════════════════════════════════════════
# TAB: ARQUEAR
# ════════════════════════════════════════════════════════════════════════════
with tab_arqueo:
    st.markdown("#### Arqueo")
    fechas_disco = loader.fechas_con_datos(UPLOADS, empresa)
    if not fechas_disco:
        st.info("Aún no hay archivos subidos. Empieza en **📤 Subir archivos**.")
    else:
        c1, c2 = st.columns([1, 4])
        do = c1.button("⚖️ Arquear", type="primary")
        c2.caption(
            f"Se procesarán automáticamente **{len(fechas_disco)} día(s)** con datos subidos: "
            f"{', '.join(f.strftime('%d/%m') for f in fechas_disco[-8:])}"
            + (" (+ anteriores)" if len(fechas_disco) > 8 else "")
        )

        if do:
            bar = st.progress(0.0, text="Iniciando…")
            t0 = time.time()
            estado_msg = st.empty()

            def step_loader(p, txt):
                # p es 0..1 de los archivos cargados (70% del trabajo total estimado)
                total_p = 0.70 * p
                elapsed = time.time() - t0
                eta = (elapsed / total_p - elapsed) if total_p > 0.02 else 0
                bar.progress(min(0.70, total_p),
                             text=f"📂 Cargando · {txt}  ({int(total_p*100)}%, ~{int(eta)}s restantes)")

            data = loader.cargar(UPLOADS, empresa, fechas_disco, progress=step_loader)

            all_difs = []
            n_dias = len(fechas_disco)
            for i, f in enumerate(fechas_disco, start=1):
                p = 0.70 + 0.30 * (i / n_dias)
                elapsed = time.time() - t0
                eta = (elapsed / p - elapsed) if p > 0.02 else 0
                bar.progress(p, text=f"⚖️ Cuadrando {f.strftime('%d/%m/%Y')} "
                                      f"({int(p*100)}%, ~{int(eta)}s restantes)")
                difs = cuadrar_dia(fecha=f, df_erp=data["erp"],
                                   bbva_remesas=data["bbva_remesas"], cajamar=data["cajamar"],
                                   drive_pb=data["drive_pb"], drive_otros=data["drive_otros"],
                                   santander_bizum=data.get("bizum"))
                arq_id = incidencias.registrar_arqueo(empresa, f, difs)
                all_difs.append((f, arq_id, difs))

            bar.progress(1.0, text=f"✅ Listo en {int(time.time()-t0)}s")
            time.sleep(0.4); bar.empty()

            df_d = diferencias_a_df([d for _, _, lst in all_difs for d in lst])
            n_err = (df_d["Severidad"].isin(["error","miss"])).sum()
            n_warn = (df_d["Severidad"] == "warn").sum()
            n_pend = (df_d["Severidad"] == "pendiente").sum()
            n_ok = (df_d["Severidad"] == "ok").sum()
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Días procesados", n_dias)
            m2.metric("Cuadradas", n_ok)
            m3.metric("Errores", n_err)
            m4.metric("Avisos", n_warn)
            m5.metric("Pendientes", n_pend)

            # Estado por día
            ui.section_title("Estado por día")
            por_dia = []
            for f, arq_id, difs in all_difs:
                sev = {d.severity for d in difs}
                if "error" in sev or "miss" in sev: e = "❌ Con incidencias"
                elif "warn" in sev or "pendiente" in sev: e = "⚠️ Con avisos"
                else: e = "✅ OK"
                por_dia.append({"Fecha": f, "Arqueo": arq_id, "Estado": e,
                                "Líneas con incidencia": sum(1 for d in difs if d.severity in ("error","miss","warn","pendiente"))})
            st.dataframe(pd.DataFrame(por_dia), use_container_width=True, hide_index=True)

            # Falta TPV → uploaders inline
            miss_rows = df_d[df_d["Severidad"] == "miss"]
            if not miss_rows.empty:
                ui.section_title("Acciones rápidas · Falta TPV")
                key_miss = miss_rows[["Fecha", "Sección"]].drop_duplicates().values.tolist()
                for fecha_m, sec in key_miss:
                    with st.container(border=True):
                        fucs = [f for f, s in cfg.FUC_TO_SEC.items() if s == sec]
                        st.markdown(f"**{sec} · {cfg.SEC_TO_NOMBRE.get(sec,'')}** "
                                    f"— día {fecha_m.strftime('%d/%m/%Y')}")
                        st.caption(f"FUC esperado(s): {', '.join(fucs)}")
                        up_inline = st.file_uploader(
                            "Sube aquí el TPV", accept_multiple_files=True,
                            key=f"miss_up_{sec}_{fecha_m.isoformat()}",
                            label_visibility="collapsed",
                        )
                        if up_inline:
                            for f in up_inline:
                                save_uploaded(empresa, fecha_m, "bbva_remesas", f)
                            st.rerun()

            ui.section_title("Detalle por línea")
            def color_sev(v):
                return {"error":"background-color:#ffd6d6","miss":"background-color:#ffd6d6",
                        "warn":"background-color:#fff5cc","ok":"background-color:#dcf5e3",
                        "pendiente":"background-color:#dde3ff"}.get(v, "")
            st.dataframe(
                df_d.style.format({"ERP":"{:,.2f} €","Externo":"{:,.2f} €","Δ":"{:,.2f} €"})
                     .applymap(color_sev, subset=["Severidad"]),
                use_container_width=True, height=520,
            )

# ════════════════════════════════════════════════════════════════════════════
# TAB: RESUMEN
# ════════════════════════════════════════════════════════════════════════════
with tab_resumen:
    st.markdown(f"#### Resumen del **{fecha.strftime('%d/%m/%Y')}**")
    st.caption("Vista agregada del día seleccionado en la barra lateral. "
               "Verde = todo conciliado · Rojo = hay incidencia abierta.")

    bar = st.progress(0.0, text="Cargando…")
    t0 = time.time()
    data = loader.cargar(UPLOADS, empresa, [fecha],
                         progress=lambda p, t: bar.progress(min(1.0, p),
                            text=f"📂 {t}  ({int(p*100)}%)"))
    bar.empty()

    df_res = resumen.generar(fechas=[fecha], df_erp=data["erp"],
                              bbva_remesas=data["bbva_remesas"], cajamar_df=data["cajamar"],
                              drive_pb_map=data["drive_pb"], drive_ot_map=data["drive_otros"],
                              santander_bizum_df=data.get("bizum"))

    if df_res.empty:
        st.info("Sin datos para este día. Sube al menos el ERP en la pestaña Subir archivos.")
    else:
        df_dp = resumen.estado_por_dia_permiso(df_res)
        ui.section_title(f"Estado del día {fecha.strftime('%d/%m/%Y')}")
        ccols = st.columns(3)
        for col, perm in zip(ccols, ["Permiso B", "Otros Permisos", "Tasas"]):
            sub = df_dp[df_dp["permiso"] == perm]
            estados = set(sub["estado"]) if not sub.empty else set()
            if not estados: color, txt = "#f0f1f3", "—"
            elif "error" in estados:
                n = (sub["estado"] == "error").sum()
                color, txt = "#ffd6d6", f"❌ {perm}: {n} sec con incidencia"
            elif "warn" in estados:
                n = (sub["estado"] == "warn").sum()
                color, txt = "#fff5cc", f"⚠️ {perm}: {n} sec con aviso"
            else: color, txt = "#dcf5e3", f"✅ {perm}: todas OK"
            col.markdown(f'<div style="padding:14px;border-radius:10px;background:{color};'
                         f'font-weight:600;text-align:center;">{txt}</div>',
                         unsafe_allow_html=True)

        ui.section_title("Estado por sección y permiso")
        if not df_dp.empty:
            pivot = df_dp.pivot_table(index="seccion", columns="permiso",
                                       values="estado", aggfunc="first")
            def cell_color(v):
                return {"ok":"background-color:#dcf5e3","warn":"background-color:#fff5cc",
                        "error":"background-color:#ffd6d6"}.get(v, "")
            st.dataframe(pivot.style.applymap(cell_color), use_container_width=True)

        ui.section_title("Detalle por sección · 7 líneas")
        for sec in cfg.IVERALSO_SECS:
            sub = df_res[df_res["seccion"] == sec]
            if sub.empty: continue
            sub2 = sub.copy(); sub2["línea"] = sub2["permiso"] + " · " + sub2["fp"]
            estados_sec = set(sub2["estado"])
            ico = "✅" if estados_sec <= {"ok"} else ("⚠️" if "error" not in estados_sec else "❌")
            with st.expander(f"{ico} **{sec}** · {cfg.SEC_TO_NOMBRE[sec]}"):
                disp = sub2[["línea","erp","externo","delta","estado","detalle"]].copy()
                def col_est(v):
                    return {"error":"background-color:#ffd6d6","warn":"background-color:#fff5cc",
                            "ok":"background-color:#dcf5e3","pendiente":"background-color:#dde3ff",
                            "miss":"background-color:#ffd6d6"}.get(v, "")
                st.dataframe(disp.style.format(
                    {"erp":"{:,.2f} €","externo":"{:,.2f} €","delta":"{:,.2f} €"}
                    ).applymap(col_est, subset=["estado"]), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB: RETIRADAS
# ════════════════════════════════════════════════════════════════════════════
with tab_ret:
    st.markdown("#### Retiradas y pagos por sección y caja")
    st.caption("Acumulado total de pagos detectados en Caja Permiso B y Caja Otros Permisos. "
               "Rojo hasta que un responsable las marque resueltas en Incidencias.")

    bar = st.progress(0.0, text="Cargando…")
    fechas_disco = loader.fechas_con_datos(UPLOADS, empresa)
    if not fechas_disco: fechas_disco = [fecha]
    data = loader.cargar(UPLOADS, empresa, fechas_disco,
                         progress=lambda p, t: bar.progress(min(1.0, p),
                            text=f"📂 {t}  ({int(p*100)}%)"))
    bar.empty()

    df_r = retiradas.extraer(data.get("drive_pb"), data.get("drive_otros"))
    nuevas = incidencias.registrar_retiradas(empresa, df_r)
    if nuevas: st.toast(f"{nuevas} retiradas nuevas registradas")

    if df_r.empty:
        st.info("No hay retiradas registradas todavía.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Retiradas detectadas", len(df_r))
        c2.metric("Caja Permiso B", f"{df_r[df_r['caja']=='Permiso B']['importe'].sum():,.2f} €")
        c3.metric("Caja Otros Permisos", f"{df_r[df_r['caja']=='Otros Permisos']['importe'].sum():,.2f} €")

        ui.section_title("Detalle")
        from arqueo.models import Incidencia
        with db.session() as s:
            ids_resueltas = set()
            res = s.query(Incidencia).filter(
                Incidencia.empresa_id == incidencias.empresa_id(empresa),
                Incidencia.concepto.like("Retirada%"),
                Incidencia.estado == "resuelta",
            ).all()
            for r in res:
                ids_resueltas.add((r.fecha, r.seccion, float(r.encontrado)))
        df_r["estado_actual"] = df_r.apply(
            lambda x: "resuelta" if (x["fecha"], x["seccion"], float(x["importe"])) in ids_resueltas
            else "pendiente_validar", axis=1)
        def color_est(v):
            return {"resuelta":"background-color:#dcf5e3",
                    "pendiente_validar":"background-color:#ffd6d6"}.get(v, "")
        st.dataframe(df_r.style.format({"importe":"{:,.2f} €"})
                          .applymap(color_est, subset=["estado_actual"]),
                     use_container_width=True, height=400)

    df_admin = data.get("admin", pd.DataFrame())
    if not df_admin.empty:
        ui.section_title("Movimientos en Caja Administración")
        st.dataframe(df_admin.style.format({"importe":"{:,.2f} €"}),
                     use_container_width=True, height=300)

# ════════════════════════════════════════════════════════════════════════════
# TAB: INCIDENCIAS
# ════════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.markdown("#### Incidencias")
    from arqueo.models import Incidencia
    with db.session() as s:
        rows = s.query(Incidencia).order_by(
            Incidencia.fecha.desc(), Incidencia.id.desc()
        ).limit(500).all()
    if not rows:
        st.info("Aún no hay incidencias registradas.")
    else:
        df_inc = pd.DataFrame([{
            "ID": r.id, "Fecha": r.fecha, "Sección": r.seccion, "Concepto": r.concepto,
            "ERP": r.esperado or 0.0, "Externo": r.encontrado or 0.0, "Δ": r.delta or 0.0,
            "Estado": r.estado, "Descripción": r.descripcion or "",
        } for r in rows])
        c1, c2, c3 = st.columns(3)
        c1.metric("Abiertas", (df_inc["Estado"] == "abierta").sum())
        c2.metric("Pdte validar", (df_inc["Estado"] == "pendiente_validar").sum())
        c3.metric("Resueltas", (df_inc["Estado"] == "resuelta").sum())

        ui.section_title("Acción rápida")
        st.caption("Selecciona una incidencia abierta y márcala como resuelta tras revisarla.")
        abiertas = df_inc[df_inc["Estado"].isin(["abierta", "pendiente_validar"])]
        if not abiertas.empty:
            opciones = abiertas.apply(
                lambda x: f"#{x['ID']} · {x['Fecha']} · {x['Sección']} · {x['Concepto']} · Δ {x['Δ']:,.2f}€", axis=1
            ).tolist()
            sel = st.selectbox("Incidencia a resolver", opciones, key="sel_inc")
            comentario = st.text_input("Comentario al resolver", key="com_inc")
            if st.button("✓ Marcar como resuelta", type="primary"):
                inc_id = int(sel.split("#")[1].split(" ")[0])
                with db.session() as s:
                    inc = s.query(Incidencia).get(inc_id)
                    if inc:
                        inc.estado = "resuelta"; inc.comentario = comentario
                        inc.resuelta_en = dt.datetime.utcnow(); s.commit()
                st.success(f"Incidencia #{inc_id} marcada como resuelta."); st.rerun()

        ui.section_title("Todas las incidencias")
        def color_est(v):
            return {"abierta":"background-color:#ffd6d6",
                    "pendiente_validar":"background-color:#fff5cc",
                    "resuelta":"background-color:#dcf5e3"}.get(v, "")
        st.dataframe(df_inc.style.format({"ERP":"{:,.2f} €","Externo":"{:,.2f} €","Δ":"{:,.2f} €"})
                          .applymap(color_est, subset=["Estado"]),
                     use_container_width=True, height=520)
