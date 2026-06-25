"""Parser de los archivos BBVA Net Cash: remesas individuales (.xlsx) y Norma 43 (.txt)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
from typing import Iterable
import pandas as pd
from .. import config as cfg


def _parse_amount(s):
    if not isinstance(s, str):
        return None
    s = s.replace("EUR", "").strip().lstrip("+").lstrip("-")
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_es(s):
    if not isinstance(s, str):
        return None
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", s)
    if not m:
        return None
    months = {"Ene":1,"Feb":2,"Mar":3,"Abr":4,"May":5,"Jun":6,
              "Jul":7,"Ago":8,"Sep":9,"Oct":10,"Nov":11,"Dic":12}
    d = int(m.group(1)); y = int(m.group(3))
    mo = months.get(m.group(2)[:3])
    return dt.date(y, mo, d) if mo else None


def parse_remesa_xlsx(path: str | Path) -> dict:
    """Devuelve un dict con FUC, sección, importe y movimientos (si los hay)."""
    df = pd.read_excel(path, sheet_name=0, engine="calamine", header=None)
    out = {"file": str(path), "fuc": None, "sec": None, "tipologia": None,
           "fecha_remesa": None, "importe": None, "nombre": None, "movimientos": []}
    listing_row = None
    for r in range(len(df)):
        for c in range(df.shape[1]):
            v = df.iat[r, c]
            if isinstance(v, str):
                m = re.match(r"Comercio (\d+)", v)
                if m:
                    out["fuc"] = m.group(1)
                if v == "Nombre del comercio" and c + 1 < df.shape[1]:
                    out["nombre"] = df.iat[r, c + 1]
                if v == "TIPOLOGÍA" and c + 1 < df.shape[1]:
                    out["tipologia"] = df.iat[r, c + 1]
                if v == "FACTURACIÓN" and c + 1 < df.shape[1]:
                    out["importe"] = _parse_amount(df.iat[r, c + 1])
                if v == "FECHA" and c + 1 < df.shape[1] and r == 9:
                    out["fecha_remesa"] = _parse_date_es(df.iat[r, c + 1])
                if v.strip() == "Listado de movimientos":
                    listing_row = r
    out["sec"] = cfg.FUC_TO_SEC.get(out["fuc"]) if out["fuc"] else None

    if listing_row is not None:
        for r in range(listing_row + 2, len(df)):
            fecha_str = df.iat[r, 1] if df.shape[1] > 1 else None
            importe_str = df.iat[r, 8] if df.shape[1] > 8 else None
            d = _parse_date_es(fecha_str) if isinstance(fecha_str, str) else None
            if d and importe_str is not None:
                out["movimientos"].append({
                    "fecha": d,
                    "importe": _parse_amount(str(importe_str))
                })

    # Formato 2: "Listado de remesas" (mensual con terminales)
    if not out["fuc"]:
        for r in range(len(df)):
            for c in range(df.shape[1]):
                v = df.iat[r, c]
                if isinstance(v, str) and v.strip() == "Listado de remesas":
                    for rr in range(r + 2, len(df)):
                        fecha_str = df.iat[rr, 1] if df.shape[1] > 1 else None
                        terminal = df.iat[rr, 3] if df.shape[1] > 3 else None
                        importe_str = df.iat[rr, 7] if df.shape[1] > 7 else None
                        d = _parse_date_es(fecha_str) if isinstance(fecha_str, str) else None
                        if d and terminal is not None and importe_str is not None:
                            sec = cfg.TERMINAL_TO_SEC.get(str(terminal))
                            out["movimientos"].append({
                                "fecha": d,
                                "terminal": str(terminal),
                                "sec": sec,
                                "importe": _parse_amount(str(importe_str))
                            })
                    break
    return out


def parse_bizum_santander(path: str | Path) -> pd.DataFrame:
    """Lee el extracto de Bizum de Santander y devuelve los abonos Bizum."""
    df = pd.read_excel(path, sheet_name="movimientos", engine="calamine", header=None)
    df.columns = df.iloc[7]
    df = df[8:].reset_index(drop=True)
    abonos = df[df["Concepto"].astype(str).str.startswith("Abono Bizum")].copy()

    def _to_date(s):
        if isinstance(s, str):
            try: return dt.datetime.strptime(s, "%d/%m/%Y").date()
            except ValueError: pass
        if isinstance(s, (dt.datetime, pd.Timestamp)):
            return s.date()
        return None

    def _extract_alumno(c):
        if not isinstance(c, str): return ""
        m = re.search(r"Para ([\w\sÁÉÍÓÚÑáéíóúñ]+?)\s+\d{1,2}/\d{1,2}/\d{4}", c)
        return m.group(1).strip().upper() if m else ""

    abonos["fecha_op"] = abonos["Fecha Operación"].apply(_to_date)
    abonos["alumno"] = abonos["Concepto"].apply(_extract_alumno)
    abonos["importe"] = abonos["Importe"].astype(float)
    return abonos[["fecha_op", "alumno", "importe", "Concepto"]].rename(columns={"Concepto": "concepto"})


def parse_norma43(path: str | Path) -> pd.DataFrame:
    """Lee fichero Norma 43 (Cuaderno 43) y separa bruto, comisiones, etc."""
    p = Path(path)
    for enc in ("latin1", "utf-8"):
        try:
            with open(p, "r", encoding=enc) as f:
                lines = [l.rstrip("\r\n") for l in f if l.strip()]
            break
        except Exception:
            continue

    rows = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("22") and len(l) >= 42:
            try:
                fop = l[10:16]; fval = l[16:22]
                fop_d = dt.date(2000 + int(fop[:2]), int(fop[2:4]), int(fop[4:6]))
                fval_d = dt.date(2000 + int(fval[:2]), int(fval[2:4]), int(fval[4:6]))
            except ValueError:
                i += 1
                continue
            concepto = f"{l[22:24]}+{l[24:27]}"
            dh = l[27:28]
            importe = int(l[28:42]) / 100.0
            extra = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("23"):
                extra.append(lines[j][4:].strip())
                j += 1
            rows.append({
                "fecha_op": fop_d,
                "fecha_val": fval_d,
                "concepto": concepto,
                "dh": "D" if dh == "1" else "H",
                "importe_signed": -importe if dh == "1" else importe,
                "importe": importe,
                "literal": (l[52:].strip() + " " + " ".join(extra)).strip(),
            })
            i = j
        else:
            i += 1
    return pd.DataFrame(rows)
