"""Persistencia de incidencias (errores del arqueo) en la BD."""
from __future__ import annotations
import datetime as dt
from typing import Iterable
from . import db
from .models import Arqueo, Incidencia, Empresa
from .cuadre import Diferencia


def empresa_id(nombre: str) -> int:
    with db.session() as s:
        emp = s.query(Empresa).filter_by(nombre=nombre).first()
        return emp.id if emp else 1


def registrar_arqueo(nombre_empresa: str, fecha: dt.date, difs: Iterable[Diferencia]) -> int:
    """Crea un Arqueo + Incidencias asociadas. Devuelve arqueo_id."""
    eid = empresa_id(nombre_empresa)
    con_inc = any(d.severity in ("error", "warn", "miss") for d in difs)
    with db.session() as s:
        arq = Arqueo(
            empresa_id=eid, fecha_desde=fecha, fecha_hasta=fecha,
            lanzado_por="app", estado="con_incidencias" if con_inc else "ok",
        )
        s.add(arq); s.flush()
        # Borrar incidencias previas abiertas del día para evitar duplicados
        s.query(Incidencia).filter(
            Incidencia.empresa_id == eid,
            Incidencia.fecha == fecha,
            Incidencia.estado.in_(("abierta", "pendiente_validar")),
        ).delete(synchronize_session=False)
        for d in difs:
            if d.severity in ("ok",):
                continue
            estado = {"miss": "abierta", "error": "abierta", "warn": "pendiente_validar",
                      "pendiente": "pendiente_validar"}.get(d.severity, "abierta")
            s.add(Incidencia(
                arqueo_id=arq.id, empresa_id=eid, fecha=d.fecha, seccion=d.seccion,
                concepto=d.concepto, esperado=d.esperado, encontrado=d.encontrado,
                delta=d.delta, descripcion=d.descripcion, estado=estado,
            ))
        s.commit()
        return arq.id


def registrar_retiradas(nombre_empresa: str, df) -> int:
    """Crea incidencias 'pendiente_validar' por cada retirada del Drive."""
    if df is None or df.empty: return 0
    eid = empresa_id(nombre_empresa)
    n = 0
    with db.session() as s:
        for _, r in df.iterrows():
            # Evitar duplicados: misma fecha, sección, importe, concepto='Retirada ...'
            concepto = f"Retirada {r.get('caja','')} · {r.get('concepto') or ''}".strip(" ·")
            exists = s.query(Incidencia).filter(
                Incidencia.empresa_id == eid, Incidencia.fecha == r["fecha"],
                Incidencia.seccion == r["seccion"], Incidencia.concepto == concepto,
                Incidencia.encontrado == float(r["importe"]),
            ).first()
            if exists: continue
            s.add(Incidencia(
                empresa_id=eid, fecha=r["fecha"], seccion=r["seccion"],
                concepto=concepto, esperado=0.0, encontrado=float(r["importe"]),
                delta=float(r["importe"]),
                descripcion=str(r.get("notas") or r.get("cliente") or ""),
                estado="pendiente_validar",
            ))
            n += 1
        s.commit()
    return n
