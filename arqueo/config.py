"""Configuración y catálogo maestro de Iveralso."""

EMPRESAS = ["Iveralso"]

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

CAJ_TO_SEC = {
    "175142181": "S05", "175251792": "S07", "175251800": "S10", "175142223": "S12",
    "175142231": "S15", "175142249": "S17", "175142256": "S25", "175269935": "S28",
    "175142272": "S31", "175251834": "S42", "175275304": "S47",
}

TERMINAL_TO_SEC = {"43788104": "S31"}

# 7 fuentes (Drive PB + Otros se han unificado en drive_caja)
FUENTES = [
    ("erp",            "ERP Torcal",
     "Listado diario de cobros · .xls / .xlsx",
     "📋", False),
    ("bbva_extracto",  "Extracto BBVA",
     "Cuenta corriente · .xlsx, .txt (Norma 43) o .xml (camt.053)",
     "🏦", False),
    ("bbva_remesas",   "Remesas TPVs BBVA",
     f"Una remesa por FUC · {len(FUC_TO_SEC)} comercios mapeados, incluido Web Conjunta",
     "💳", True),
    ("cajamar",        "Cajamar – Tasas",
     f"Abono ventas con tarjeta · {len(CAJ_TO_SEC)} códigos mapeados",
     "📜", False),
    ("santander_ext",  "Extracto Santander",
     "Cuenta corriente · .xlsx",
     "🏦", False),
    ("santander_bizum","Santander – Bizum",
     "Abonos Bizum (transitorio hasta FUC Bizum BBVA)",
     "📱", False),
    ("drive_caja",     "Drive Caja por sección",
     "11 archivos (1 por sección) · cada uno con hojas Permiso B y Otros Permisos",
     "📒", True),
    ("drive_admin",    "Drive Caja Administración",
     "Caja Administración / Responsable · cuadra las retiradas de las secciones",
     "🗄️", False),
]

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
