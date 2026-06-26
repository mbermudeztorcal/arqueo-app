"""Parser del extracto de cuenta corriente BBVA en formatos .xlsx, .txt (Norma 43) o .xml (camt.053)."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path
import pandas as pd
from . import bbva as _legacy  # parse_norma43 ya existe


def detectar_formato(path: str | Path) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls"): return "xlsx"
    if ext == ".xml": return "xml"
    if ext == ".txt": return "norma43"
    # fallback: leer cabecera
    try:
        with open(p, "rb") as f:
            head = f.read(120)
        if head.startswith(b"<?xml") or b"camt.053" in head:
            return "xml"
        if head[:2] == b"PK":
            return "xlsx"
        return "norma43"
    except Exception:
        return "xlsx"


def parse(path: str | Path) -> pd.DataFrame:
    fmt = detectar_formato(path)
    if fmt == "norma43":
        df = _legacy.parse_norma43(path)
        # Normalizar al esquema común
        if df.empty: return df
        return pd.DataFrame({
            "fecha": df["fecha_op"],
            "fecha_val": df["fecha_val"],
            "concepto": df["literal"],
            "concepto_codigo": df["concepto"],
            "importe": df["importe_signed"],
            "dh": df["dh"],
        })
    if fmt == "xml":
        return _parse_camt053(path)
    return _parse_xlsx(path)


def _parse_xlsx(path: str | Path) -> pd.DataFrame:
    """Lee un extracto BBVA en xlsx (formato estándar de descarga BBVA Net Cash)."""
    df = pd.read_excel(path, sheet_name=0, engine="calamine", header=None)
    header_row = None
    for i in range(min(30, len(df))):
        row = df.iloc[i].astype(str).str.lower()
        if any("fecha" in v for v in row) and any("importe" in v for v in row):
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()
    df.columns = df.iloc[header_row]
    df = df[header_row + 1:].reset_index(drop=True)

    def _to_d(s):
        if isinstance(s, (dt.datetime, pd.Timestamp)): return s.date()
        if isinstance(s, str):
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try: return dt.datetime.strptime(s.split()[0], fmt).date()
                except ValueError: pass
        return None

    col_fecha = next((c for c in df.columns if isinstance(c, str) and "fecha" in c.lower()), None)
    col_imp = next((c for c in df.columns if isinstance(c, str) and "importe" in c.lower()), None)
    col_conc = next((c for c in df.columns if isinstance(c, str) and ("concepto" in c.lower() or "descripcion" in c.lower())), None)
    if not col_fecha or not col_imp:
        return pd.DataFrame()
    out = []
    for _, row in df.iterrows():
        d = _to_d(row[col_fecha])
        if d is None: continue
        try: imp = float(row[col_imp])
        except (TypeError, ValueError): continue
        out.append({"fecha": d, "fecha_val": d, "concepto": str(row[col_conc]) if col_conc else "", "importe": imp, "dh": "H" if imp > 0 else "D"})
    return pd.DataFrame(out)


def _parse_camt053(path: str | Path) -> pd.DataFrame:
    """Lee un fichero camt.053 (XML SEPA) y devuelve movimientos."""
    from lxml import etree
    p = Path(path)
    tree = etree.parse(str(p))
    ns = {"c": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.06"}
    out = []
    for ntry in tree.iterfind(".//c:Ntry", ns):
        amt_el = ntry.find("c:Amt", ns)
        cd_el = ntry.find("c:CdtDbtInd", ns)
        bookg = ntry.find("c:BookgDt/c:Dt", ns)
        val = ntry.find("c:ValDt/c:Dt", ns)
        if amt_el is None or cd_el is None or bookg is None:
            continue
        try: imp = float(str(amt_el.text).replace(",", "."))
        except ValueError: continue
        signo = 1 if cd_el.text == "CRDT" else -1
        d = dt.date.fromisoformat(bookg.text)
        dv = dt.date.fromisoformat(val.text) if val is not None else d
        nombre = ""
        nm_el = ntry.find(".//c:Dbtr/c:Nm", ns) or ntry.find(".//c:Cdtr/c:Nm", ns)
        if nm_el is not None: nombre = nm_el.text or ""
        codigo = ""
        bk_el = ntry.find(".//c:BkTxCd/c:Prtry/c:Cd", ns)
        if bk_el is not None: codigo = bk_el.text or ""
        out.append({"fecha": d, "fecha_val": dv, "concepto": nombre, "concepto_codigo": codigo, "importe": signo * imp, "dh": "H" if signo > 0 else "D"})
    return pd.DataFrame(out)
