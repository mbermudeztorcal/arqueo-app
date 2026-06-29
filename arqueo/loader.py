"""Loader de fuentes con cache por (ruta, mtime) y barra de progreso opcional.

Streamlit cachea los resultados de los parsers usando la combinación
(ruta absoluta del archivo, mtime). Mientras el archivo no cambie, los re-runs
de la pestaña no vuelven a parsearlo, lo cual evita esperas largas tras subir
los archivos una sola vez.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from typing import Iterable, Callable
import pandas as pd
import streamlit as st

from .parsers import erp as erp_p, bbva as bbva_p
from .parsers import bbva_extracto as bbvaext_p, cajamar as caj_p
from .parsers import santander as sant_p
from .parsers import drive_caja as caja_p, drive_admin as adm_p


# ── Parsers con cache_data (la key es ruta + mtime) ─────────────────────────
@st.cache_data(show_spinner=False)
def _erp(path: str, _mtime: float) -> pd.DataFrame:
    return erp_p.parse(path)


@st.cache_data(show_spinner=False)
def _bbva_remesa(path: str, _mtime: float) -> dict:
    return bbva_p.parse_remesa_xlsx(path)


@st.cache_data(show_spinner=False)
def _bbva_extracto(path: str, _mtime: float) -> pd.DataFrame:
    return bbvaext_p.parse(path)


@st.cache_data(show_spinner=False)
def _cajamar(path: str, _mtime: float) -> pd.DataFrame:
    return caj_p.parse(path)


@st.cache_data(show_spinner=False)
def _santander(path: str, _mtime: float) -> pd.DataFrame:
    return sant_p.parse(path)


@st.cache_data(show_spinner=False)
def _bizum(path: str, _mtime: float) -> pd.DataFrame:
    return bbva_p.parse_bizum_santander(path)


@st.cache_data(show_spinner=False)
def _drive_caja(path: str, _mtime: float) -> dict:
    # Devuelve {'pb': df, 'otros': df}
    return caja_p.parse(path)


@st.cache_data(show_spinner=False)
def _drive_admin(path: str, _mtime: float) -> pd.DataFrame:
    return adm_p.parse(path)


# ── Utilidades de descubrimiento ────────────────────────────────────────────
def fechas_con_datos(uploads_root: Path, empresa: str) -> list[dt.date]:
    """Detecta las fechas que tienen al menos un archivo subido en cualquier fuente."""
    root = uploads_root / empresa.lower()
    if not root.exists(): return []
    out = []
    for child in sorted(root.iterdir()):
        if not child.is_dir(): continue
        try:
            f = dt.date.fromisoformat(child.name)
        except ValueError:
            continue
        if any(child.rglob("*.*")):
            out.append(f)
    return out


def _count_files(uploads_root: Path, empresa: str, fechas: Iterable[dt.date]) -> int:
    total = 0
    for f in fechas:
        d = uploads_root / empresa.lower() / f.isoformat()
        if d.exists():
            total += sum(1 for p in d.rglob("*.*") if p.is_file())
    return total


def _files_of(uploads_root: Path, empresa: str, fecha: dt.date, fuente: str) -> list[Path]:
    d = uploads_root / empresa.lower() / fecha.isoformat() / fuente
    return sorted(d.glob("*")) if d.exists() else []


# ── Carga principal con progreso ────────────────────────────────────────────
def cargar(
    uploads_root: Path, empresa: str, fechas: list[dt.date],
    progress: Callable[[float, str], None] | None = None,
) -> dict:
    """Carga todas las fuentes para las fechas indicadas, llamando a `progress`
    (porcentaje en 0..1, texto) tras cada archivo."""
    df_erps = []
    bbva_remesas = []
    df_caj = pd.DataFrame(); df_bbva_ext = pd.DataFrame()
    df_sant = pd.DataFrame(); df_bizum = pd.DataFrame()
    df_admin = pd.DataFrame()
    df_pb, df_ot = {}, {}

    total = _count_files(uploads_root, empresa, fechas) or 1
    done = 0

    def tick(text):
        nonlocal done
        done += 1
        if progress: progress(min(1.0, done / total), text)

    for fecha in fechas:
        # ERP
        for f in _files_of(uploads_root, empresa, fecha, "erp"):
            try: df_erps.append(_erp(str(f), f.stat().st_mtime))
            except Exception as e: st.warning(f"ERP {f.name}: {e}")
            tick(f"ERP · {f.name}")
        # BBVA remesas
        for f in _files_of(uploads_root, empresa, fecha, "bbva_remesas"):
            try:
                if f.suffix.lower() == ".xlsx":
                    bbva_remesas.append(_bbva_remesa(str(f), f.stat().st_mtime))
            except Exception as e: st.warning(f"BBVA remesa {f.name}: {e}")
            tick(f"Remesa BBVA · {f.name}")
        # BBVA extracto
        for f in _files_of(uploads_root, empresa, fecha, "bbva_extracto"):
            try: df_bbva_ext = pd.concat([df_bbva_ext, _bbva_extracto(str(f), f.stat().st_mtime)], ignore_index=True)
            except Exception as e: st.warning(f"Extracto BBVA {f.name}: {e}")
            tick(f"Extracto BBVA · {f.name}")
        # Cajamar
        for f in _files_of(uploads_root, empresa, fecha, "cajamar"):
            try: df_caj = pd.concat([df_caj, _cajamar(str(f), f.stat().st_mtime)], ignore_index=True)
            except Exception as e: st.warning(f"Cajamar {f.name}: {e}")
            tick(f"Cajamar · {f.name}")
        # Santander extracto
        for f in _files_of(uploads_root, empresa, fecha, "santander_ext"):
            try: df_sant = pd.concat([df_sant, _santander(str(f), f.stat().st_mtime)], ignore_index=True)
            except Exception as e: st.warning(f"Santander {f.name}: {e}")
            tick(f"Santander · {f.name}")
        # Bizum Santander
        for f in _files_of(uploads_root, empresa, fecha, "santander_bizum"):
            try: df_bizum = pd.concat([df_bizum, _bizum(str(f), f.stat().st_mtime)], ignore_index=True)
            except Exception as e: st.warning(f"Bizum {f.name}: {e}")
            tick(f"Bizum · {f.name}")
        # Drive Caja
        for f in _files_of(uploads_root, empresa, fecha, "drive_caja"):
            sec = caja_p.detect_seccion(f.name)
            if not sec:
                tick(f"Drive Caja · {f.name} (sec?)"); continue
            try:
                parsed = _drive_caja(str(f), f.stat().st_mtime)
                if not parsed["pb"].empty: df_pb[sec] = parsed["pb"]
                if not parsed["otros"].empty: df_ot[sec] = parsed["otros"]
            except Exception as e: st.warning(f"Drive Caja {sec}: {e}")
            tick(f"Drive Caja · {sec}")
        # Drive Admin
        for f in _files_of(uploads_root, empresa, fecha, "drive_admin"):
            try: df_admin = pd.concat([df_admin, _drive_admin(str(f), f.stat().st_mtime)], ignore_index=True)
            except Exception as e: st.warning(f"Drive Admin {f.name}: {e}")
            tick(f"Caja Administración · {f.name}")

    df_erp = pd.concat(df_erps, ignore_index=True) if df_erps else pd.DataFrame()
    return {"erp": df_erp, "bbva_remesas": bbva_remesas, "cajamar": df_caj,
            "drive_pb": df_pb, "drive_otros": df_ot, "bbva_extracto": df_bbva_ext,
            "santander": df_sant, "bizum": df_bizum, "admin": df_admin}
