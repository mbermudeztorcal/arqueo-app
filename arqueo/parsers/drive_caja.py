"""Parser unificado del Excel Drive 'Caja' de cada sección.

Cada archivo del Drive contiene 2 hojas relevantes:
- Hoja 'SEC.NN CAJA' → movimientos de Permiso B (efectivo)
- Hoja 'CAJA TORCAL' → movimientos de Otros Permisos (efectivo)
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from . import drive_pb, drive_otros


def detect_seccion(filename: str) -> str | None:
    """Detecta sección desde el nombre del archivo (cualquier convención)."""
    return drive_pb.detect_seccion(filename) or drive_otros.detect_seccion(filename)


def parse(path: str | Path) -> dict:
    """Devuelve {'pb': df, 'otros': df} con ambos parseos."""
    out = {"pb": pd.DataFrame(), "otros": pd.DataFrame()}
    try:
        out["pb"] = drive_pb.parse(path)
    except Exception:
        pass
    try:
        out["otros"] = drive_otros.parse(path)
    except Exception:
        pass
    return out
