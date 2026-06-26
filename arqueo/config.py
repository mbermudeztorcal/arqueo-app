"""Configuración y catálogo maestro de Iveralso."""

EMPRESAS = ["Iveralso"]

# Las 11 secciones de Iveralso
SECCIONES_IVERALSO = [
    {"codigo": "S05", "nombre": "Corazones"},
    {"codigo": "S07", "nombre": "C/ Don Cristian"},
    {"codigo": "S10", "nombre": "C/ Manrique"},
    {"codigo": "S12", "nombre": "Huelin"},
    {"codigo": "S15", "nombre": "Av. Plutarco"},
    {"codigo": "S17", "nombre": "Alhaurín de la Torre"},
    {"codigo": "S25", "nombre": "Camino del Pato"},
    {"codigo": "S28", "nombre": "Delicias"},
    {"codigo": "S31", "nombre": "C/ Ayala"},
    {"codigo": "S42", "nombre": "La Luz"},
    {"codigo": "S47", "nombre": "El Palo"},
]

IVERALSO_SECS = [s["codigo"] for s in SECCIONES_IVERALSO]
SEC_TO_NOMBRE = {s["codigo"]: s["nombre"] for s in SECCIONES_IVERALSO}

# FUC BBVA -> Sección Iveralso (incluye dobles datáfonos)
FUC_TO_SEC = {
    "348406919": "S05",
    "348342072": "S07",
    "348342148": "S10", "368154258": "S10",
    "348338575": "S12",
    "348407032": "S15", "368155537": "S15",
    "348345182": "S17",
    "348338617": "S25",
    "348406851": "S28",
    "348406794": "S31",
    "350082228": "S42", "348338682": "S42",
    "348346073": "S47", "368153896": "S47",
    "368761680": "WEB_CONJUNTA",
}

# Cajamar código de comercio -> Sección
CAJ_TO_SEC = {
    "175142181": "S05", "175251792": "S07", "175251800": "S10", "175142223": "S12",
    "175142231": "S15", "175142249": "S17", "175142256": "S25", "175269935": "S28",
    "175142272": "S31", "175251834": "S42", "175275304": "S47",
}

# Terminal BBVA (formato "Listado de remesas") -> Sección
TERMINAL_TO_SEC = {"43788104": "S31"}

# 8 fuentes de datos por día
FUENTES = [
    ("erp",            "ERP Torcal",                          "Listado diario de cobros (.xls/.xlsx)"),
    ("bbva_extracto",  "Extracto BBVA (cuenta)",              "Movimientos de la cuenta corriente BBVA: .xlsx, .txt (Norma 43) o .xml (camt.053)"),
    ("bbva_remesas",   "Remesas TPVs BBVA",                   f"Una remesa por FUC ({len(FUC_TO_SEC)} comercios mapeados, incluido Web Conjunta)"),
    ("cajamar",        "Cajamar – Extracto Tasas",            f"Movimientos abono ventas con tarjeta ({len(CAJ_TO_SEC)} códigos mapeados)"),
    ("santander_ext",  "Extracto Santander (cuenta)",         "Movimientos cuenta corriente Santander (.xlsx)"),
    ("santander_bizum","Santander – Extracto Bizum",          "Abonos Bizum (transitorio mientras llega el FUC Bizum BBVA)"),
    ("drive_pb",       "Drive Excel Permiso B",               "11 archivos, uno por sección"),
    ("drive_otros",    "Drive Excel Otros Permisos",          "11 archivos, uno por sección"),
]

# Formas de pago × tipo permiso = las 7 líneas del resumen diario por sección
LINEAS_RESUMEN = [
    ("Permiso B",     "Tarjeta"),
    ("Permiso B",     "Efectivo"),
    ("Permiso B",     "Bizum"),
    ("Otros Permisos","Efectivo"),
    ("Otros Permisos","Bizum"),
    ("Tasas",         "Tarjeta"),
    ("Tasas",         "Bizum"),
]

SECCIONES_CON_DOBLE_FUC = {"S10", "S15", "S42", "S47"}
