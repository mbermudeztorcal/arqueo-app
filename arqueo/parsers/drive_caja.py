"""Parser unificado: lee el archivo una sola vez con openpyxl read_only y
pasa las hojas (list of lists) a parse_sheets de PB y Otros."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from . import drive_pb, drive_otros


def detect_seccion(filename: str) -> str | None:
    return drive_pb.detect_seccion(filename) or drive_otros.detect_seccion(filename)


def parse(path: str | Path) -> dict:
    out = {"pb": pd.DataFrame(), "otros": pd.DataFrame()}
    sheets = None
    try:
        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
        try:
            sheets = {sn: [list(row) for row in wb[sn].iter_rows(values_only=True)]
                      for sn in wb.sheetnames}
        finally:
            wb.close()
    except Exception:
        return out
    if not sheets:
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
