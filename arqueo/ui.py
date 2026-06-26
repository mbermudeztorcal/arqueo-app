"""Estilos y componentes de UI."""
import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Cabecera principal */
.brand-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    background: linear-gradient(135deg, #1f3a5f 0%, #2d5a8f 100%);
    color: white;
    border-radius: 14px;
    box-shadow: 0 4px 12px rgba(31,58,95,0.15);
    margin-bottom: 22px;
}
.brand-header .logo {
    width: 44px; height: 44px;
    background: rgba(255,255,255,0.18);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px;
}
.brand-header h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.3px;
}
.brand-header .subtitle {
    font-size: 13px;
    opacity: 0.85;
    margin-top: 2px;
}

/* Cards de fuentes */
[data-testid="stContainer"] > div > div > [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid #e3e8ef !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: border-color .15s ease;
}
[data-testid="stContainer"] > div > div > [data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #c9d2e0 !important;
}

/* Métricas */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e3e8ef;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
[data-testid="stMetricLabel"] { font-weight: 500; color: #5b6573; font-size: 13px; }
[data-testid="stMetricValue"] { font-weight: 700; }

/* Badges de estado */
.status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
.status-ok    { background:#dcf5e3; color:#1f7a3a; }
.status-warn  { background:#fff3c4; color:#8a6500; }
.status-err   { background:#ffd6d6; color:#a31919; }
.status-pend  { background:#dde3ff; color:#384b9a; }
.status-miss  { background:#f0f1f3; color:#6b7280; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f4f6fa;
    padding: 6px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
    color: #4b5666;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #1f3a5f !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* DataFrame */
[data-testid="stDataFrame"] {
    border: 1px solid #e3e8ef;
    border-radius: 12px;
    overflow: hidden;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e3e8ef;
}

/* Esconder elementos por defecto de Streamlit */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display:none; }

/* Botones primarios */
button[kind="primary"] {
    background: #1f3a5f !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 6px rgba(31,58,95,0.2);
}
button[kind="primary"]:hover { background: #2d5a8f !important; }

/* Spacing helper */
.section-title {
    font-size: 14px;
    font-weight: 600;
    color: #1f3a5f;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    margin: 28px 0 12px;
}
</style>
"""

def render_header(empresa: str, subtitle: str = "Arqueo automático"):
    """Cabecera principal con branding."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"""
        <div class="brand-header">
            <div class="logo">⚖️</div>
            <div>
                <h1>{empresa}</h1>
                <div class="subtitle">{subtitle}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def status_badge(estado: str) -> str:
    cls = {"ok":"ok", "warn":"warn", "error":"err", "pendiente":"pend", "miss":"miss"}.get(estado, "miss")
    label = {"ok":"OK", "warn":"AVISO", "error":"ERROR", "pendiente":"PDTE", "miss":"FALTA"}.get(estado, "—")
    return f'<span class="status-badge status-{cls}">{label}</span>'


def section_title(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)
