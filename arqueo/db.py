"""Inicialización de la sesión SQLAlchemy."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Empresa
from . import config as cfg


def get_data_dir() -> Path:
    """Carpeta de datos persistentes. En Render apuntamos a /tmp o a un volumen."""
    p = Path(os.environ.get("ARQUEO_DATA_DIR", "data")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / "uploads").mkdir(exist_ok=True)
    return p


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_path = get_data_dir() / "arqueo.db"
        db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False, future=True)


_engine = None
_Session = None


def session():
    global _engine, _Session
    if _engine is None:
        _engine = get_engine()
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
        # Seed Iveralso si no existe
        with _Session() as s:
            if not s.query(Empresa).filter_by(nombre="Iveralso").first():
                s.add(Empresa(nombre="Iveralso", cif="B93381259"))
                s.commit()
    return _Session()
