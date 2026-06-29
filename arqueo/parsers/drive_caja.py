"""Parser unificado del Excel Drive 'Caja' de cada sección.
Carga el archivo una sola vez con openpyxl (tolerante con fechas mal escritas
en las hojas) y parsea las dos hojas en memoria."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from . import drive_pb, drive_otros


def detect_seccion(filename: str) -> str | None:
    return drive_pb.detect_seccion(filename) or drive_otros.detect_seccion(filename)


def parse(path: str | Path) -> dict:
    out = {"pb": pd.DataFrame(), "otros": pd.DataFrame()}
    try:
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl", header=None)
    except Exception:
        # Si openpyxl también falla, intentamos calamine como último recurso
        try:
            sheets = pd.read_excel(path, sheet_name=None, engine="calamine", header=None)
        except Exception:
            return out
    try:
        out["pb"] = drive_pb.parse_sheets(sheets)
    except Exception:
        pass
    try:
        out["otros"] = drive_otros.parse_sheets(sheets)
    except Exception:
        pass
    return out
