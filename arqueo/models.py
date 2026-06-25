"""Modelos SQLAlchemy. SQLite ahora, Postgres después con el mismo código."""
from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Float, ForeignKey, Text, Boolean, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Empresa(Base):
    __tablename__ = "empresas"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    cif = Column(String)
    creada_en = Column(DateTime, default=dt.datetime.utcnow)


class Archivo(Base):
    __tablename__ = "archivos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    fuente = Column(String, nullable=False)  # erp | bbva | cajamar | drive_pb | drive_otros | santander_bizum
    fecha_dia = Column(Date, nullable=False)
    ruta = Column(String, nullable=False)
    nombre_original = Column(String)
    parsed_ok = Column(Boolean, default=False)
    subido_por = Column(String, default="sistema")
    subido_en = Column(DateTime, default=dt.datetime.utcnow)


class Movimiento(Base):
    __tablename__ = "movimientos"
    id = Column(Integer, primary_key=True)
    archivo_id = Column(Integer, ForeignKey("archivos.id"))
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    fuente = Column(String, nullable=False)
    fecha = Column(Date, nullable=False)
    seccion = Column(String)
    tipo_permiso = Column(String)
    tipo_concepto = Column(String)
    fp = Column(String)
    importe = Column(Float, nullable=False, default=0.0)
    alumno = Column(String)
    ref = Column(String)
    raw = Column(Text)


class Arqueo(Base):
    __tablename__ = "arqueos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    fecha_desde = Column(Date, nullable=False)
    fecha_hasta = Column(Date, nullable=False)
    lanzado_por = Column(String, default="anon")
    lanzado_en = Column(DateTime, default=dt.datetime.utcnow)
    estado = Column(String, default="ok")  # ok | con_incidencias


class Incidencia(Base):
    __tablename__ = "incidencias"
    id = Column(Integer, primary_key=True)
    arqueo_id = Column(Integer, ForeignKey("arqueos.id"))
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    fecha = Column(Date, nullable=False)
    seccion = Column(String)
    concepto = Column(String)
    esperado = Column(Float)
    encontrado = Column(Float)
    delta = Column(Float)
    descripcion = Column(Text)
    estado = Column(String, default="abierta")  # abierta | pendiente_validar | resuelta
    comentario = Column(Text)
    abierta_en = Column(DateTime, default=dt.datetime.utcnow)
    resuelta_en = Column(DateTime)
