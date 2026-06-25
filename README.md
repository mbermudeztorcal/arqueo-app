# Arqueo App — Spike

Aplicación web para automatizar el arqueo diario de **Iveralso Málaga S.L.** (con vistas a multi-empresa).

Fase **0 (spike técnico)**: este código valida el stack y el flujo end-to-end con el día de la prueba.
Cubre subida de archivos, cuadre automático y registro de incidencias en base de datos.

---

## Funcionalidades del spike

- 📤 Subida drag & drop de los 6 tipos de archivos del día (ERP, BBVA, Cajamar, Drive Permiso B, Drive Otros Permisos, Santander Bizum).
- 🔍 Detector automático de qué archivos faltan para arquear.
- ⚖️ Botón "Arquear" que ejecuta el motor de cuadre y muestra los descuadres con código de color.
- 📋 Listado de incidencias generadas, guardadas en SQLite.

No incluye todavía (Fase 1 en adelante):

- Login Google con cuentas `@torcal.es`.
- Workflow completo de validación de incidencias (Manuel/Dani).
- Calendario rojo/verde y dashboard.
- Validación de continuidad de saldos y retiradas.

---

## Ejecutar en local

Requisitos: Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate         # Linux/Mac
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
streamlit run app.py
```

La app abre `http://localhost:8501` en tu navegador.
Los datos se guardan en `./data/` (SQLite + archivos subidos).

---

## Despliegue en Render (gratis)

1. Sube este proyecto a un repositorio en GitHub.
2. Entra en [render.com](https://render.com) y crea cuenta gratis (con tu cuenta de GitHub).
3. Pulsa **New +** → **Web Service** → conecta el repo.
4. Render detectará el archivo `render.yaml` automáticamente; deja los valores por defecto y pulsa **Create Web Service**.
5. En ~5 minutos te dará una URL del estilo `https://arqueo-app.onrender.com`.

> **Limitaciones del plan gratis de Render**:
> - La instancia se duerme tras 15 min sin tráfico (tarda ~30 s en despertar al recibir la primera petición).
> - Disco de la instancia es **efímero**: los archivos subidos y la base SQLite se pierden en cada redeploy. Para producción (Fase 1) migramos la base a Postgres gestionado (Supabase tiene 500 MB gratis) y los archivos a Supabase Storage o Cloudflare R2.

---

## Estructura del proyecto

```
arqueo-app/
├── app.py                 ← Entrypoint Streamlit
├── requirements.txt
├── render.yaml            ← Configuración de despliegue
├── runtime.txt
├── README.md
├── arqueo/
│   ├── config.py          ← Catálogo Iveralso (secciones, FUC, códigos Cajamar)
│   ├── db.py              ← Conexión SQLAlchemy
│   ├── models.py          ← Tablas: Empresa, Archivo, Movimiento, Arqueo, Incidencia
│   ├── cuadre.py          ← Motor de cuadre (reglas de negocio)
│   └── parsers/
│       ├── erp.py         ← ERP Torcal (HTML disfrazado de .xls)
│       ├── bbva.py        ← Remesas .xlsx + Norma 43 + Bizum Santander
│       ├── cajamar.py     ← Extracto Cajamar (.xls)
│       ├── drive_pb.py    ← Excel Drive Permiso B (hoja SEC.NN CAJA)
│       └── drive_otros.py ← Excel Drive Otros Permisos (hoja CAJA TORCAL)
└── data/                  ← Generado en ejecución (SQLite + uploads)
```

---

## Reglas de negocio implementadas

Las que ya validamos con la prueba del 25/05/2026:

- ✅ Tarjeta Permiso B = suma de remesas BBVA del FUC de la sección (con doble datáfono cuando aplica).
- ✅ Tasas Tarjeta = movimientos Cajamar `ABONO VENTAS CON TARJETA` por código de comercio.
- ✅ Efectivo Permiso B = `ingresos (efectivo)` del Drive Permiso B.
- ✅ Efectivo Otros Permisos = `Cobros (Efectivo)` del Drive Otros Permisos.
- ✅ **Regla intensivos**: si `B-Efectivo + Otros-Efectivo` total cuadra pero por separado no, se reporta como aviso (no error).
- ✅ Transferencias en Permiso B o Tasas → error.
- ⚠️ Bizum y Web Conjunta → marcados como avisos (no se cuadran por día, ver README maestro).

---

## Roadmap

| Fase | Estado | Contenido |
|---|---|---|
| **0 Spike** | ✅ entregable | Lo que ves aquí |
| 1 MVP | siguiente | Login Google + workflow incidencias + dashboard rojo/verde |
| 2 Retiradas y saldos | después | Caja Administración + cierre/apertura de saldos |
| 3 Multi-empresa | abierto | Onboarding de la 2ª empresa |
