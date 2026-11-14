import hashlib
import json
import math
import re
from contextlib import contextmanager
from datetime import datetime
from html import escape as hesc
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# =====================================================
# STREAMLIT PAGE CONFIGURATION
# Must be called once, before any other st.* command
# =====================================================
APP_TITLE = "HSKH Ultrafiltration Design"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Local project modules
from ultrapro_ui import vendor_selector, rack_rules
import water_chemistry as chem

# Check that water_chemistry.py is up to date
_missing = [
    f
    for f in ("analyze", "auto_balance", "cleaning_demand")
    if not hasattr(chem, f)
]

if _missing:
    st.error(
        f"water_chemistry.py is out of date "
        f"(missing: {', '.join(_missing)}). "
        f"Replace it with the latest water_chemistry.py, "
        f"then restart Streamlit. File in use: {chem.__file__}"
    )
    st.stop()

ss = st.session_state

# =====================================================
# APP SETTINGS
# =====================================================
APP_WIDTH_VW = 75                                               # content width, % of screen
PROJECT_DIR = Path(__file__).resolve().parent / "UltraPRO_Projects"
AUTOLOAD_LAST = True                                            # re-open last project at start-up
NO_SAVE_PREFIX = ("_", "ui_", "FormSubmitter", "nav", "w_")           # keys never written to project files

MAIN_TABS = ["📁 Projects", "🧩 System Design", "💧 Feed", "🔷 UF", "📄 Report"]
UF_TABS = ["📐 Design", "⚙️ Configuration", "🔄 Backwash", "🧪 CEB", "🧼 CIP", "🛠 Additional Settings"]


# =====================================================
# LOOK & FEEL  (light blue / metallic grey / silver gradient page, light grey gradient boxes with black boundaries)
# =====================================================
def apply_layout_css():
    # tab-style navigation buttons (top tabs + sidebar tabs): white tabs, black outline, violet active tab
    nav_css = ""
    for scope in (".st-key-topnav", ".st-key-sidenav"):
        nav_css += f"""
    {scope} button[kind="secondary"], {scope} button[data-testid="stBaseButton-secondary"] {{
        background:#E3E5E8 !important; border:1px solid #000000 !important; box-shadow:none !important;
    }}
    {scope} button[kind="secondary"] *, {scope} button[data-testid="stBaseButton-secondary"] * {{
        color:#111111 !important; font-weight:700 !important;
    }}
    {scope} button[kind="secondary"]:hover, {scope} button[data-testid="stBaseButton-secondary"]:hover {{
        background:#CFD3D8 !important; border-color:#000000 !important;
    }}
    {scope} button[kind="primary"], {scope} button[data-testid="stBaseButton-primary"] {{
        background:linear-gradient(180deg,#CDD1D6,#A9B0B8) !important; border:1px solid #000000 !important;
        box-shadow:0 3px 8px rgba(0,0,0,.5) !important;
    }}
    {scope} button[kind="primary"] *, {scope} button[data-testid="stBaseButton-primary"] * {{
        color:#111111 !important; font-weight:800 !important;
    }}
    {scope} button {{ font-size:15px; padding:.55rem .8rem; border-radius:10px; }}
    """
    css = """
    <style>
    :root { color-scheme: light; }
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stHeader"] { background: transparent; }

    /* ---------- light blue / metallic grey / silver gradient background (full page) ---------- */
    .stApp {
        background:
            linear-gradient(135deg, #DCEEFB 0%, #C5D3E0 22%, #AEB8C4 42%, #D9DEE4 60%, #B7C1CC 80%, #E3EBF3 100%) fixed;
        color:#111111;
    }
    [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { background: transparent !important; }
    .block-container {
        max-width: __W__vw !important; padding: 0 0 3rem 0 !important; background: transparent;
        margin-top: 0 !important;
    }
    @media (max-width: 1200px) { .block-container { max-width: 96vw !important; } }

    /* Streamlit's markdown container has a negative bottom margin; this padding stops
       the next element from overlapping our custom HTML blocks */
    .mdw { padding-bottom: 1rem; }

    /* the element that only holds this CSS is invisible but still adds a flex gap above the title */
    [data-testid="stElementContainer"]:has(style), .element-container:has(style) {
        display: none !important;
    }

    /* ---------- title stays fixed at the top while scrolling ---------- */
    [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; }
    [data-testid="stElementContainer"]:has(.hdr), .element-container:has(.hdr) {
        position: sticky; top: 0; z-index: 999;
        background: rgba(222,232,243,.96); backdrop-filter: blur(6px);
        box-shadow: 0 4px 10px rgba(40,60,90,.28); border-radius: 0 0 12px 12px;
        padding: 8px 10px 0 10px; margin-top: 0;
    }

    /* ---------- big title band ---------- */
    .hdr { display:flex; justify-content:space-between; align-items:flex-end; gap:16px;
           padding: 6px 4px 12px 4px; border-bottom: 3px solid #7658CC; }
    .hdr-title { font-size: 28px; font-weight: 900; color:#2A1559; letter-spacing:.5px; line-height:1.05; }
    .hdr-sub { color:#5B3FB5; font-size:11px; letter-spacing:2.5px; text-transform:uppercase;
               margin-top:4px; font-weight:700; }
    .hdr-right { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
    .chip { background:#fff; border:1px solid #000; color:#111; padding:4px 12px;
            border-radius:999px; font-size:12.5px; font-weight:700; white-space:nowrap; }
    .chip.ok { background:#E3E5E8; }
    .page-h { color:#2A1559; font-size:22px; font-weight:800; margin: 4px 2px 0 2px; letter-spacing:.3px; }

    /* ---------- white cards, black boundary ---------- */
    [class*="st-key-card_"] {
        background:linear-gradient(135deg,#FFFFFF 0%,#F1F2F4 55%,#DADDE1 100%); border:2px solid #000000; border-radius:12px;
        padding: 12px 18px 14px 18px; box-shadow: 0 4px 14px rgba(0,0,0,.20);
        margin-bottom: .35rem; gap: .55rem; color:#1B1B1B;
    }
    [class*="st-key-pcard_"] {
        background:#F4F5F7; border:1px solid #000000; border-radius:10px; padding: 10px 14px; gap:.45rem;
    }
    [class*="st-key-pcard_"]:hover { box-shadow:0 3px 10px rgba(0,0,0,.35); }
    .card-title { font-weight:800; color:#111111; font-size:15px; letter-spacing:.3px; line-height:1.3;
                  border-bottom:2px solid #000000; padding-bottom:5px; }
    .sub { font-weight:800; color:#5B3FB5; font-size:12px; text-transform:uppercase; letter-spacing:.7px;
           line-height:1.3; margin-top:4px; }
    .pname { font-weight:800; color:#111111; font-size:15px; line-height:1.35; }
    .pmeta { color:#4A4A4A; font-size:12px; line-height:1.45; }

    /* ---------- small "automatic data" tiles (equal-size grid), black outline ---------- */
    .tiles { display:grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap:8px; }
    .tile { background:#F4F5F7; border:1px solid #000000; border-left:5px solid #7B838D;
            border-radius:8px; padding:5px 10px; min-width:0; min-height:46px; }
    .tile .t-l { font-size:10px; color:#4A4A4A; text-transform:uppercase; letter-spacing:.5px; line-height:1.3; }
    .tile .t-v { font-size:14px; font-weight:800; color:#111111; line-height:1.3; overflow-wrap:anywhere; }
    .tile.warn { border-left-color:#E08A00; background:#FFF7E8; }
    .tile.bad  { border-left-color:#C62828; background:#FDECEC; }
    .tile.good { border-left-color:#1B8F5A; background:#E6F6EC; }

    /* ---------- design-check rows & header chips ---------- */
    .chk { padding:6px 10px; border:1px solid #000000; border-left-width:5px; border-radius:6px; margin-bottom:5px;
           font-size:13px; line-height:1.4; }
    .chk.ok   { background:#E6F6EC; border-left-color:#1B8F5A; color:#1B4D34; }
    .chk.warn { background:#FFF7E8; border-left-color:#E08A00; color:#6B4A00; }
    .chk.bad  { background:#FDECEC; border-left-color:#C62828; color:#7A1F1F; }
    .chk.info { background:#F4F5F7; border-left-color:#7B838D; color:#111111; }
    .chip.dgood { background:#E6F6EC; color:#1B4D34; }
    .chip.dwarn { background:#FFF7E8; color:#6B4A00; }
    .chip.dbad  { background:#FDECEC; color:#7A1F1F; }

    /* ---------- text stays dark inside the white boxes (even if Streamlit is in dark mode) ---------- */
    [class*="st-key-card_"] p, [class*="st-key-card_"] li, [class*="st-key-card_"] label,
    [class*="st-key-card_"] [data-testid="stMarkdownContainer"], [class*="st-key-card_"] [data-testid="stCheckbox"] span,
    [class*="st-key-card_"] [data-testid="stRadio"] span, [class*="st-key-card_"] [data-testid="stToggle"] span { color:#1B1B1B !important; }
    [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { font-size:12.5px; font-weight:700; color:#1B1B1B !important; margin-bottom:0; }
    .stCaption, [data-testid="stCaptionContainer"] { color:#4A4A4A !important; }

    /* ---------- inputs: white, black boundary; calculated / disabled: grey ---------- */
    [data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"],
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {
        background:#FFFFFF !important; background-color:#FFFFFF !important; border:1px solid #000000 !important; border-radius:6px !important; }
    div[data-baseweb="base-input"], div[data-baseweb="base-input"] > div { background:transparent !important; background-color:transparent !important; }
    input, textarea { background-color:#FFFFFF !important; color:#111111 !important; -webkit-text-fill-color:#111111 !important; caret-color:#111111; }
    div[data-baseweb="select"] div, div[data-baseweb="select"] span, div[data-baseweb="select"] input {
        background-color:#FFFFFF !important; color:#111111 !important; -webkit-text-fill-color:#111111 !important; }
    div[data-baseweb="select"] svg { fill:#111111 !important; }
    input:disabled, textarea:disabled { background-color:#E6E6E6 !important; -webkit-text-fill-color:#555555 !important; color:#555555 !important; }
    div[data-baseweb="input"]:has(input:disabled), [data-testid="stNumberInputContainer"]:has(input:disabled) {
        background:#E6E6E6 !important; background-color:#E6E6E6 !important; }
    div[data-baseweb="select"]:has([aria-disabled="true"]) div { background-color:#E6E6E6 !important; }
    [data-testid="stNumberInput"] button { background-color:#FFFFFF !important; color:#111111 !important; border-color:#000000 !important; }
    [data-testid="stNumberInput"] button svg { fill:#111111 !important; }
    [data-testid="stFileUploaderDropzone"] { background-color:#FFFFFF !important; border:1px dashed #000000 !important; }
    [data-testid="stFileUploaderDropzone"] * { color:#111111 !important; }
    [data-testid="stFileUploaderDropzone"] button { background-color:#E6E6E6 !important; border:1px solid #000000 !important; }
    [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input { font-size:13.5px; padding:.28rem .55rem; }
    [data-testid="stNumberInput"] > div > div, [data-testid="stTextInput"] > div > div { min-height: 2.05rem; }
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height:2.05rem; font-size:13.5px; }
    [data-testid="stAlert"] { padding: .45rem .8rem; font-size: 13px; border:1px solid #000000; border-radius:8px; }

    /* ---------- buttons ---------- */
    .stButton button, .stDownloadButton button {
        background: linear-gradient(180deg,#F0F1F3,#D2D6DB); color:#1B1B1B; border:1px solid #000000; border-radius:8px;
        font-weight:700; width:100%; padding:.35rem .8rem;
    }
    .stButton button p, .stDownloadButton button p { color:#1B1B1B !important; }
    .stButton button:hover, .stDownloadButton button:hover { background:#C3C8CE; color:#1B1B1B; }
    .stButton button:disabled { background:#E3E5E8; color:#7A7F87; border-color:#000000; }

    /* ---------- read-only tables (light HTML, black grid) ---------- */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { border:1px solid #000000; border-radius:6px; }
    .htbl-wrap { overflow-x:auto; border:1px solid #000000; border-radius:6px; background:#FFFFFF; }
    table.htbl { border-collapse:collapse; width:100%; font-size:12.5px; color:#111111; }
    table.htbl th { background:#E3E5E8; color:#111111; text-align:left; padding:6px 10px; font-weight:700; white-space:nowrap; border:1px solid #000000; }
    table.htbl td { padding:5px 10px; border:1px solid #000000; color:#111111; background:#FFFFFF; }
    table.htbl tr:nth-child(even) td { background:#F3F4F6; }

    /* ---------- sidebar (UF tabs): light blue / metallic silver gradient ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(190deg, #E4F1FB 0%, #C3CFDB 45%, #A9B4C1 75%, #D3DAE2 100%);
        border-right: 2px solid #000000;
    }
    [data-testid="stSidebar"] * { color:#1B1B1B; }
    .sb-brand { font-size:22px; font-weight:900; letter-spacing:.5px; line-height:1.1; padding:4px 2px 10px 2px;
                border-bottom:2px solid #7658CC; color:#2A1559; }
    .sb-brand small { display:block; font-size:11px; font-weight:700; letter-spacing:2px; color:#5B3FB5;
                      text-transform:uppercase; margin-top:3px; }
    .sb-h { font-size:11px; letter-spacing:2px; font-weight:800; color:#5B3FB5; margin:6px 0 0 2px; text-transform:uppercase; }
    .sb-row { display:flex; justify-content:space-between; gap:8px; font-size:12.5px; padding:5px 8px; margin-bottom:4px;
              background:#fff; border:1px solid #000; border-radius:6px; }
    .sb-row, .sb-row * { color:#111111 !important; }
    .sb-row b { text-align:right; overflow-wrap:anywhere; }
    .sb-status { font-size:12px; background:#fff; border:1px solid #000; border-radius:8px; padding:6px 10px; }
    .sb-status, .sb-status * { color:#111111 !important; }
    .st-key-sidenav button { justify-content:flex-start; text-align:left; }
    </style>
    """.replace("__W__", str(APP_WIDTH_VW))
    st.markdown(css + "<style>" + nav_css + "</style>", unsafe_allow_html=True)

apply_layout_css()

AUTO_WRITE_THEME = True       # create .streamlit/config.toml (light theme) where you start Streamlit, if it has no [theme]
THEME_TOML = """[theme]
base = "light"
primaryColor = "#6D4FC2"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F2F2F2"
textColor = "#111111"
"""


def _ensure_light_theme():
    try:
        cfg = Path.cwd() / ".streamlit" / "config.toml"
        old = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        if "[theme]" in old:
            return False
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(old + ("\n" if old else "") + THEME_TOML, encoding="utf-8")
        return True
    except OSError:
        return False


if AUTO_WRITE_THEME and "_theme_checked" not in st.session_state:
    st.session_state["_theme_checked"] = True
    if _ensure_light_theme():
        st.session_state["_theme_note"] = True


# =====================================================
# UI HELPERS
# =====================================================
_CARD_N = [0]
_FLOW_PH = [None]          # placeholder for the process-flow diagram shown under each page title


def md(html):
    """Custom HTML block. The bottom padding (.mdw) stops Streamlit's negative markdown margin
    from pulling the next element on top of it."""
    st.markdown(f'<div class="mdw">{html}</div>', unsafe_allow_html=True)


@contextmanager
def card(title=None, icon="", prefix="card"):
    """Bordered white box (WAVE PRO style panel)."""
    _CARD_N[0] += 1
    try:
        box = st.container(key=f"{prefix}_{_CARD_N[0]}")
    except TypeError:                       # very old Streamlit: no keyed containers
        box = st.container()
    with box:
        if title:
            md(f'<div class="card-title">{icon} {hesc(title)}</div>')
        yield


def sub(text):
    md(f'<div class="sub">{hesc(text)}</div>')


def page_title(text):
    """Page heading. Also reserves a slot for the process-flow diagram (filled at the end of the run,
    so it always shows the latest numbers). The System Design page has its own full diagram."""
    md(f'<div class="page-h">{hesc(text)}</div>')
    _FLOW_PH[0] = st.empty() if ss.get("nav_main", "").endswith("UF") else None   # flow diagram on the UF tab only


def tiles(items):
    """Small read-only boxes for automatically calculated data.
    items: (label, value) or (label, value, 'warn'|'bad'|'good')."""
    html = ['<div class="tiles">']
    for it in items:
        cls = f" {it[2]}" if len(it) > 2 else ""
        html.append(f'<div class="tile{cls}"><div class="t-l">{hesc(str(it[0]))}</div>'
                    f'<div class="t-v">{hesc(str(it[1]))}</div></div>')
    html.append("</div>")
    md("".join(html))


def _num(x):
    s = f"{x:,.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def show_df(df, **kw):
    """Read-only table as light HTML with a black grid (readable whatever the Streamlit theme)."""
    html = df.to_html(index=False, escape=True, classes="htbl", border=0, na_rep="", justify="left", float_format=_num)
    html = re.sub(r"\s*\n\s*", "", html)
    st.markdown(f'<div class="htbl-wrap">{html}</div>', unsafe_allow_html=True)


def fmt(v, d=1, unit=""):
    try:
        s = f"{float(v):,.{d}f}"
    except (TypeError, ValueError):
        s = str(v)
    return f"{s} {unit}".strip()


# =====================================================
# AUTO-SAVE ENGINE
# Every input is created through the w_* helpers (see "widget helpers" below): each value is stored
# in a permanent data key, so nothing is lost when you change tabs - no Save buttons.
# =====================================================
if "_saved" not in ss:
    ss["_saved"] = {}
SAVED = ss["_saved"]


def _is_saved_key(k):
    return isinstance(k, str) and not k.startswith(NO_SAVE_PREFIX)


def _safe_name(name):
    s = re.sub(r"[^\w\- ]+", "", str(name)).strip().replace(" ", "_")
    return s or "Project"


def _default_project_name():
    return "Project_" + datetime.now().strftime("%Y%m%d_%H%M")


def collect_project():
    data = {k: v for k, v in SAVED.items() if _is_saved_key(k)}
    for k, v in ss.items():
        if _is_saved_key(k):
            data[k] = v
    clean = {}
    for k, v in data.items():
        try:
            json.dumps(v)
            clean[k] = v
        except (TypeError, ValueError):
            pass
    return clean


def project_json():
    body = collect_project()
    body["_meta"] = {"app": APP_TITLE, "version": 3,
                     "saved_at": datetime.now().isoformat(timespec="seconds")}
    return json.dumps(body, indent=2, default=str)


def load_project_data(data, clear=True):
    if clear:
        for k in list(ss.keys()):
            if _is_saved_key(k):
                del ss[k]
        for k in [k for k in SAVED if _is_saved_key(k)]:
            del SAVED[k]
    for k, v in data.items():
        if _is_saved_key(k):
            ss[k] = v
            SAVED[k] = v


def project_path(name=None):
    n = _safe_name(name or ss.get("project_name") or _default_project_name())
    return PROJECT_DIR / n / f"{n}.uff"


def _write_last(rel):
    try:
        PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        (PROJECT_DIR / ".last_project").write_text(rel, encoding="utf-8")
    except OSError:
        pass


def save_to_disk():
    """Write to UltraPRO_Projects/<name>/<name>.uff (folder is created automatically)."""
    try:
        path = project_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(project_json(), encoding="utf-8")
        _write_last(str(path.relative_to(PROJECT_DIR)).replace("\\", "/"))
        ss["_last_path"] = str(path)
        ss["_last_saved_at"] = datetime.now().strftime("%H:%M:%S")
        ss["_disk_error"] = ""
        return path
    except OSError as e:
        ss["_disk_error"] = str(e)
        return None


@st.cache_data(show_spinner=False)
def _project_meta(path_str, mtime):
    try:
        d = json.loads(Path(path_str).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {"name": d.get("project_name", ""), "client": d.get("pi_client", ""),
            "flow": d.get("uf_feed_flow"), "modules": d.get("total_modules"),
            "vendor": d.get("uf_vendor_saved", ""), "module": d.get("selected_module", "")}


def list_projects():
    out = []
    try:
        for p in PROJECT_DIR.glob("*/*.uff"):
            mt = p.stat().st_mtime
            meta = _project_meta(str(p), mt)
            out.append({"rel": str(p.relative_to(PROJECT_DIR)).replace("\\", "/"), "mtime": mt,
                        "name": meta.get("name") or p.stem, **{k: meta.get(k) for k in
                        ("client", "flow", "modules", "vendor", "module")}})
    except OSError:
        return []
    return sorted(out, key=lambda x: x["mtime"], reverse=True)


def _ago(ts):
    s = max(0, datetime.now().timestamp() - ts)
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < 86400:
        return f"{int(s // 3600)} h ago"
    if s < 2592000:
        return f"{int(s // 86400)} days ago"
    return f"{int(s // 2592000)} months ago"


# ---- callbacks (run before the script, so they may change widget state) ----
def _cb_new():
    load_project_data({}, clear=True)
    name = _default_project_name()
    ss["project_name"] = name
    SAVED["project_name"] = name
    ss["nav_main"] = MAIN_TABS[0]
    ss["_flash"] = ("success", "New project created - it gets its own folder automatically.")


def _cb_open_path(rel):
    try:
        data = json.loads((PROJECT_DIR / rel).read_text(encoding="utf-8"))
        load_project_data(data)
        if not ss.get("project_name"):
            ss["project_name"] = SAVED["project_name"] = Path(rel).stem
        _write_last(rel)
        ss["nav_main"] = MAIN_TABS[1]
        ss["_flash"] = ("success", f"Opened project: {rel}")
    except Exception as e:
        ss["_flash"] = ("error", f"Could not open project: {e}")


def _cb_upload():
    f = ss.get("ui_upload")
    if f is None:
        return
    try:
        load_project_data(json.loads(f.getvalue().decode("utf-8")))
        if not ss.get("project_name"):
            ss["project_name"] = SAVED["project_name"] = Path(f.name).stem
        ss["nav_main"] = MAIN_TABS[1]
        ss["_flash"] = ("success", f"Loaded project file: {f.name}")
    except Exception as e:
        ss["_flash"] = ("error", f"Invalid project file: {e}")


# ---- start-up: re-open the last project, then restore saved widget values ----
if "_booted" not in ss:
    ss["_booted"] = True
    if AUTOLOAD_LAST:
        try:
            rel = (PROJECT_DIR / ".last_project").read_text(encoding="utf-8").strip()
            load_project_data(json.loads((PROJECT_DIR / rel).read_text(encoding="utf-8")), clear=False)
        except Exception:
            pass

for _k, _v in SAVED.items():
    if _k not in ss:
        ss[_k] = _v


# ---- widget helpers (use these instead of st.number_input etc.) ----
# Every value lives in a plain "data key" ss[key] (mirrored in SAVED) that is NEVER a widget key,
# so Streamlit can't clean it up when you leave a page or bring back an old default.
# The widget itself uses the key "w_<key>": it is refreshed from the data key on every run
# and writes back through on_change, which Streamlit runs before the page is re-drawn - so even a
# value typed just before clicking another tab is kept.
def _sync(key, wkey):
    ss[key] = ss[wkey]
    SAVED[key] = ss[wkey]


def _stored(key, default):
    return ss[key] if key in ss else SAVED.get(key, default)


def _prepare(key, cur):
    wkey = "w_" + key
    ss[key] = cur
    SAVED[key] = cur
    ss[wkey] = cur
    return wkey


def w_number(label, key, default=0.0, **kw):
    cur = _stored(key, default)
    is_int = isinstance(default, int) and not isinstance(default, bool)
    try:
        cur = int(cur) if is_int else float(cur)
    except (TypeError, ValueError):
        cur = default
    if kw.get("min_value") is not None:
        cur = max(cur, type(cur)(kw["min_value"]))
    if kw.get("max_value") is not None:
        cur = min(cur, type(cur)(kw["max_value"]))
    wkey = _prepare(key, cur)
    return st.number_input(label, key=wkey, on_change=_sync, args=(key, wkey), **kw)


def _w(fn, label, key, default, *pos, **kw):
    wkey = _prepare(key, _stored(key, default))
    return fn(label, *pos, key=wkey, on_change=_sync, args=(key, wkey), **kw)


def _choice(fn, label, options, key, default, **kw):
    options = list(options)
    if default is None or default not in options:
        default = options[0]
    cur = _stored(key, default)
    if cur not in options:
        cur = default
    wkey = _prepare(key, cur)
    return fn(label, options, key=wkey, on_change=_sync, args=(key, wkey), **kw)


def w_select(label, options, key, default=None, **kw):
    return _choice(st.selectbox, label, options, key, default, **kw)


def w_radio(label, options, key, default=None, **kw):
    return _choice(st.radio, label, options, key, default, **kw)


def w_check(label, key, default=False, **kw):
    return _w(st.checkbox, label, key, default, **kw)


def w_toggle(label, key, default=False, **kw):
    return _w(st.toggle, label, key, default, **kw)


def w_text(label, key, default="", **kw):
    return _w(st.text_input, label, key, default, **kw)


def w_area(label, key, default="", **kw):
    return _w(st.text_area, label, key, default, **kw)


# =====================================================
# CHEMISTRY HELPERS
# =====================================================
def _fraction(pka, ph):
    return 1 / (1 + 10 ** (pka - ph))


def borate_alkalinity(boron_mgl, ph):
    return boron_mgl * _fraction(9.24, ph) / 10.81


def silica_alkalinity(silica_mgl, ph):
    return silica_mgl * _fraction(9.8, ph) / 60.08


def ammonia_alkalinity(nh4_mgl, ph):
    return nh4_mgl * _fraction(9.25, ph) / 18.04


def calculate_alkalinity(hco3, co3, boron, silica, nh4, ph):
    carbonate_alk = hco3 * 50 / 61 + co3 * 50 / 30
    return (carbonate_alk
            + borate_alkalinity(boron, ph) * 50
            + silica_alkalinity(silica, ph) * 50
            + ammonia_alkalinity(nh4, ph) * 50)


# =====================================================
# CHEMICAL CLEANING (CEB / CIP) CALCULATIONS
# One function, compute_cleaning(), feeds the CEB page, CIP page, Backwash page, the Configuration
# recovery and the PDF report - so every page always shows the same numbers.
# =====================================================
GFD_LMH = 1.699            # 1 gfd -> L/m2/h
GPM_M3H = 0.2271           # 1 gpm -> m3/h

# strength = weight fraction, density = kg/L (None = solid / gas, reported as kg of 100 % chemical),
# eqwt = mg per meq (acids / bases).  NaOCl density 1.136 reproduces WAVE's 114.9 gal/h at 350 mg/L.
CHEMICALS = {
    "HCl(32)":          {"label": "HCl (32%)",     "strength": 0.32, "density": 1.16, "eqwt": 36.46},
    "H2SO4(98)":        {"label": "H2SO4 (98%)",   "strength": 0.98, "density": 1.84, "eqwt": 49.04},
    "NaOH(50)":         {"label": "NaOH (50%)",    "strength": 0.50, "density": 1.53, "eqwt": 40.00},
    "NaOCl(12)":        {"label": "NaOCl (12%)",   "strength": 0.12, "density": 1.136},
    "NaOCl":            {"label": "NaOCl (12%)",   "strength": 0.12, "density": 1.136},
    "Peroxide":         {"label": "H2O2 (35%)",    "strength": 0.35, "density": 1.13},
    "Chlorine Dioxide": {"label": "ClO2 (100%)",   "strength": 1.0,  "density": None},
    "Citric Acid 100":  {"label": "Citric (100%)", "strength": 1.0,  "density": None},
    "Citric Acid":      {"label": "Citric (100%)", "strength": 1.0,  "density": None},
    "Oxalic Acid 100":  {"label": "Oxalic (100%)", "strength": 1.0,  "density": None},
    "Oxalic Acid":      {"label": "Oxalic (100%)", "strength": 1.0,  "density": None},
}

# defaults of the CEB / CIP inputs (must match the widgets' defaults)
CLEAN_DEFAULTS = {
    "mineral_acid_enabled": True, "acid_type": "HCl(32)", "acid_ph": 2.0,
    "organic_acid_enabled": False, "organic_acid": "Citric Acid 100", "citric_dose": 20000.0, "oxalic_dose": 10000.0,
    "alkali_enabled": True, "alkali_ph": 12.0, "alkali_oxidant_enabled": True, "oxidant_dose": 350.0,
    "disinfection_enabled": False, "disinfection_chemical": "NaOCl", "disinfection_dose": 0.0,
    "cip_mineral_acid_enabled": True, "cip_acid_type": "HCl(32)", "cip_acid_ph": 2.0,
    "cip_organic_acid_enabled": False, "cip_organic_acid": "Citric Acid",
    "cip_citric_dose": 20000.0, "cip_oxalic_dose": 10000.0,
    "cip_alkali_enabled": True, "cip_alkali_ph": 12.0,
    "cip_oxidant_enabled": True, "cip_oxidant_type": "NaOCl(12)", "cip_oxidant_dose": 2000.0,
    "cip_temperature": 95.0, "cip_initial_bw_cycles": 2, "cip_rinse_soak_cycles": 1, "cip_rinse_bw_cycles": 1,
}


def cv(key):
    return ss.get(key, CLEAN_DEFAULTS[key])


def chem_kg(dose_mgl, vol_m3):
    """kg of 100 % chemical for a dose (mg/L = g/m3) in a water volume (m3)."""
    return dose_mgl * vol_m3 / 1000.0


def chem_gal(kg, ckey):
    c = CHEMICALS.get(ckey)
    if not c or not c.get("density"):
        return None
    return kg / c["strength"] / c["density"] / 3.78541


def amt(kg, gal, per_h=False):
    if kg is None:
        return "-"
    suf = "/h" if per_h else ""
    return f"{gal:,.1f} gal{suf}" if gal is not None else f"{kg:,.1f} kg{suf}"


def module_volume_key():
    return "module_volume_" + str(ss.get("selected_module", "default")).replace(" ", "_")


def compute_cleaning(mods_unit=None, online_units=None, total_units=None):
    """Hydraulics, CEB and CIP numbers for ONE unit (modules_per_unit modules), from the stored inputs.
    The Configuration page passes its live values; every other page uses what is stored."""
    g = ss.get
    md = g("selected_module_data", {}) or {}
    area = float(md.get("area", 77.0))
    n_online = int(online_units if online_units is not None else g("cfg_online_units", 2))
    n_total = int(total_units if total_units is not None
                  else n_online + int(g("cfg_standby_units", 0)) + int(g("cfg_redundant_units", 1)))
    if mods_unit is None:
        mods_unit = g("uf_modules_per_train") or math.ceil(g("uf_modules", 1) / max(n_online, 1))
    mods_unit = max(int(mods_unit), 1)

    # ---- one-unit hydraulics ----
    unit_area = mods_unit * area
    bw_gfd = g("uf_backwash_gfd", md.get("backwash_gfd", 58.9))
    ceb_gfd = g("uf_ceb_gfd", md.get("ceb_gfd", bw_gfd))
    ff_gpm = g("uf_forward_flush", md.get("forward_flush", 0.0))
    cip_rec = g("cip_recycle_input", md.get("cip_recycle", 6.6))
    air_mod = g("uf_air_flow", md.get("air_flow", 0.0))
    unit = {
        "modules": mods_unit, "area_m2": unit_area,
        "bw_flow": unit_area * bw_gfd * GFD_LMH / 1000,      # m3/h
        "ceb_flow": unit_area * ceb_gfd * GFD_LMH / 1000,    # m3/h  (ONE unit, not the whole system)
        "ff_flow": mods_unit * ff_gpm * GPM_M3H,
        "cip_flow": mods_unit * cip_rec * GPM_M3H,
        "air_scfm": mods_unit * air_mod,
        "online_units": n_online, "total_units": n_total,
    }

    # ---- backwash ----
    bw_top, bw_bot = float(g("bw_top_backwash", 30.0)), float(g("bw_bottom_backwash", 30.0))
    filt_min = max(float(g("uf_filtration_duration", 25.0)), 1.0)
    bw_event = unit["bw_flow"] * (bw_top + bw_bot) / 3600

    # ---- CEB durations ("same as backwash" aware) ----
    same = bool(g("ceb_same_as_backwash", False))

    def dur(ceb_key, bw_key, ceb_def, bw_def):
        return float(g(bw_key, bw_def)) if same else float(g(ceb_key, ceb_def))

    top = dur("ceb_top_bw", "bw_top_backwash", 45.0, 30.0)
    bot = dur("ceb_bottom_bw", "bw_bottom_backwash", 45.0, 30.0)
    ffs = dur("ceb_forward_flush", "bw_forward_flush", 45.0, 45.0)
    r_top, r_bot = float(g("bw_rinse_top", 0.0)), float(g("bw_rinse_bottom", 0.0))

    # water used per CEB event: chemical BW (CEB flow) + rinse (BW flow) + forward flush; soaking uses none
    chem_vol = unit["ceb_flow"] * (top + bot) / 3600
    rinse_vol = unit["bw_flow"] * (r_top + r_bot) / 3600
    ff_vol = unit["ff_flow"] * ffs / 3600
    event_vol = chem_vol + rinse_vol + ff_vol

    # ---- CEB schedule: acid CEB every uf_acid_ceb h, alkali/oxidant CEB every uf_alk_ceb h ----
    enabled = g("uf_feature", "CEB only") != "mini-CIP only"
    acid_int = max(float(g("uf_acid_ceb", 168.0)), 1.0)
    alk_int = max(float(g("uf_alk_ceb", 24.0)), 1.0)
    acid_on = bool(cv("mineral_acid_enabled") or cv("organic_acid_enabled"))
    alk_on = bool(cv("alkali_enabled") or cv("alkali_oxidant_enabled"))
    ev_hr_unit = ((1 / acid_int if acid_on else 0) + (1 / alk_int if alk_on else 0)) if enabled else 0
    ev_acid_month = n_online * 720 / acid_int if enabled else 0
    ev_alk_month = n_online * 720 / alk_int if enabled else 0

    # ---- chemical demand (alkalinity balance to the target pH) ----
    wq = {"hco3": g("hco3", 0.0), "co3": g("co3", 0.0), "co2": g("co2", 0.0), "boron": g("boron", 0.0),
          "silica": g("silica", 0.0), "ammonium": g("ammonium", 0.0)}
    feed_ph, temp = float(g("feed_ph", 7.0)), float(g("temperature", 25.0))
    # temperature of the cleaning solution (CEB page: feed temperature or its own box; CIP: recycle temperature)
    ceb_temp = temp if g("ceb_use_feed_temp", True) else (float(g("ceb_temperature", 66.0)) - 32) / 1.8
    cip_temp = (float(cv("cip_temperature")) - 32) / 1.8
    ceb_dem = chem.cleaning_demand(wq, feed_ph, float(cv("acid_ph")), float(cv("alkali_ph")), ceb_temp, temp)
    cip_dem = chem.cleaning_demand(wq, feed_ph, float(cv("cip_acid_ph")), float(cv("cip_alkali_ph")), cip_temp, temp)

    def ceb_row(step, ckey, dose, ev_month):
        kg_h, kg_ev = chem_kg(dose, unit["ceb_flow"]), chem_kg(dose, chem_vol)
        gal_h, gal_ev = chem_gal(kg_h, ckey), chem_gal(kg_ev, ckey)
        return {"step": step, "chem": CHEMICALS[ckey]["label"], "dose": dose,
                "kg_h": kg_h, "gal_h": gal_h, "kg_event": kg_ev, "gal_event": gal_ev,
                "kg_month": None if ev_month is None else kg_ev * ev_month,
                "gal_month": None if (ev_month is None or gal_ev is None) else gal_ev * ev_month}

    rows = []
    if cv("mineral_acid_enabled"):
        k = cv("acid_type")
        rows.append(ceb_row("Acid CEB", k, ceb_dem["acid_meq"] * CHEMICALS[k]["eqwt"], ev_acid_month))
    if cv("organic_acid_enabled"):
        k = cv("organic_acid")
        rows.append(ceb_row("Acid CEB (organic)", k,
                            float(cv("citric_dose") if "Citric" in k else cv("oxalic_dose")), ev_acid_month))
    if cv("alkali_enabled"):
        rows.append(ceb_row("Alkali CEB", "NaOH(50)", ceb_dem["base_meq"] * CHEMICALS["NaOH(50)"]["eqwt"], ev_alk_month))
    if cv("alkali_oxidant_enabled"):
        rows.append(ceb_row("Oxidant CEB", "NaOCl(12)", float(cv("oxidant_dose")), ev_alk_month))
    if cv("disinfection_enabled") and float(cv("disinfection_dose")) > 0:
        rows.append(ceb_row("Disinfection CEB", cv("disinfection_chemical"), float(cv("disinfection_dose")), None))

    ceb = {"enabled": enabled, "rows": rows, "demand": ceb_dem, "temp_c": ceb_temp, "chem_vol": chem_vol, "rinse_vol": rinse_vol,
           "ff_vol": ff_vol, "event_vol": event_vol, "events_hr_unit": ev_hr_unit,
           "loss_per_hr": n_online * event_vol * ev_hr_unit, "ff_loss_hr": n_online * ff_vol * ev_hr_unit,
           "soak_min": float(g("chemical_soak", 10.0)),
           "acid_interval": acid_int, "alk_interval": alk_int}

    # ---- CIP (one unit) ----
    module_vol = float(g(module_volume_key(), area * 0.688))     # L/module; 0.688 L/m2 reproduces WAVE's 616 gal
    tank_factor = float(g("cip_tank_factor", 200.0)) / 100
    tank_l = mods_unit * module_vol * tank_factor
    tank_m3 = tank_l / 1000
    acid_step = bool(cv("cip_mineral_acid_enabled") or cv("cip_organic_acid_enabled"))
    alk_step = bool(cv("cip_alkali_enabled") or cv("cip_oxidant_enabled"))
    steps = int(acid_step) + int(alk_step)
    bw_cycles = int(cv("cip_initial_bw_cycles")) + int(cv("cip_rinse_bw_cycles"))
    d_t = max(0.0, (float(cv("cip_temperature")) - 32) / 1.8 - temp)
    interval_d = max(float(g("uf_cip_interval", 30.0)), 1.0)
    ev_month = 30 / interval_d * n_total          # every unit is cleaned once per interval

    def cip_row(step, ckey, dose):
        kg = chem_kg(dose, tank_m3)
        gal = chem_gal(kg, ckey)
        return {"step": step, "chem": CHEMICALS[ckey]["label"], "dose": dose, "kg_event": kg, "gal_event": gal,
                "kg_month": kg * ev_month, "gal_month": None if gal is None else gal * ev_month}

    crow = []
    if cv("cip_mineral_acid_enabled"):
        k = cv("cip_acid_type")
        crow.append(cip_row("Acid CIP", k, cip_dem["acid_meq"] * CHEMICALS[k]["eqwt"]))
    if cv("cip_organic_acid_enabled"):
        k = cv("cip_organic_acid")
        crow.append(cip_row("Acid CIP (organic)", k,
                            float(cv("cip_citric_dose") if "Citric" in k else cv("cip_oxalic_dose"))))
    if cv("cip_alkali_enabled"):
        crow.append(cip_row("Alkali CIP", "NaOH(50)", cip_dem["base_meq"] * CHEMICALS["NaOH(50)"]["eqwt"]))
    if cv("cip_oxidant_enabled"):
        crow.append(cip_row("Oxidant CIP", cv("cip_oxidant_type"), float(cv("cip_oxidant_dose"))))

    cip = {"temp_c": cip_temp, "module_vol": module_vol, "tank_l": tank_l, "tank_gal": tank_l / 3.78541, "tank_factor": tank_factor,
           "steps": steps, "solution_vol": tank_m3 * steps, "bw_vol": bw_cycles * bw_event,
           "turnover_min": tank_m3 / unit["cip_flow"] * 60 if unit["cip_flow"] > 0 else 0.0,
           "d_t": d_t, "heater_kwh": tank_l * d_t * 4.186 / 3600 * steps,
           "events_month": ev_month, "rows": crow, "demand": cip_dem}

    # ---- unit availability: share of time a unit is actually filtering ----
    # A unit filters for `filt_min`, then spends t_bw in the backwash sequence; every CEB takes it offline for t_ceb.
    #   A = (1 - CEBs per hour x t_ceb) / (1 + t_bw / filtration time)
    valve = float(g("valve_open_close", 5.0))
    wait = float(g("typical_wait", 0.0))
    ramp = float(g("pump_ramp", 0.0))
    air_off = bool(md) and md.get("verified", True) and md.get("air_flow", 1) == 0
    ff_off = bool(md) and md.get("verified", True) and md.get("forward_flush", 1) == 0
    between = max(float(g("bw_between_air_scour", 1)), 1.0)

    def seq_s(steps):
        """Sequence time (s): every active step adds valve / wait time, pumped steps add the pump ramp."""
        total = 0.0
        for sec, pumped in steps:
            if sec > 0:
                total += sec + valve + wait + (ramp if pumped else 0.0)
        return total

    bw_ff_s = 0.0 if ff_off else float(g("bw_forward_flush", 45.0))
    bw_air_s = 0.0 if air_off else float(g("bw_air_scour", 20.0)) / between
    t_bw = seq_s([(float(g("bw_filtrate_to_level", 0.0)), True), (bw_bot, True), (bw_top, True),
                  (bw_air_s, False), (bw_ff_s, True), (float(g("bw_drain", 30.0)), False),
                  (float(g("bw_lumen_fill", 0.0)), True)])
    ceb_ff_s = 0.0 if ff_off else ffs
    ceb_air_s = 0.0 if air_off else dur("ceb_air_scour", "bw_air_scour", 20.0, 20.0)
    t_ceb = seq_s([(ceb_air_s, False), (dur("ceb_drain", "bw_drain", 30.0, 30.0), False), (top, True), (bot, True),
                   (ceb_ff_s, True), (float(g("chemical_soak", 10.0)) * 60, False), (r_top, True), (r_bot, True)])
    avail = (1 - ev_hr_unit * t_ceb / 3600) / (1 + t_bw / (filt_min * 60))
    avail = min(max(avail, 0.05), 1.0)
    cycles_hr = avail * 60 / filt_min                         # backwash cycles per hour, per online unit
    ff_per_module = float(ff_gpm) * GPM_M3H * (bw_ff_s / 3600 * cycles_hr + ceb_ff_s / 3600 * ev_hr_unit)

    bw = {"event_vol": bw_event, "cycles_hr": cycles_hr, "loss_hr": n_online * bw_event * cycles_hr,
          "ff_loss_hr": n_online * unit["ff_flow"] * bw_ff_s / 3600 * cycles_hr}
    av = {"A": avail, "t_bw_s": t_bw, "t_ceb_s": t_ceb, "cycles_hr": cycles_hr, "ff_per_module": ff_per_module}

    return {"unit": unit, "bw": bw, "ceb": ceb, "cip": cip, "avail": av}


def flux_model(feed_m3h, online_modules, area_m2, cl):
    """Average gross filtrate and the flux while the units are filtering (what WAVE calls operating flux)."""
    av = cl["avail"]
    strainer = feed_m3h * (1 - float(ss.get("strainer_recovery", 100.0)) / 100)
    gross = max(feed_m3h - strainer - av["ff_per_module"] * online_modules, 0.0)       # m3/h
    area_ft2 = online_modules * area_m2 * 10.764
    op = gross * 4.4029 * 1440 / (av["A"] * area_ft2) if area_ft2 > 0 else 0.0           # gfd while filtering
    return {"gross": gross, "strainer": strainer, "A": av["A"], "op_flux_gfd": op, "area_ft2": area_ft2}


def required_modules_exact(feed_m3h, flux_gfd, area_m2, cl):
    """Online modules needed so that the flux while filtering equals the design flux."""
    av = cl["avail"]
    strainer = feed_m3h * (1 - float(ss.get("strainer_recovery", 100.0)) / 100)
    per_module = av["A"] * flux_gfd * GFD_LMH / 1000 * area_m2          # m3/h of gross filtrate per online module
    denom = per_module + av["ff_per_module"]
    return (feed_m3h - strainer) / denom if denom > 0 else 0.0


# =====================================================
# DESIGN CHECK  (is the selected module / number of units & trains big enough?)
# =====================================================
def design_check(live=None):
    """Compare the selected configuration with the design basis.
    `live` can override stored values (the Design / Configuration pages pass what they just calculated)."""
    live = live or {}

    def g(key, default=None):
        return live[key] if key in live else ss.get(key, default)

    md = ss.get("selected_module_data", {}) or {}
    area = float(md.get("area", 77.0))
    feed = float(g("uf_feed_flow", 0) or 0)
    d_flux = float(g("uf_flux_gfd", 0) or 0)                  # design flux, gfd (Design page)
    req = int(g("uf_modules", 0) or 0)                        # modules required at the design flux
    on_mod = int(g("online_modules", 0) or 0)                 # online modules in the configuration
    n_on, n_sb, n_red = (int(g(k, 0) or 0) for k in ("cfg_online_units", "cfg_standby_units", "cfg_redundant_units"))
    t_on, t_sb = max(int(g("trains_online", 1) or 1), 1), int(g("standby_trains", 0) or 0)
    rec, rec_t = g("uf_recovery_calc"), float(g("uf_recovery_input", g("uf_recovery", 95.0)) or 0)

    if on_mod <= 0 or req <= 0 or d_flux <= 0 or feed <= 0:
        return {"status": "info", "checks": [], "tiles": [],
                "summary": "Complete the Design and Configuration sections to see whether the selected size is "
                           "enough for the feed flow and design flux."}

    fm = flux_model(feed, on_mod, area, compute_cleaning())
    A, gross = fm["A"], fm["gross"]
    op_flux = fm["op_flux_gfd"]                                       # gfd while the units are filtering
    cap = A * on_mod * area * d_flux * GFD_LMH / 1000                 # average gross filtrate at the design flux
    margin = (cap / gross - 1) * 100 if gross > 0 else 0.0
    per_unit = on_mod // max(n_on, 1)

    checks = []

    def add(level, text):
        checks.append({"level": level, "text": text})

    # ---- size verdict: flow & flux ----
    if op_flux <= d_flux * 1.0005:
        add("ok", f"Flux: operating flux while filtering {op_flux:.1f} gfd is within the design flux of {d_flux:.1f} gfd.")
        add("ok", f"Flow: at the design flux ({A * 100:.0f}% filtering time) the online modules give {cap:.1f} m³/hr, "
                  f"enough for the {gross:.1f} m³/hr gross filtrate needed ({margin:+.0f}% margin).")
    else:
        add("bad", f"Flux: operating flux while filtering {op_flux:.1f} gfd is ABOVE the design flux of {d_flux:.1f} gfd "
                   f"({(op_flux / d_flux - 1) * 100:.0f}% too high).")
        add("bad", f"Flow: at the design flux ({A * 100:.0f}% filtering time) the online modules only give {cap:.1f} m³/hr, "
                   f"less than the {gross:.1f} m³/hr gross filtrate needed ({margin:.0f}%).")
    if on_mod >= req:
        add("ok", f"Modules: {on_mod} online modules ≥ {req} required.")
    else:
        add("bad", f"Modules: only {on_mod} online modules, {req} are required (short by {req - on_mod}). "
                   f"Add modules per unit or more units.")
    if margin > 30:
        add("info", f"Over-sized: capacity is {margin:.0f}% above the required flow and operating flux is only "
                    f"{op_flux / d_flux * 100:.0f}% of the design flux. Fewer modules may be enough.")

    # ---- units: production while a unit is in BW / CEB / CIP ----
    if n_red + n_sb >= 1:
        add("ok", "Units: a standby / redundant unit covers a unit that is offline for BW / CEB / CIP.")
    elif n_on >= 2:
        f_n1 = op_flux * n_on / (n_on - 1)
        if f_n1 > d_flux * 1.0005:
            add("warn", f"Units: with no redundant unit, flux rises to {f_n1:.1f} gfd while one unit is offline "
                        f"for BW / CEB / CIP (design {d_flux:.1f} gfd). Add a redundant unit.")
        else:
            add("ok", f"Units: flux stays at {f_n1:.1f} gfd (within design) while one unit is offline.")
    else:
        add("warn", "Units: a single online unit and no redundant unit - production stops during BW / CEB / CIP.")

    # ---- trains ----
    if n_on % t_on != 0:
        add("warn", f"Trains: {n_on} online units cannot be split evenly across {t_on} operating trains.")
    else:
        add("ok", f"Trains: {t_on} operating train{'s' if t_on != 1 else ''} × {n_on // t_on} unit"
                  f"{'s' if n_on // t_on != 1 else ''} ({on_mod // t_on} modules, {feed / t_on:.1f} m³/hr each)"
                  f"{'' if t_sb else '; no standby train'}.")

    # ---- module ----
    mflux = md.get("flux_gfd")
    if isinstance(mflux, (int, float)) and mflux > 0 and d_flux > mflux * 1.2:
        add("warn", f"Module: design flux {d_flux:.1f} gfd is {(d_flux / mflux - 1) * 100:.0f}% above the "
                    f"{ss.get('selected_module', 'selected module')} default of {mflux:.0f} gfd - confirm with the vendor.")
    if md and md.get("verified", True) is False:
        add("warn", f"Module: data for {ss.get('selected_module', 'this module')} is generic - verify rack size and "
                    f"flows with the vendor datasheet.")

    # ---- recovery (from the Configuration page) ----
    if rec:
        if float(rec) + 1e-9 >= rec_t:
            add("ok", f"Recovery: {float(rec):.1f}% meets the target of {rec_t:.1f}%.")
        else:
            add("warn", f"Recovery: {float(rec):.1f}% is below the target of {rec_t:.1f}%. Shorten backwash / CEB "
                        f"water use or lower the target.")

    levels = [c["level"] for c in checks]
    size_bad = any(c["level"] == "bad" for c in checks)
    status = "bad" if size_bad else ("warn" if "warn" in levels else "ok")
    detail = f"{on_mod} online modules ({n_on} unit{'s' if n_on != 1 else ''} × {per_unit}), operating flux " \
             f"{op_flux:.1f} gfd vs design {d_flux:.1f} gfd, capacity {cap:.1f} vs {gross:.1f} m³/hr"
    if size_bad:
        summary = f"Selected size is TOO SMALL: {detail}. {max(req - on_mod, 0)} more online module(s) needed."
    elif status == "warn":
        warns = "; ".join(c["text"].split(": ", 1)[0] for c in checks if c["level"] == "warn")
        summary = f"Selected size meets the required flow and flux ({detail}), but check: {warns}."
    else:
        summary = f"Selected size OK: {detail}."

    cls = "good" if not size_bad else "bad"
    tiles_ = [("Required modules", req), ("Online modules", f"{on_mod} ({n_on} × {per_unit})", cls),
              ("Design flux", f"{d_flux:.1f} gfd"), ("Operating flux", f"{op_flux:.1f} gfd", cls),
              ("Gross filtrate: capacity / needed", f"{cap:.1f} / {gross:.1f} m³/hr"), ("Margin", f"{margin:+.0f} %", cls),
              ("Filtering time", f"{A * 100:.1f} %")]
    return {"status": status, "summary": summary, "checks": checks, "tiles": tiles_}


def render_design_check(res):
    """Banner + checklist card, and a pop-up (toast) whenever the verdict changes."""
    icons = {"ok": "✅", "warn": "⚠️", "bad": "❌", "info": "ℹ️"}
    box = {"ok": st.success, "warn": st.warning, "bad": st.error, "info": st.info}[res["status"]]
    ok_rows = [c for c in res["checks"] if c["level"] == "ok"]
    caution_rows = sorted((c for c in res["checks"] if c["level"] != "ok"),
                          key=lambda c: {"info": 0, "warn": 1, "bad": 2}.get(c["level"], 0))
    if res["checks"]:
        # 1) selection: tiles + the checks that passed
        with card("Design Check - selected module, units & trains", "🧭"):
            tiles(res["tiles"])
            md("".join(f'<div class="chk {c["level"]}">{icons[c["level"]]} {hesc(c["text"])}</div>'
                       for c in ok_rows))
    # 2) below it: all cautions / warnings
    box(f"{icons[res['status']]} {res['summary']}")
    if caution_rows:
        md("".join(f'<div class="chk {c["level"]}">{icons[c["level"]]} {hesc(c["text"])}</div>'
                   for c in caution_rows))
    if res["status"] != "info":
        sig = (res["status"], res["summary"])
        if ss.get("_chk_sig") != sig:
            ss["_chk_sig"] = sig
            try:
                st.toast(res["summary"], icon=icons[res["status"]])
            except Exception:
                pass


def _toc_removal():
    """TOC removed by UF: the TOC Rejection set under Additional Settings, 20 % if it is left at 0."""
    r = float(ss.get("TOC_rejection", 0) or 0)
    return min(r, 100.0) / 100 if r > 0 else 0.20


def compute_permeate():
    """Feed vs UF permeate quality (also stores ufp_* values for Report / PDF)."""
    g = ss.get
    feed = {
        "Calcium": g("ca", 0.0), "Magnesium": g("mg", 0.0), "Sodium": g("na", 0.0),
        "Potassium": g("k", 0.0), "Bicarbonate": g("hco3", 0.0), "Carbonate": g("co3", 0.0),
        "Sulfate": g("so4", 0.0), "Chloride": g("cl", 0.0), "Nitrate": g("no3", 0.0),
        "Silica": g("silica", 0.0), "Boron": g("boron", 0.0),
        "TDS": g("calculated_tds", 0.0), "Hardness": g("hardness", 0.0),
        "Conductivity": g("conductivity", 0.0), "Turbidity": g("Turbidity", 0.0),
        "TSS": g("TSS", 0.0), "TOC": g("TOC", 0.0), "SDI": g("sdi", 0.0),
        "pH": g("feed_ph", 7.0),
    }
    permeate = dict(feed)                       # dissolved species pass through UF
    permeate["Turbidity"] = feed["Turbidity"] * 0.01
    permeate["TSS"] = feed["TSS"] * 0.01
    permeate["TOC"] = feed["TOC"] * (1 - _toc_removal())
    permeate["SDI"] = min(feed["SDI"], 2.0)

    ss["ufp_tds"] = permeate["TDS"]
    ss["ufp_hardness"] = permeate["Hardness"]
    ss["ufp_conductivity"] = permeate["Conductivity"]
    ss["ufp_turbidity"] = permeate["Turbidity"]
    ss["ufp_tss"] = permeate["TSS"]
    ss["ufp_toc"] = permeate["TOC"]
    ss["ufp_sdi"] = permeate["SDI"]
    ss["ufp_ph"] = permeate["pH"]
    return feed, permeate


# ---- treated water after UF (effluent) ----
TW_IONS = [("Calcium (Ca)", "ca"), ("Magnesium (Mg)", "mg"), ("Sodium (Na)", "na"), ("Potassium (K)", "k"),
           ("Ammonium (NH4)", "ammonium"), ("Barium (Ba)", "ba"), ("Strontium (Sr)", "sr"),
           ("Bicarbonate (HCO3)", "hco3"), ("Carbonate (CO3)", "co3"), ("Sulphate (SO4)", "so4"),
           ("Chloride (Cl)", "cl"), ("Nitrate (NO3)", "no3"), ("Fluoride (F)", "fluoride"),
           ("Silica (SiO2)", "silica"), ("Boron (B)", "boron"), ("Iron (Fe)", "iron"),
           ("Manganese (Mn)", "manganese"), ("Free CO2", "co2")]


def treated_water():
    """Treated water after UF: flows, feed vs UF-permeate tables and checks against typical RO-feed limits.
    Dissolved species pass through UF unchanged; turbidity / TSS are 99 % removed, TOC by the TOC rejection
    (20 % if not set), and SDI15 is limited to 2.0."""
    g = ss.get
    feed, perm = compute_permeate()

    def row(label, unit, f, p, show_rem=True):
        f, p = float(f or 0), float(p or 0)
        return {"param": label, "unit": unit, "feed": f, "perm": p,
                "rem": (1 - p / f) * 100 if (show_rem and f > 0) else None}

    temp = g("temperature", 25.0)
    quality = [row("pH", "-", feed["pH"], perm["pH"], False), row("Temperature", "°C", temp, temp, False),
               row("TDS", "mg/L", feed["TDS"], perm["TDS"]), row("Hardness", "mg/L as CaCO3", feed["Hardness"], perm["Hardness"]),
               row("Alkalinity", "mg/L as CaCO3", g("alkalinity", 0.0), g("alkalinity", 0.0)),
               row("Conductivity", "µS/cm", feed["Conductivity"], perm["Conductivity"]),
               row("Turbidity", "NTU", feed["Turbidity"], perm["Turbidity"]), row("TSS", "mg/L", feed["TSS"], perm["TSS"]),
               row("TOC", "mg/L", feed["TOC"], perm["TOC"]), row("SDI15", "-", feed["SDI"], perm["SDI"], False)]
    ions = [r for r in (row(label, "mg/L", g(key, 0.0), g(key, 0.0)) for label, key in TW_IONS) if r["feed"] > 0]

    feed_flow = float(g("uf_feed_flow", 0) or 0)
    rec = float(g("uf_recovery_calc", g("uf_recovery", 95.0)) or 0)
    net = feed_flow * rec / 100

    checks = []
    if perm["Turbidity"] <= 0.1:
        checks.append(("ok", f"Turbidity {perm['Turbidity']:.3f} NTU is within the typical UF filtrate / RO feed limit of 0.1 NTU."))
    else:
        checks.append(("warn", f"Turbidity {perm['Turbidity']:.3f} NTU is above the typical limit of 0.1 NTU - check pretreatment and the fibre integrity."))
    if feed["SDI"] <= 0:
        checks.append(("info", "SDI15 was not entered on the Feed page - enter it to check the SDI of the UF permeate."))
    elif perm["SDI"] <= 3:
        checks.append(("ok", f"SDI15 {perm['SDI']:.1f} is within the typical RO feed limit of 3."))
    else:
        checks.append(("warn", f"SDI15 {perm['SDI']:.1f} is above the typical RO feed limit of 3."))
    for name, key in (("Iron", "iron"), ("Manganese", "manganese")):
        v = float(g(key, 0) or 0)
        if v > 0.05:
            checks.append(("warn", f"{name} {v:.3f} mg/L is above the typical RO feed limit of 0.05 mg/L - oxidise and filter before RO."))
        elif v > 0:
            checks.append(("ok", f"{name} {v:.3f} mg/L is within the typical RO feed limit of 0.05 mg/L."))
    if feed["TOC"] > 0:
        checks.append(("info", f"TOC {feed['TOC']:.2f} to {perm['TOC']:.2f} mg/L ({_toc_removal() * 100:.0f} % removal assumed)."))
    return {"feed_flow": feed_flow, "net": net, "waste": feed_flow - net, "recovery": rec,
            "quality": quality, "ions": ions, "checks": checks}


def tw_dataframe(rows):
    return pd.DataFrame([{"Parameter": r["param"], "Unit": r["unit"], "Feed": round(r["feed"], 3),
                          "UF permeate": round(r["perm"], 3),
                          "Removal (%)": "-" if r["rem"] is None else f"{r['rem']:.1f}"} for r in rows])


def render_treated_water():
    tw = treated_water()
    q = {r["param"]: r for r in tw["quality"]}
    icons = {"ok": "✅", "warn": "⚠️", "info": "ℹ️"}
    t_cls = "good" if q["Turbidity"]["perm"] <= 0.1 else "warn"
    s_cls = "" if q["SDI15"]["feed"] <= 0 else ("good" if q["SDI15"]["perm"] <= 3 else "warn")
    with card("Effluent - Treated Water after UF", "💧"):
        sub("Effluent flows")
        tiles([("Feed flow", f"{tw['feed_flow']:.1f} m³/hr"), ("Treated water (net UF permeate)", f"{tw['net']:.1f} m³/hr"),
               ("UF waste (strainer + BW + FF + CEB)", f"{tw['waste']:.1f} m³/hr"), ("UF recovery", f"{tw['recovery']:.1f} %")])
        sub("Effluent quality")
        tiles([("pH", f"{q['pH']['perm']:.2f}"), ("TDS", f"{q['TDS']['perm']:.1f} mg/L"),
               ("Conductivity", f"{q['Conductivity']['perm']:.0f} µS/cm"),
               ("Hardness", f"{q['Hardness']['perm']:.1f} mg/L CaCO3"), ("Alkalinity", f"{q['Alkalinity']['perm']:.1f} mg/L CaCO3"),
               ("Turbidity", f"{q['Turbidity']['perm']:.3f} NTU", t_cls), ("TSS", f"{q['TSS']['perm']:.3f} mg/L"),
               ("TOC", f"{q['TOC']['perm']:.2f} mg/L"),
               ("SDI15", f"{q['SDI15']['perm']:.1f}", s_cls) if s_cls else ("SDI15", f"{q['SDI15']['perm']:.1f}")])
        sub("Check against typical RO feed guidelines")
        md("".join(f'<div class="chk {lv}">{icons[lv]} {hesc(tx)}</div>' for lv, tx in tw["checks"]))
        sub("Effluent - feed vs UF permeate - water quality & particulates")
        show_df(tw_dataframe(tw["quality"]), hide_index=True)
        sub("Effluent - feed vs UF permeate - dissolved species")
        if tw["ions"]:
            show_df(tw_dataframe(tw["ions"]), hide_index=True)
        else:
            st.info("Enter the feed water analysis on the Feed page to see the dissolved species.")
        st.caption("Dissolved ions pass through UF unchanged. Assumed removal: turbidity and TSS 99 %, TOC 20 % (or the TOC "
                   "Rejection set under Additional Settings), SDI15 limited to 2.0. Iron and manganese are treated as "
                   "dissolved; particulate / oxidised Fe and Mn would be removed by UF. Limits shown are typical RO feed "
                   "guidelines - confirm with the RO membrane vendor.")


# =====================================================
# PDF REPORT
# =====================================================
NAVY = colors.HexColor("#0B2545")
BLUE = colors.HexColor("#134074")
LIGHT = colors.HexColor("#EEF3F9")
GRID = colors.HexColor("#C9D4E3")


def build_pdf_report():
    g = ss.get
    feed, perm = compute_permeate()
    project = g("project_name", "UltraPRO Project")
    now = datetime.now().strftime("%d %b %Y  %H:%M")
    mod = g("selected_module_data", {}) or {}
    cl = compute_cleaning()
    dc = design_check()
    dc_txt = dc["summary"].replace("³", "3").replace("×", "x").replace("≥", ">=")
    s_cell = ParagraphStyle("cell", parent=getSampleStyleSheet()["Normal"], fontSize=8.5, leading=10.5)

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("t", parent=styles["Title"], textColor=NAVY, fontSize=22, alignment=0, spaceAfter=2)
    s_sub = ParagraphStyle("s", parent=styles["Normal"], textColor=colors.grey, fontSize=10)
    s_h = ParagraphStyle("h", parent=styles["Heading2"], textColor=BLUE, fontSize=13, spaceBefore=12, spaceAfter=5)

    def tbl(rows, header=None, widths=None):
        data = ([header] if header else []) + rows
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                 ("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        start = 0
        if header:
            start = 1
            style += [("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        for i in range(start, len(data)):
            if (i - start) % 2 == 1:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
        t.setStyle(TableStyle(style))
        return t

    W = 174 * mm
    kv_w = [W * 0.45, W * 0.55]
    story = [Paragraph(f"{APP_TITLE} - Report", s_title),
             Paragraph(f"{escape(str(project))}  |  {now}", s_sub), Spacer(1, 6)]

    def section(title, rows, header=None, widths=None):
        story.append(Paragraph(title, s_h))
        story.append(tbl(rows, header, widths or kv_w))

    section("1. Project &amp; Module", [
        ["Project", str(project)], ["Project / case number", g("pi_number", "")],
        ["Client", g("pi_client", "")], ["Location", g("pi_location", "")],
        ["Prepared by", g("pi_engineer", "")], ["Application", g("pi_application", "")],
        ["Vendor", g("uf_vendor_saved", "")], ["UF module", g("selected_module", "")],
        ["Membrane area / module", fmt(mod.get("area", ""), 1, "m2")],
        ["Mounting / orientation", f"{mod.get('mounting', '')} / {mod.get('orientation', '')}"],
        ["Material / mode", f"{mod.get('material', '')} / {mod.get('mode', '')}"],
    ])

    ions = [("Calcium (Ca)", "ca"), ("Magnesium (Mg)", "mg"), ("Sodium (Na)", "na"), ("Potassium (K)", "k"),
            ("Barium (Ba)", "ba"), ("Strontium (Sr)", "sr"), ("Bicarbonate (HCO3)", "hco3"),
            ("Carbonate (CO3)", "co3"), ("Sulphate (SO4)", "so4"), ("Chloride (Cl)", "cl"),
            ("Nitrate (NO3)", "no3"), ("Fluoride (F)", "fluoride"), ("Silica (SiO2)", "silica"),
            ("Boron (B)", "boron"), ("Iron (Fe)", "iron"), ("Manganese (Mn)", "manganese"),
            ("Ammonium (NH4)", "ammonium"), ("Free CO2", "co2")]
    rows = []
    for i in range(0, len(ions), 2):
        a, b = ions[i], ions[i + 1]
        rows.append([a[0], fmt(g(a[1], 0), 2), b[0], fmt(g(b[1], 0), 2)])
    section("2. Feed Water Analysis (mg/L)", rows, ["Species", "mg/L", "Species", "mg/L"],
            [W * 0.30, W * 0.20, W * 0.30, W * 0.20])
    section("Feed Water Parameters", [
        ["Water type", g("water_type", "")], ["pH", fmt(g("feed_ph", 7), 2)],
        ["Charge balance error", fmt(g("charge_balance_pct", 0), 2, "%")],
        ["Temperature", fmt(g("temperature", 25), 1, "C")], ["TDS", fmt(g("calculated_tds", 0), 1, "mg/L")],
        ["Hardness", fmt(g("hardness", 0), 1, "mg/L as CaCO3")],
        ["Alkalinity", fmt(g("alkalinity", 0), 1, "mg/L as CaCO3")],
        ["Conductivity", fmt(g("conductivity", 0), 1, "uS/cm")],
        ["Turbidity / TSS / TOC / SDI",
         f"{fmt(g('Turbidity', 0), 2)} NTU / {fmt(g('TSS', 0), 2)} mg/L / {fmt(g('TOC', 0), 2)} mg/L / {fmt(g('sdi', 0), 2)}"],
    ])

    tw = treated_water()
    a = lambda x: str(x).replace("µ", "u").replace("°C", "C")
    story.append(Paragraph("3. Effluent - Treated Water after UF (UF Permeate)", s_h))
    story.append(tbl([["Feed flow", fmt(tw["feed_flow"], 1, "m3/hr")],
                      ["Effluent: treated water flow (net UF permeate)", fmt(tw["net"], 1, "m3/hr")],
                      ["UF waste flow (strainer + BW + FF + CEB)", fmt(tw["waste"], 1, "m3/hr")],
                      ["UF recovery", fmt(tw["recovery"], 1, "%")]], None, kv_w))
    wq = [W * 0.30, W * 0.20, W * 0.16, W * 0.18, W * 0.16]
    tw_head = ["Parameter", "Unit", "Feed", "UF permeate", "Removal %"]

    def tw_rows(rows):
        return [[r["param"], a(r["unit"]), fmt(r["feed"], 3), fmt(r["perm"], 3),
                 "-" if r["rem"] is None else fmt(r["rem"], 1)] for r in rows]

    story.append(Spacer(1, 6))
    story.append(tbl(tw_rows(tw["quality"]), tw_head, wq))
    if tw["ions"]:
        story.append(Spacer(1, 6))
        story.append(tbl(tw_rows(tw["ions"]), tw_head, wq))
    story.append(Spacer(1, 6))
    icon_ = {"ok": "OK", "warn": "WARNING", "info": "NOTE"}
    story.append(tbl([[icon_[lv], Paragraph(escape(a(tx)), s_cell)] for lv, tx in tw["checks"]],
                     ["Result", "Check against typical RO feed guidelines"], [W * 0.14, W * 0.86]))
    story.append(Paragraph("Dissolved ions pass through UF unchanged. Assumed removal: turbidity and TSS 99 %, TOC 20 % "
                           "(or the TOC Rejection in Additional Settings), SDI15 limited to 2.0.", s_cell))
    section("4. UF Design Basis", [
        ["Feed flow", fmt(g("uf_feed_flow", 0), 1, "m3/hr")],
        ["Filtrate flux", f"{fmt(g('uf_flux_gfd', 0), 1)} gfd"],
        ["Backwash flux", f"{fmt(g('uf_backwash_gfd', 0), 1)} gfd"],
        ["CEB flux / flow per unit", f"{fmt(g('uf_ceb_gfd', 0), 1)} gfd / {fmt(cl['unit']['ceb_flow'], 1)} m3/hr"],
        ["Required membrane area", fmt(g("uf_required_area", 0), 0, "m2")],
        ["Required modules (design)", fmt(g("uf_modules", 0), 0)],
        ["Special features", g("uf_feature", "")],
        ["Filtration duration", fmt(g("uf_filtration_duration", 0), 0, "min")],
        ["Acid CEB / Alkali CEB / CIP interval",
         f"{fmt(g('uf_acid_ceb', 0), 0)} hr / {fmt(g('uf_alk_ceb', 0), 0)} hr / {fmt(g('uf_cip_interval', 0), 0)} days"],
    ])

    section("5. System Configuration", [
        ["Online / standby / redundant units",
         f"{g('cfg_online_units', 0)} / {g('cfg_standby_units', 0)} / {g('cfg_redundant_units', 0)}"],
        ["Racks (or platforms) per unit", g("cfg_racks_per_unit", 0)],
        ["Modules per rack", g("cfg_modules_per_rack", 0)],
        ["Total modules", g("total_modules", 0)], ["Online modules", g("online_modules", 0)],
        ["Operating flux (while filtering)", fmt(g("operating_flux_gfd", 0), 1, "gfd")],
        ["Unit filtering time (BW / CEB downtime)", fmt(cl["avail"]["A"] * 100, 1, "%")],
        ["UF recovery", fmt(g("uf_recovery_calc", 0), 1, "%")],
        ["Backwash flow (per unit)", fmt(g("uf_backwash_flow", 0), 1, "m3/hr")],
        ["CIP flow (per unit)", fmt(g("uf_cip_flow", 0), 1, "m3/hr")],
        ["Operating / standby trains", f"{g('trains_online', 0)} / {g('standby_trains', 0)}"],
        ["Design check", Paragraph(escape(dc_txt), s_cell)],
    ])

    section("6. Backwash Protocol (seconds)", [
        ["Filtrate to level", g("bw_filtrate_to_level", 0)], ["Bottom backwash", g("bw_bottom_backwash", 0)],
        ["Top backwash", g("bw_top_backwash", 0)], ["Air scour", g("bw_air_scour", 0)],
        ["Forward flush", g("bw_forward_flush", 0)], ["Drain", g("bw_drain", 0)],
        ["Backwashes between air scour", g("bw_between_air_scour", 1)],
    ])

    ceb, cip_, unit = cl["ceb"], cl["cip"], cl["unit"]

    section("7. CEB Chemical Consumption (one unit cleaned at a time)", [
        ["CEB flow per unit", f"{fmt(unit['ceb_flow'], 1)} m3/hr ({fmt(unit['ceb_flow'] * 4.4029, 0)} gpm)"],
        ["Water per CEB event", fmt(ceb["event_vol"], 2, "m3")],
        ["CEB water loss (all online units)", fmt(ceb["loss_per_hr"], 2, "m3/hr")],
        ["Acid CEB / alkali CEB interval", f"{fmt(ceb['acid_interval'], 0)} h / {fmt(ceb['alk_interval'], 0)} h"],
    ])
    if ceb["rows"]:
        story.append(Spacer(1, 6))
        story.append(tbl([[r["step"], r["chem"], fmt(r["dose"], 0), amt(r["kg_h"], r["gal_h"], True),
                           amt(r["kg_event"], r["gal_event"]), amt(r["kg_month"], r["gal_month"])]
                          for r in ceb["rows"]],
                         ["Step", "Chemical", "Dose mg/L", "Feed rate", "Per CEB", "Per month"],
                         [W * 0.20, W * 0.18, W * 0.13, W * 0.17, W * 0.16, W * 0.16]))

    def on(flag, txt):
        return txt if cv(flag) else "Off"

    section("8. CIP Settings & Consumption (one unit cleaned at a time)", [
        ["Recycle temperature", fmt(cv("cip_temperature"), 0, "F")],
        ["Cycles: initial BW / rinse-soak / rinse BW",
         f"{cv('cip_initial_bw_cycles')} / {cv('cip_rinse_soak_cycles')} / {cv('cip_rinse_bw_cycles')}"],
        ["Mineral acid", on("cip_mineral_acid_enabled", f"{cv('cip_acid_type')} to pH {cv('cip_acid_ph')}")],
        ["Alkali", on("cip_alkali_enabled", f"NaOH(50) to pH {cv('cip_alkali_ph')}")],
        ["Oxidant", on("cip_oxidant_enabled", f"{cv('cip_oxidant_type')} {cv('cip_oxidant_dose')} mg/L")],
        ["CIP water source", g("cip_water_source", "")],
        ["CIP tank volume", f"{fmt(cip_['tank_gal'], 0)} gal ({fmt(cip_['tank_l'], 0)} L)"],
        ["CIP flow per unit / tank turnover",
         f"{fmt(unit['cip_flow'], 1)} m3/hr / {fmt(cip_['turnover_min'], 1)} min"],
        ["Heat-up energy per CIP", f"{fmt(cip_['heater_kwh'], 1)} kWh (+{fmt(cip_['d_t'], 1)} C)"],
        ["CIPs per month (all units)", fmt(cip_["events_month"], 2)],
    ])
    if cip_["rows"]:
        story.append(Spacer(1, 6))
        story.append(tbl([[r["step"], r["chem"], fmt(r["dose"], 0), amt(r["kg_event"], r["gal_event"]),
                           amt(r["kg_month"], r["gal_month"])] for r in cip_["rows"]],
                         ["Step", "Chemical", "Dose mg/L", "Per CIP", "Per month"],
                         [W * 0.24, W * 0.22, W * 0.16, W * 0.19, W * 0.19]))

    section("9. Pump Sizing", [
        ["Feed pump (max flow)", fmt(g("feed_pump_gpm", 0), 0), fmt(g("feed_pump_psi", 0), 1), fmt(g("feed_pump_head_ft", 0), 1), fmt(g("feed_pump_hp", 0), 2)],
        ["Backwash pump (BW / CEB)", fmt(g("bw_pump_gpm", 0), 0), fmt(g("backwash_pump_psi", 0), 1), fmt(g("bw_pump_head_ft", 0), 1), fmt(g("bw_pump_hp", 0), 2)],
        ["CIP pump", fmt(g("cip_pump_gpm", 0), 0), fmt(g("cip_pump_psi", 0), 1), fmt(g("cip_pump_head_ft", 0), 1), fmt(g("cip_pump_hp", 0), 2)],
    ], ["Pump", "Flow (gpm)", "Pressure (psi)", "Head (ft)", "Power (hp)"],
        [W * 0.32, W * 0.15, W * 0.18, W * 0.17, W * 0.18])

    def decor(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(1.2)
        canvas.line(18 * mm, A4[1] - 15 * mm, A4[0] - 18 * mm, A4[1] - 15 * mm)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(NAVY)
        canvas.drawString(18 * mm, A4[1] - 12 * mm, APP_TITLE)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 12 * mm, str(project)[:60])
        canvas.drawString(18 * mm, 10 * mm, f"Generated {now}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=22 * mm, bottomMargin=18 * mm,
                            title=f"{APP_TITLE} - {project}", author="HSKH")
    doc.build(story, onFirstPage=decor, onLaterPages=decor)
    return buf.getvalue()


# =====================================================
# SESSION DEFAULTS
# =====================================================
defaults = {
    "project_name": _default_project_name(),
    "ca": 0.0, "mg": 0.0, "na": 0.0, "k": 0.0, "ba": 0.0, "sr": 0.0,
    "hco3": 0.0, "co3": 0.0, "co2": 0.0, "so4": 0.0, "cl": 0.0, "no3": 0.0,
    "fluoride": 0.0, "silica": 0.0, "boron": 0.0, "iron": 0.0, "manganese": 0.0,
    "temperature": 25.0, "feed_ph": 7.0,
    "Turbidity": 0.0, "TSS": 0.0, "TOC": 0.0, "sdi": 0.0,
    "calculated_tds": 0.0, "hardness": 0.0, "conductivity": 0.0, "alkalinity": 0.0,
    "uf_feed_flow": 50.0, "uf_recovery": 95.0,
    "water_type": "Municipal Water",
    "uf_module_area": 77.0,
    "trains_online": 2, "standby_trains": 1,
    "uf_vendor_saved": "DuPont (IntegraTec / Inge)",
    "uf_technology_saved": "PVDF Out-In",
    "uf_module_saved": "IntegraTec XP 77 IP",
}
for key, value in defaults.items():
    ss.setdefault(key, value)


# =====================================================
# NAVIGATION  (top tabs + sidebar tabs)
# =====================================================
hdr_ph = st.empty()                      # big title band - filled at the end of the run

if ss.get("nav_main") not in MAIN_TABS:
    ss["nav_main"] = MAIN_TABS[0]
if ss.get("nav_uf") not in UF_TABS:
    ss["nav_uf"] = UF_TABS[0]


def _cb_nav(key, value):
    ss[key] = value


def nav_buttons(box_key, labels, state_key, horizontal):
    """Tab-style navigation: the active tab is a filled (primary) button."""
    try:
        box = st.container(key=box_key)
    except TypeError:
        box = st.container()
    with box:
        if horizontal:
            for i, (col, label) in enumerate(zip(st.columns(len(labels)), labels)):
                with col:
                    st.button(label, key=f"ui_{state_key}_{i}", on_click=_cb_nav, args=(state_key, label),
                              type="primary" if ss[state_key] == label else "secondary")
        else:
            for i, label in enumerate(labels):
                st.button(label, key=f"ui_{state_key}_{i}", on_click=_cb_nav, args=(state_key, label),
                          type="primary" if ss[state_key] == label else "secondary")


nav_buttons("topnav", MAIN_TABS, "nav_main", True)
main = ss["nav_main"].split(" ", 1)[1]

uf_page = "Design"
with st.sidebar:
    md('<div class="sb-brand">💧 HSKH<small>Ultrafiltration Design</small></div>')
    side_status = st.empty()
    if main == "UF":
        md('<div class="sb-h">UF Sections</div>')
        nav_buttons("sidenav", UF_TABS, "nav_uf", False)
        uf_page = ss["nav_uf"].split(" ", 1)[1]
    else:
        md('<div class="sb-h">Project Snapshot</div>')
        gg = ss.get
        snap = [("Water", gg("water_type", "")), ("Feed flow", f"{gg('uf_feed_flow', 0):.1f} m³/hr"),
                ("Module", gg("selected_module", "-")), ("Total modules", gg("total_modules", 0)),
                ("Recovery", f"{gg('uf_recovery_calc', 0):.1f} %")]
        md("".join(f'<div class="sb-row"><span>{hesc(l)}</span><b>{hesc(str(v))}</b></div>' for l, v in snap))
        md('<div class="sb-h">Tip</div>'
           '<div class="sb-row"><span>Open the <b>UF</b> tab for Design, Configuration, Backwash, '
           'CEB, CIP and Additional Settings.</span></div>')

flash = ss.pop("_flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
if ss.get("_theme_note"):
    st.info("A light-theme file (.streamlit/config.toml) was created. Stop and restart Streamlit once so every box and "
            "widget uses it.")


# =====================================================
# VIEW: PROJECTS  (all project information + project files)
# =====================================================
def view_projects():
    page_title("📁 Projects")

    with card("Project Information", "📋"):
        c = st.columns(3)
        with c[0]:
            w_text("Project name", "project_name")
            w_text("Project / case number", "pi_number")
        with c[1]:
            w_text("Client", "pi_client")
            w_text("Location", "pi_location")
        with c[2]:
            w_text("Prepared by", "pi_engineer")
            w_text("Date", "pi_date", datetime.now().strftime("%d %b %Y"))
        w_text("Application", "pi_application", "Cooling water treatment for boiler use")
        w_area("Notes", "pi_notes", height=80)

    with card("Project File", "💾"):
        c = st.columns([1, 1, 1.2, 1.4])
        with c[0]:
            st.button("🆕 New Project", key="ui_new", on_click=_cb_new)
        with c[1]:
            if st.button("💾 Save now", key="ui_save"):
                ss["_save_clicked"] = True
        with c[2]:
            w_check("Auto-save to folder", "autosave_disk", True)
        with c[3]:
            st.download_button("⬇ Download .uff", data=project_json(),
                               file_name=f"{_safe_name(ss.get('project_name', 'Project'))}.uff",
                               mime="application/json", key="ui_dl_uff")
        st.file_uploader("Load a project file (.uff) from your computer", type=["uff", "json"],
                         key="ui_upload", on_change=_cb_upload)
        st.caption(f"Every project is stored in its own folder under: {PROJECT_DIR}")

    with card("All Projects", "🗂"):
        q = st.text_input("Search projects", key="ui_search", placeholder="Type part of a project name…")
        items = [p for p in list_projects() if q.lower() in (p["name"] or "").lower()] if q else list_projects()
        cells = ["NEW"] + items
        current = str(ss.get("_last_path", ""))
        for r in range(0, len(cells), 3):
            cols = st.columns(3)
            for c, cell in zip(cols, cells[r:r + 3]):
                with c:
                    with card(prefix="pcard"):
                        if cell == "NEW":
                            md('<div class="pname">➕ Create New Project</div>'
                               '<div class="pmeta">Starts empty, gets its own folder</div>')
                            st.button("Create", key="ui_new2", on_click=_cb_new)
                        else:
                            is_cur = current.replace("\\", "/").endswith(cell["rel"])
                            md(
                                f'<div class="pname">{hesc(cell["name"] or "")}'
                                f'{" &nbsp;🟢" if is_cur else ""}</div>'
                                f'<div class="pmeta">Edited {_ago(cell["mtime"])}'
                                f'{" · " + hesc(str(cell["client"])) if cell["client"] else ""}</div>'
                                f'<div class="pmeta">{hesc(str(cell["module"] or "-"))} · '
                                f'{fmt(cell["flow"] or 0, 1)} m³/hr · {cell["modules"] or 0} modules</div>')
                            st.button("Open", key=f"ui_open_{cell['rel']}",
                                      on_click=_cb_open_path, args=(cell["rel"],))


# =====================================================
# PROCESS FLOW DIAGRAM  (full on System Design, a card under the title on every other page)
# =====================================================
def system_svg(active=None):
    """Original-style process schematic (left -> right).  Own symbol set:
    circle-and-triangle pumps, butterfly valves, hexagon strainer, horizontal fibre capsules in a module bank,
    wave-level tanks, chevron flow arrows and a different line style per stream
    (solid = feed / permeate, dashed = backwash, dash-dot = CIP, dotted = waste / air).
    `active` ('feed' | 'uf' | 'product') outlines the stage that belongs to the page being viewed."""
    g = ss.get
    GPM = 4.4029                                              # m3/h -> gpm
    cl = compute_cleaning()
    u, ceb, cip = cl["unit"], cl["ceb"], cl["cip"]

    feed_flow = float(g("uf_feed_flow", 0) or 0)
    rec = float(g("uf_recovery_calc", g("uf_recovery", 95.0)) or 0)
    prod = feed_flow * rec / 100
    waste = feed_flow - prod
    gross = float(g("gross_permeate", 0) or 0) or prod
    flux = float(g("operating_flux_gfd", 0) or 0)

    n_on, n_sb, n_red = (int(g(k, 0) or 0) for k in ("cfg_online_units", "cfg_standby_units", "cfg_redundant_units"))
    n_tot = n_on + n_sb + n_red
    mpr, rpu = int(g("cfg_modules_per_rack", 0) or 0), int(g("cfg_racks_per_unit", 1) or 1)
    tot_mod = int(g("total_modules", 0) or 0)
    mod = hesc(str(g("selected_module", "-")))
    wtype = hesc(str(g("water_type", "")))

    feed_gpm = feed_flow * GPM
    pump_gpm = float(g("feed_pump_gpm", 0) or 0) or feed_gpm
    pump_psi = float(g("feed_pump_psi", 0) or 0)
    bw_gpm, ceb_gpm = u["bw_flow"] * GPM, u["ceb_flow"] * GPM
    bw_psi = float(g("backwash_pump_psi", 0) or 0)
    cip_gpm, cip_psi = u["cip_flow"] * GPM, float(g("cip_pump_psi", 0) or 0)
    air_scfm = u["air_scfm"]
    strainer_um = float(g("strainer_size", 150.0) or 0)
    strainer_rec = float(g("strainer_recovery", 100.0) or 0)

    tank_on = g("storage_option", "BW + Filtrate") != "No Tank"
    vol_gal = max(cl["bw"]["event_vol"], ceb["event_vol"]) * 264.172 * float(g("bw_filtrate_factor", 100.0)) / 100
    tank_txt = f"{vol_gal:,.0f} gal" if tank_on else "No tank"

    HL = "#F28C28"
    C_FEED, C_PERM, C_CIP, C_WASTE, C_AIR, INK = "#0F766E", "#1D6FD6", "#7C3AED", "#EA580C", "#64748B", "#1E293B"

    def line(d, color, w=4, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" '
                f'stroke-linejoin="round"{da}/>')

    def chev(x, y, d, color):
        pts = {"r": "-5,-6 3,0 -5,6", "l": "5,-6 -3,0 5,6", "d": "-6,-5 0,3 6,-5", "u": "-6,5 0,-3 6,5"}[d]
        return (f'<polyline transform="translate({x},{y})" points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')

    def pump(x, y, color, d="r"):
        tri = {"r": "-5,-7 8,0 -5,7", "l": "5,-7 -8,0 5,7"}[d]
        return (f'<g transform="translate({x},{y})"><circle r="15" fill="#fff" stroke="{color}" stroke-width="2.5"/>'
                f'<polygon points="{tri}" fill="{color}"/></g>')

    def valve(x, y, color):
        return (f'<g transform="translate({x},{y})"><line x1="0" y1="-7" x2="0" y2="-15" stroke="{INK}" stroke-width="2"/>'
                f'<line x1="-5" y1="-15" x2="5" y2="-15" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
                f'<circle r="7" fill="#fff" stroke="{color}" stroke-width="2.5"/>'
                f'<line x1="0" y1="-7" x2="0" y2="7" stroke="{color}" stroke-width="2.5"/></g>')

    def strainer(x, y):
        return (f'<g transform="translate({x},{y})"><polygon points="-12,0 -6,-11 6,-11 12,0 6,11 -6,11" fill="#fff" '
                f'stroke="{C_FEED}" stroke-width="2.5"/><polyline points="-7,2 -3,-4 1,4 5,-3 8,1" fill="none" '
                f'stroke="{C_FEED}" stroke-width="1.6"/></g>')

    def blower(x, y):
        return (f'<g transform="translate({x},{y})"><circle r="15" fill="#fff" stroke="{C_AIR}" stroke-width="2.5"/>'
                + "".join(f'<path d="M0,0 L{9 * math.cos(math.radians(a)):.1f},{9 * math.sin(math.radians(a)):.1f}" '
                          f'stroke="{C_AIR}" stroke-width="3" stroke-linecap="round"/>' for a in (-90, 30, 150))
                + '</g>')

    def tank(x, y, w, h, color, cid, lines):
        wave = (f"M{x},{y + h * .42} q{w / 8},-9 {w / 4},0 t{w / 4},0 t{w / 4},0 t{w / 4},0 V{y + h} H{x} Z")
        s = (f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/></clipPath>'
             f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#F8FAFC" stroke="{color}" stroke-width="2.5"/>'
             f'<path d="{wave}" fill="{color}" fill-opacity=".30" clip-path="url(#{cid})"/>')
        for i, (t, sz, wt) in enumerate(lines):
            s += txt(x + w / 2, y + h * .45 + i * 17, t, sz, wt, INK, "middle")
        return s

    def txt(x, y, s, size=12, w=400, fill=INK, anchor="start"):
        return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{fill}" '
                f'text-anchor="{anchor}">{s}</text>')

    def card_box(x, y, w, h, color, title, sub_):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#fff" stroke="{color}" stroke-width="2.5"/>'
                f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="14" fill="{color}"/>'
                f'<rect x="{x}" y="{y + 14}" width="{w}" height="12" fill="{color}"/>'
                + txt(x + w / 2, y + 18, title, 12.5, 700, "#fff", "middle")
                + "".join(txt(x + w / 2, y + 48 + i * 16, t, sz, wt, INK, "middle") for i, (t, sz, wt) in enumerate(sub_)))

    def chip(x, y, w, label, value, color="#475569"):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="#fff" stroke="{color}" stroke-width="1.5"/>'
                f'<text x="{x + 12}" y="{y + 17}" font-size="11.5" fill="{color}" font-weight="700">{label}'
                f'<tspan fill="{INK}" font-weight="500"> {value}</tspan></text>')

    # ---- stat chips ----
    chips = (chip(20, 8, 232, "Module", mod) + chip(260, 8, 150, "Units", f"{n_tot} ({n_on}+{n_sb}+{n_red})")
             + chip(418, 8, 196, "Modules", f"{n_tot}×({mpr}×{rpu}) = {tot_mod}")
             + chip(622, 8, 130, "Flux", f"{flux:.0f} gfd") + chip(760, 8, 150, "Recovery", f"{rec:.2f} %"))

    # ---- CEB chemical box ----
    ceb_t = []
    for i, r in enumerate(ceb["rows"][:4]):
        ceb_t.append(f'<path transform="translate(702,{93 + i * 16})" d="M0,-6 C5,1 5,5 0,5 C-5,5 -5,1 0,-6Z" fill="{C_CIP}"/>')
        ceb_t.append(txt(712, 97 + i * 16, f"{r['step'].replace(' CEB', '')}: {r['dose']:,.0f} mg/L {hesc(r['chem'])} · "
                                           f"{hesc(amt(r['kg_h'], r['gal_h'], True))}", 11))
    if not ceb_t:
        ceb_t.append(txt(702, 97, "No CEB chemical switched on", 11))

    # ---- cleaning-interval chips ----
    feat = g("uf_feature", "CEB only")
    acid_on = bool(cv("mineral_acid_enabled") or cv("organic_acid_enabled")) and feat != "mini-CIP only"
    alk_on = bool(cv("alkali_enabled") or cv("alkali_oxidant_enabled")) and feat != "mini-CIP only"
    iv = [("Filtration", f"{float(g('uf_filtration_duration', 25)):.0f} min"),
          ("Acid CEB", f"{float(g('uf_acid_ceb', 168)):.0f} h" if acid_on else "off"),
          ("Alkali/Ox CEB", f"{float(g('uf_alk_ceb', 24)):.0f} h" if alk_on else "off"),
          ("Disinfection", "on" if cv("disinfection_enabled") else "off"),
          ("mini-CIP", "on" if feat != "CEB only" else "off"),
          ("CIP", f"every {float(g('uf_cip_interval', 30)):.0f} d")]
    ivs = "".join(chip(20 + i * 160, 514, 152, a, b, "#334155") for i, (a, b) in enumerate(iv))

    # ---- membrane capsules (horizontal hollow-fibre modules) ----
    caps = ""
    for cy in (153, 203, 253):
        caps += (f'<rect x="432" y="{cy - 18}" width="178" height="36" rx="18" fill="#EEF4FA" stroke="#3B5B7C" stroke-width="2"/>'
                 + "".join(f'<line x1="446" y1="{cy + o}" x2="596" y2="{cy + o}" stroke="#7FB2E5" stroke-width="1.6"/>'
                           for o in (-9, -3, 3, 9)))

    hl = ""
    boxes = {"feed": (10, 150, 372, 140), "uf": (392, 96, 266, 214), "product": (688, 150, 306, 114)}
    if active in boxes:
        x, y, w, h = boxes[active]
        hl = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{HL}" fill-opacity=".10" '
              f'stroke="{HL}" stroke-width="3" stroke-dasharray="8 5"/>')

    svg = f"""
<html><body style="margin:0;background:transparent;font-family:'Segoe UI',Arial,sans-serif;">
<svg viewBox="0 0 1000 570" width="1000" xmlns="http://www.w3.org/2000/svg"
     style="display:block;margin:0 auto;max-width:100%;height:auto;font-family:'Segoe UI',Arial,sans-serif;">
{hl}
{chips}

<!-- ===== streams ===== -->
{line("M130,203 H418", C_FEED, 4)}
{line("M622,203 H840", C_PERM, 4)}
{line("M760,203 V345", C_PERM, 4)}
{line("M700,385 H632 V262", C_PERM, 3, "9 6")}
{line("M300,90 H470 V105", C_CIP, 3, "12 4 2 4")}
{line("M560,105 V45 H230 V60", C_CIP, 3, "12 4 2 4")}
{line("M690,125 H600 V105", C_CIP, 3, "2 6")}
{line("M585,300 V470 H840", C_WASTE, 4, "1 8")}
{line("M315,395 H500 V300", C_AIR, 4, "1 8")}
<!-- module manifolds -->
{line("M418,153 V253", C_FEED, 4)}{line("M418,153 H432", C_FEED, 3)}{line("M418,253 H432", C_FEED, 3)}
{line("M622,153 V253", C_PERM, 4)}{line("M610,153 H622", C_PERM, 3)}{line("M610,253 H622", C_PERM, 3)}

<!-- ===== module bank ===== -->
<rect x="400" y="105" width="250" height="195" rx="16" fill="#F5F8FB" stroke="#3B5B7C" stroke-width="2" stroke-dasharray="3 0"/>
{txt(525, 124, f"UF bank · {n_tot} units", 11.5, 700, "#3B5B7C", "middle")}
{caps}
{txt(525, 292, mod, 10.5, 500, "#475569", "middle")}

<!-- ===== sources / sinks ===== -->
{card_box(20, 163, 110, 80, C_FEED, "FEED", [(f"{feed_gpm:,.0f} gpm", 15, 700), (wtype, 10.5, 400)])}
{txt(20, 262, f"TSS {float(g('TSS', 0)):.0f} mg/L · TOC {float(g('TOC', 0)):.0f} mg/L", 11, 400, "#475569")}
{txt(20, 276, f"Turbidity {float(g('Turbidity', 0)):.0f} NTU", 11, 400, "#475569")}
{card_box(840, 163, 140, 80, C_PERM, "NET FILTRATE", [(f"{prod * GPM:,.0f} gpm", 15, 700), ("UF permeate", 10.5, 400)])}
{card_box(840, 440, 140, 80, C_WASTE, "WASTE", [(f"{waste * GPM:,.0f} gpm", 15, 700), ("BW + FF + CEB", 10.5, 400)])}

<!-- ===== tanks ===== -->
{tank(700, 345, 120, 80, C_PERM, "wv1", [("Filtrate / BW tank", 11, 700), (tank_txt, 12, 600)])}
{tank(160, 60, 140, 62, C_CIP, "wv2", [("CIP tank", 11, 700), (f"{cip['tank_gal']:,.0f} gal", 12, 600)])}

<!-- ===== CEB dosing box ===== -->
<rect x="690" y="55" width="300" height="100" rx="12" fill="#fff" stroke="{C_CIP}" stroke-width="2.5"/>
{txt(702, 75, "CEB dosing (100 % chemical)", 12, 700, C_CIP)}
{"".join(ceb_t)}

<!-- ===== symbols ===== -->
{pump(190, 203, C_FEED)}{strainer(255, 203)}{valve(325, 203, C_FEED)}
{valve(700, 203, C_PERM)}{valve(520, 470, C_WASTE)}{valve(585, 372, C_WASTE)}
{pump(345, 90, C_CIP)}{pump(668, 385, C_PERM, "l")}{blower(300, 395)}

<!-- ===== flow chevrons ===== -->
{chev(150, 203, "r", C_FEED)}{chev(385, 203, "r", C_FEED)}
{chev(660, 203, "r", C_PERM)}{chev(805, 203, "r", C_PERM)}{chev(760, 300, "d", C_PERM)}{chev(690, 385, "l", C_PERM)}{chev(632, 290, "u", C_PERM)}
{chev(400, 90, "r", C_CIP)}{chev(400, 45, "l", C_CIP)}
{chev(585, 420, "d", C_WASTE)}{chev(700, 470, "r", C_WASTE)}
{chev(400, 395, "r", C_AIR)}{chev(500, 340, "u", C_AIR)}

<!-- ===== labels ===== -->
{txt(190, 235, "Feed pump", 12, 700, C_FEED, "middle")}{txt(190, 249, f"{pump_gpm:,.0f} gpm @ {pump_psi:.0f} psi", 10.5, 400, "#475569", "middle")}
{txt(262, 172, "Strainer", 11.5, 700, C_FEED, "middle")}{txt(262, 185, f"{strainer_um:.0f} µm · {strainer_rec:.0f} %", 10.5, 400, "#475569", "middle")}
{txt(330, 232, "Feed valve", 11, 400, "#475569", "middle")}
{txt(345, 55, "CIP pump", 11.5, 700, C_CIP, "middle")}{txt(345, 128, f"{cip_gpm:,.0f} gpm @ {cip_psi:.0f} psi", 10.5, 400, "#475569", "middle")}
{txt(700, 232, "Filtrate valve", 11, 400, "#475569", "middle")}
{txt(668, 340, "Backwash pump", 11.5, 700, C_PERM, "middle")}{txt(668, 420, f"BW {bw_gpm:,.0f} · CEB {ceb_gpm:,.0f} gpm @ {bw_psi:.0f} psi", 10.5, 400, "#475569", "middle")}
{txt(640, 185, f"Gross {gross * GPM:,.0f} gpm", 11, 600, C_PERM)}
{txt(300, 430, "Air scour", 11.5, 700, C_AIR, "middle")}{txt(300, 444, f"{air_scfm:,.0f} scfm", 10.5, 400, "#475569", "middle")}
{txt(520, 496, "Bottom drain", 11, 400, "#475569", "middle")}{txt(600, 376, "Drain", 11, 400, "#475569")}

<!-- ===== cleaning intervals & legend ===== -->
{ivs}
<g font-size="10.5" fill="#475569">
 <line x1="20" y1="556" x2="52" y2="556" stroke="{C_FEED}" stroke-width="4" stroke-linecap="round"/>{txt(58, 560, "Feed / permeate", 10.5, 400, "#475569")}
 <line x1="170" y1="556" x2="202" y2="556" stroke="{C_PERM}" stroke-width="3" stroke-dasharray="9 6" stroke-linecap="round"/>{txt(208, 560, "Backwash", 10.5, 400, "#475569")}
 <line x1="290" y1="556" x2="322" y2="556" stroke="{C_CIP}" stroke-width="3" stroke-dasharray="12 4 2 4" stroke-linecap="round"/>{txt(328, 560, "CIP / CEB chemicals", 10.5, 400, "#475569")}
 <line x1="470" y1="556" x2="502" y2="556" stroke="{C_WASTE}" stroke-width="4" stroke-dasharray="1 8" stroke-linecap="round"/>{txt(508, 560, "Waste", 10.5, 400, "#475569")}
 <line x1="580" y1="556" x2="612" y2="556" stroke="{C_AIR}" stroke-width="4" stroke-dasharray="1 8" stroke-linecap="round"/>{txt(618, 560, "Air", 10.5, 400, "#475569")}
</g>
</svg></body></html>"""
    return svg


def fill_flow_diagram():
    """Draw the flow diagram in the slot reserved by page_title() (called after the page has been built,
    so every number is current).  The stage that belongs to the open tab is outlined in orange."""
    ph = _FLOW_PH[0]
    if ph is None:
        return
    active = {"Feed": "feed", "UF": "uf", "Report": "product"}.get(main)
    with ph.container():
        with card("Process Flow Diagram", "🗺"):
            components.html(system_svg(active), height=600)


def view_system():
    page_title("🧩 System Design")
    feed, perm = compute_permeate()
    g = ss.get

    with card("Stream Summary", "📊"):
        sub("Feed")
        tiles([("Water type", g("water_type", "")), ("Flow", f"{g('uf_feed_flow', 0):.1f} m³/hr"),
               ("pH", f"{g('feed_ph', 7):.2f}"), ("Temp", f"{g('temperature', 25):.1f} °C"),
               ("TDS", f"{g('calculated_tds', 0):.0f} mg/L"), ("Turbidity", f"{g('Turbidity', 0):.2f} NTU"),
               ("TOC", f"{g('TOC', 0):.1f} mg/L"), ("SDI", f"{g('sdi', 0):.1f}")])
        sub("UF")
        tiles([("Module", g("selected_module", "-")), ("Total modules", g("total_modules", 0)),
               ("Online modules", g("online_modules", 0)), ("Flux", f"{g('operating_flux_gfd', 0):.1f} gfd"),
               ("Recovery", f"{g('uf_recovery_calc', 0):.1f} %"),
               ("Trains", f"{g('trains_online', 0)} + {g('standby_trains', 0)}")])
        sub("Product (UF permeate)")
        tiles([("TDS", f"{perm['TDS']:.0f} mg/L"), ("Turbidity", f"{perm['Turbidity']:.3f} NTU"),
               ("TSS", f"{perm['TSS']:.3f} mg/L"), ("TOC", f"{perm['TOC']:.2f} mg/L"),
               ("SDI", f"{perm['SDI']:.1f}"), ("pH", f"{perm['pH']:.2f}")])

    render_design_check(design_check())

    with card("Feed vs UF Permeate Quality", "💧"):
        show_df(pd.DataFrame({"Parameter": list(feed.keys()), "Feed Water": list(feed.values()),
                              "UF Permeate": list(perm.values())}), hide_index=True)


# =====================================================
# VIEW: FEED
# =====================================================
def _cb_apply_balance(changes):
    """Write the balanced concentrations into the stored data (inputs refresh on the next run)."""
    for k, v in changes.items():
        ss[k] = v
        SAVED[k] = v
    names = ", ".join(f"{chem.IONS[k][0]} → {v:.2f} mg/L" for k, v in changes.items())
    ss["_flash"] = ("success", f"Water analysis balanced: {names}")


def _cb_set_value(key, value):
    ss[key] = value
    SAVED[key] = value


def view_feed():
    page_title("💧 Feed Water")

    with card("Import Water Analysis (IMS)", "📂"):
        c = st.columns([4, 1])
        uploaded_file = c[0].file_uploader("IMS Excel file", type=["xlsx"], key="ui_ims_upload",
                                           label_visibility="collapsed")
        if c[1].button("Load file", key="ui_ims_load"):
            if uploaded_file is None:
                st.warning("Please select IMS Excel file")
            else:
                df = pd.read_excel(uploaded_file, header=1, engine="openpyxl").dropna(how="all")
                water = dict(zip(df["Species"].astype(str).str.strip(), df["Raw water"]))
                mapping = {
                    "Calcium": "ca", "Magnesium": "mg", "Sodium": "na", "Potassium": "k",
                    "Ammonium": "ammonium", "Strontium": "sr", "Barium": "ba", "Fluoride": "fluoride",
                    "Chloride": "cl", "Sulfate": "so4", "Nitrate": "no3",
                    "Carbonate": "co3", "Bicarbonate": "hco3", "Boron": "boron",
                    "Silica": "silica", "pH": "feed_ph", "CO2": "co2",
                    "Turbidity": "Turbidity", "TSS": "TSS", "TOC": "TOC", "SDI": "sdi",
                }
                for species, key in mapping.items():
                    default = 7.0 if key == "feed_ph" else 0.0
                    value = water.get(species, default)
                    value = default if pd.isna(value) else float(value)
                    ss[key] = value
                    SAVED[key] = value
                st.success("✅ IMS Water Analysis Loaded Successfully")

    with card("Feed Parameters", "⚙️"):
        p1, p2, p3 = st.columns([1.2, 1.4, 1])
        with p1:
            water_types = ["UF Permeate", "Softened Water", "Well Water", "Ground Water",
                           "Municipal Water", "Surface Water", "Brackish Water", "Sea Water"]
            water_type = w_select("Water Type", water_types, "water_type", "Municipal Water")
        sdi_requirements = {
            "UF Permeate": ("SDI < 1", "good"), "Softened Water": ("SDI < 3", "good"),
            "Well Water": ("SDI < 3", "good"), "Ground Water": ("SDI < 3", "good"),
            "Municipal Water": ("SDI < 5", "warn"), "Surface Water": ("SDI < 5", "warn"),
            "Brackish Water": ("Membrane pretreatment, SDI < 3", "bad"),
            "Sea Water": ("Conventional pretreatment + UF, SDI < 3", "bad"),
        }
        sdi_text, sdi_cls = sdi_requirements[water_type]
        with p2:
            md('<div style="height:.5rem"></div>')
            tiles([("Recommended feed requirement", sdi_text, sdi_cls)])
        with p3:
            w_number("UF Feed Flow (m³/hr)", "uf_feed_flow", 50.0)

    with card("Feed Water Analysis", "🧪"):
        sub("Cations (mg/L)")
        c = st.columns(7)
        with c[0]: w_number("Calcium (Ca)", "ca", 0.0)
        with c[1]: w_number("Magnesium (Mg)", "mg", 0.0)
        with c[2]: w_number("Sodium (Na)", "na", 0.0)
        with c[3]: w_number("Potassium (K)", "k", 0.0)
        with c[4]: w_number("Ammonium (NH4)", "ammonium", 0.0)
        with c[5]: w_number("Barium (Ba)", "ba", 0.0)
        with c[6]: w_number("Strontium (Sr)", "sr", 0.0)
        sub("Anions (mg/L)")
        c = st.columns(6)
        with c[0]: w_number("Bicarbonate (HCO3)", "hco3", 0.0)
        with c[1]: w_number("Carbonate (CO3)", "co3", 0.0)
        with c[2]: w_number("Sulphate (SO4)", "so4", 0.0)
        with c[3]: w_number("Chloride (Cl)", "cl", 0.0)
        with c[4]: w_number("Nitrate (NO3)", "no3", 0.0)
        with c[5]: w_number("Fluoride (F)", "fluoride", 0.0)
        sub("Metals, neutral species, temperature & pH")
        c = st.columns(7)
        with c[0]: w_number("Silica (SiO2) mg/L", "silica", 0.0)
        with c[1]: w_number("Boron (B) mg/L", "boron", 0.0)
        with c[2]: w_number("Iron (Fe) mg/L", "iron", 0.0)
        with c[3]: w_number("Manganese (Mn) mg/L", "manganese", 0.0)
        with c[4]: w_number("Free CO2 mg/L", "co2", 0.0)
        with c[5]: w_number("Temperature (°C)", "temperature", 25.0)
        with c[6]: w_number("pH", "feed_ph", 7.0)
        sub("Particulates & organics")
        c = st.columns(6)
        with c[0]: w_number("Turbidity (NTU)", "Turbidity", 0.0)
        with c[1]: w_number("TSS (mg/L)", "TSS", 0.0)
        with c[2]: w_number("TOC (mg/L)", "TOC", 0.0)
        with c[3]: w_number("SDI15", "sdi", 0.0)

    # ---- ion balance (see water_chemistry.py) ----
    w = {k: float(ss.get(k, 0) or 0) for k in chem.ION_KEYS + ("silica", "boron")}
    ph = float(ss.get("feed_ph", 7.0))
    temp = float(ss.get("temperature", 25.0))
    res = chem.analyze(w, ph, temp)

    ss["calculated_tds"] = res["tds"]
    ss["hardness"] = res["hardness"]
    ss["conductivity"] = res["conductivity"]
    ss["alkalinity"] = res["alkalinity"]
    ss["charge_balance_pct"] = res["cbe_pct"]
    ss["raw_ph"] = ph
    ss["bicarbonate"] = w["hco3"]
    ss["carbonate"] = w["co3"]

    with card("Charge Balance", "⚖️"):
        cls = {"OK": "good", "Review": "warn", "Fail": "bad"}[res["status"]]
        tiles([("Cations", f"{res['cation_total']:.3f} meq/L"), ("Anions", f"{res['anion_total']:.3f} meq/L"),
               ("Difference (cat − an)", f"{res['diff_meq']:+.3f} meq/L"),
               ("Charge balance error", f"{res['cbe_pct']:+.2f} % · {res['status']}", cls)])
        if res["status"] != "OK" and (res["cation_total"] + res["anion_total"]) > 0:
            if res["diff_meq"] > 0:
                st.warning("Excess cations - an anion (Cl⁻, SO₄²⁻, HCO₃⁻, NO₃⁻) is missing or too low. "
                           "Check the analysis, or use Auto balance below.")
            else:
                st.warning("Excess anions - a cation (Na⁺, Ca²⁺, Mg²⁺, K⁺) is missing or too low. "
                           "Check the analysis, or use Auto balance below.")

        def ion_df(kind, total):
            rows = [(lab, mg, meq) for key, lab, kd, mg, meq in res["rows"]
                    if kd == kind and (meq > 0 or key in ("h", "oh"))]
            df = pd.DataFrame({
                "Ion": [r[0] for r in rows] + ["Total"],
                "mg/L": [round(r[1], 2) for r in rows] + [None],
                "meq/L": [round(r[2], 4) for r in rows] + [round(total, 4)],
                "% of group": [round(r[2] / total * 100, 1) if total > 0 else 0.0 for r in rows] + [100.0 if total > 0 else 0.0],
            })
            return df

        t1, t2 = st.columns(2)
        with t1:
            sub("Cations")
            show_df(ion_df("cation", res["cation_total"]), hide_index=True)
        with t2:
            sub("Anions")
            show_df(ion_df("anion", res["anion_total"]), hide_index=True)

        sub("Auto balance")
        b1, b2 = st.columns([3, 1])
        with b1:
            method = w_select("Balance using", list(chem.BALANCE_METHODS), "balance_method")
        bal = chem.auto_balance(w, ph, temp, method)
        with b2:
            md('<div style="height:.5rem"></div>')
            st.button("⚖️ Apply balance", key="ui_apply_balance", on_click=_cb_apply_balance,
                      args=(bal["changes"],), disabled=not bal["changes"])
        if bal["changes"]:
            tiles([(f"{chem.IONS[k][0]}  (now → balanced)", f"{w[k]:.2f} → {v:.2f} mg/L")
                   for k, v in bal["changes"].items()])
            if abs(bal["residual_meq"]) > 0.01:
                st.warning(f"This method cannot fully balance the water ({bal['residual_meq']:+.3f} meq/L "
                           f"remains). Choose Na⁺ / Cl⁻ instead.")
        else:
            st.success("✅ Cations and anions are already balanced.")

    with card("Calculated Water Quality", "🧮"):
        tiles([("TDS", f"{res['tds']:.1f} mg/L"), ("Hardness", f"{res['hardness']:.1f} mg/L CaCO3"),
               ("Alkalinity", f"{res['alkalinity']:.1f} mg/L CaCO3"),
               ("Conductivity (est.)", f"{res['conductivity']:.0f} µS/cm"),
               ("Ionic strength", f"{res['ionic_strength']:.4f} mol/L")])
        if ss.get("Turbidity", 0) > 50:
            st.warning("⚠ High turbidity - consider clarification before UF")
        if ss.get("sdi", 0) > 5:
            st.warning("⚠ High SDI may reduce UF performance")
        if ss.get("iron", 0) > 0.3:
            st.warning("⚠ Iron may increase membrane fouling")
        if ss.get("manganese", 0) > 0.1:
            st.warning("⚠ Manganese may increase membrane fouling")
        if ss.get("TOC", 0) > 10:
            st.warning("⚠ High TOC may increase CEB/CIP frequency")

    with card("pH & Carbonate System", "🧬"):
        co2_entered = float(ss.get("co2", 0) or 0)
        co2_calc = chem.co2_from_ph(w["hco3"], ph, temp)
        ph_calc = chem.ph_from_co2(w["hco3"], co2_entered, temp)
        ph_neutral = chem.ph_for_neutrality(w, temp)
        tiles([("Feed pH", f"{ph:.2f}"), ("H⁺ / OH⁻", f"{res['h_meq']:.1e} / {res['oh_meq']:.1e} meq/L"),
               ("CO₂ at this pH & HCO₃⁻", f"{co2_calc:.1f} mg/L"), ("CO₂ entered", f"{co2_entered:.1f} mg/L"),
               ("pH from HCO₃⁻ + CO₂", f"{ph_calc:.2f}" if ph_calc else "-"),
               ("pH for charge neutrality", f"{ph_neutral:.2f}" if ph_neutral else "not reachable")])
        c1, c2 = st.columns([1, 3])
        with c1:
            st.button("Use calculated CO₂", key="ui_use_co2", on_click=_cb_set_value,
                      args=("co2", round(co2_calc, 2)), disabled=w["hco3"] <= 0)
        with c2:
            st.caption("CO₂ is estimated from pH and bicarbonate (25 °C-corrected pK₁). The neutrality pH is where "
                       "cations = anions; if the ions are far out of balance it cannot be reached by pH alone.")


# =====================================================
# UF PAGES
# =====================================================
def uf_strip():
    g = ss.get
    with card():
        tiles([("Module", g("selected_module", "-")), ("Feed flow", f"{g('uf_feed_flow', 0):.1f} m³/hr"),
               ("Total modules", g("total_modules", 0)), ("Operating flux", f"{g('operating_flux_gfd', 0):.1f} gfd"),
               ("Recovery", f"{g('uf_recovery_calc', 0):.1f} %")])


def view_uf_design():
    page_title("🔷 UF · Design")
    uf_strip()

    left, right = st.columns([1, 1.6])
    with left:
        with card("Feed Flow & Module Selection", "🧱"):
            uf_feed_flow = w_number("Feed Flow (m³/hr)", "uf_feed_flow", 50.0)
            vendor, uf_technology, module, selected = vendor_selector()

            ss["selected_module_data"] = selected
            ss["selected_module_name"] = module
            ss["selected_module"] = module
            ss["uf_module_area"] = selected["area"]
            ss["uf_module_flux"] = selected["flux_gfd"]
            module_area = selected["area"]

            length_txt = (f"{selected['length']:,} mm" if isinstance(selected["length"], (int, float)) else "N/A")
            tmp_txt = f"{selected['tmp']} bar" if isinstance(selected["tmp"], (int, float)) else "N/A"
            fid_txt = f"{selected['id']} mm" if isinstance(selected["id"], (int, float)) else "N/A"
            tiles([("Module area", f"{module_area} m²"), ("Length", length_txt),
                   ("Max TMP", tmp_txt), ("Fiber ID", fid_txt),
                   ("Material", selected["material"]), ("Mode", selected["mode"]),
                   ("Mounting", selected["mounting"]), ("Orientation", selected["orientation"])])

    with right:
        mk = module.replace(" ", "_")      # per-module keys: each module remembers its own values
        with card("Design Flux & Flow Rates", "💧"):
            c1, c2, c3 = st.columns(3)
            with c1:
                flux_gfd = w_number("Filtrate Flux (GFD)", f"flux_{mk}", float(selected["flux_gfd"]),
                                    min_value=10.0, max_value=80.0)
                air_flow = w_number("Air Flow (scfm/module)", f"air_{mk}", float(selected["air_flow"]))
            with c2:
                backwash_gfd = w_number("Backwash Flux (GFD)", f"bwf_{mk}", float(selected["backwash_gfd"]))
                forward_flush = w_number("Forward Flush (gpm/module)", f"ff_{mk}",
                                         float(selected["forward_flush"]))
            with c3:
                ceb_gfd = w_number("CEB Flux (GFD)", f"cebf_{mk}", float(selected["ceb_gfd"]))
                cip_recycle_in = w_number("CIP Recycle (gpm/module)", f"cip_{mk}",
                                          float(selected["cip_recycle"]))

        with card("Special Features & Cleaning Intervals", "🕒"):
            c1, c2 = st.columns([1.2, 1])
            with c1:
                w_radio("UF Special Features", ["CEB only", "mini-CIP only", "CEB and mini-CIP"], "uf_feature")
                w_check("Adjust pH / Oxidant / Coagulant", "uf_adjust_chem", False)
            with c2:
                w_number("Filtration Duration (min)", "uf_filtration_duration", 25.0)
            c1, c2, c3 = st.columns(3)
            with c1: w_number("Acid CEB Interval (hr)", "uf_acid_ceb", 168.0)
            with c2: w_number("Alkali/Oxidant CEB (hr)", "uf_alk_ceb", 24.0)
            with c3: w_number("CIP Interval (days)", "uf_cip_interval", 30.0)

    flux = flux_gfd * 1.699            # GFD -> LMH
    backwash_flux = backwash_gfd * 1.699
    ceb_flux = ceb_gfd * 1.699
    n_exact = required_modules_exact(uf_feed_flow, flux_gfd, module_area, compute_cleaning())
    required_modules = max(math.ceil(n_exact - 1e-9), 1)
    required_area = n_exact * module_area
    ceb_flow = (required_area * ceb_flux) / 1000

    ss.update({
        "uf_flux": flux, "uf_flux_gfd": flux_gfd,
        "uf_backwash_flux": backwash_flux, "uf_backwash_gfd": backwash_gfd,
        "uf_ceb_flux": ceb_flux, "uf_ceb_gfd": ceb_gfd, "uf_ceb_flow": ceb_flow,
        "uf_required_area": required_area, "uf_modules": required_modules,
        "uf_air_flow": air_flow, "cip_recycle_input": cip_recycle_in, "uf_forward_flush": forward_flush,
    })

    with card("Design Results", "📐"):
        tiles([("Required membrane area", f"{required_area:,.0f} m²"),
               ("Required modules", required_modules), ("CEB flow (all modules)", f"{ceb_flow:.1f} m³/hr"),
               ("Filtrate flux", f"{flux_gfd:.1f} gfd"), ("Backwash flux", f"{backwash_gfd:.1f} gfd"),
               ("CEB flux", f"{ceb_gfd:.1f} gfd"),
               ("Filtering time (unit availability)", f"{compute_cleaning()['avail']['A'] * 100:.1f} %")])

    check_box = st.container()          # design check goes BELOW the selection / design cards
    with check_box:
        render_design_check(design_check(live={"uf_feed_flow": uf_feed_flow, "uf_flux_gfd": flux_gfd,
                                               "uf_modules": required_modules}))


def view_uf_configuration():
    page_title("⚙️ UF · Configuration")

    feed_flow = max(float(ss.get("uf_feed_flow", 50.0)), 0.001)
    modules_required = ss.get("uf_modules", 1)
    recovery = ss.get("uf_recovery", 95.0)

    vendor = ss.get("uf_vendor_saved", "")
    module_name = ss.get("selected_module", "")
    module_data = ss.get("selected_module_data", {})

    if not module_data:
        st.warning("No module selected yet. Choose a vendor and module on the Design section first. "
                   "Using DuPont XP 77 defaults for now.")

    module_area_m2 = module_data.get("area", 77.0)
    mounting = module_data.get("mounting", "Rack")
    orientation = module_data.get("orientation", "Vertical")

    rules = dict(rack_rules(vendor))
    if mounting == "Open Platform":
        rules.update(min=1, max=100, sizes=None, default=min(rules["default"], 100), verified=False,
                     note="Open-platform module: rack-size limit not applied. Confirm the skid layout with the vendor.")

    with card():
        tiles([("Vendor", vendor or "N/A"), ("Module", module_name or "N/A"),
               ("Area", f"{module_area_m2} m²"), ("Mounting", mounting), ("Orientation", orientation)])

    c_left, c_right = st.columns(2)
    with c_left:
        with card("Train Configuration", "🚂"):
            a, b = st.columns(2)
            with a: trains_online = w_number("Operating Trains", "trains_online", 2, min_value=1)
            with b: standby_trains = w_number("Standby Trains", "standby_trains", 1, min_value=0)
            total_trains = trains_online + standby_trains
    with c_right:
        with card("Recovery & Cleaning", "♻️"):
            a, b, c = st.columns(3)
            with a:
                uf_recovery_input = w_number("UF Recovery (%)", "uf_recovery_input", float(recovery),
                                             min_value=85.0, max_value=99.9)
            with b: w_number("Backwash (sec)", "cfg_bw_duration", 30.0)
            with c: w_number("CIP (hr)", "cfg_cip_duration", 4.0)

    with card("System Configuration", "🧩"):
        a, b = st.columns(2)
        with a:
            standby_option = w_radio("Standby Option",
                                     ["Constant operating flux, variable system output",
                                      "Constant system output, variable operating flux"], "standby_option")
        with b:
            w_select("Storage Tank Option", ["BW + Filtrate", "Filtrate Only", "No Tank"], "storage_option")

    unit_label = "Racks/Unit" if mounting == "Rack" else "Platforms/Unit"
    with card("Selected Configuration", "🏗"):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            racks_per_unit = w_number(unit_label, "cfg_racks_per_unit", 1, min_value=1)
        with c2:
            mpr_key = f"cfg_modules_per_rack_{vendor}_{mounting}"
            if rules["sizes"]:
                sizes = rules["sizes"]
                modules_per_rack = w_select("Modules/Rack", sizes, mpr_key,
                                            rules["default"] if rules["default"] in sizes else sizes[0])
            else:
                modules_per_rack = w_number("Modules/Rack", mpr_key, int(rules["default"]),
                                            min_value=int(rules["min"]), max_value=int(rules["max"]))
        with c3: online_units = w_number("Online Units", "cfg_online_units", 2, min_value=1)
        with c4: standby_units = w_number("Standby Units", "cfg_standby_units", 0, min_value=0)
        with c5: redundant_units = w_number("Redundant Units", "cfg_redundant_units", 1, min_value=0)
        st.caption(rules["note"] + ("" if rules["verified"] else "  (generic - please verify)"))

        total_units = online_units + standby_units + redundant_units
        total_racks = racks_per_unit * total_units
        modules_per_unit = racks_per_unit * modules_per_rack
        total_modules = total_units * modules_per_unit
        online_modules = online_units * modules_per_unit

        cl0 = compute_cleaning()           # availability depends on the cycle durations, not on the unit size
        fm = flux_model(feed_flow, online_modules, module_area_m2, cl0)
        flow_gpm = feed_flow * 4.4029
        online_area_ft2 = fm["area_ft2"]
        operating_flux_gfd = fm["op_flux_gfd"]

        tiles([("Total units", total_units), ("Total racks", total_racks),
               ("Modules / unit", modules_per_unit), ("Total modules", total_modules),
               ("Online modules", online_modules), ("Operating flux (filtering)", f"{operating_flux_gfd:.2f} gfd"),
               ("Filtering time", f"{fm['A'] * 100:.1f} %")])

        design_flux_gfd = ss.get("uf_flux_gfd")
        if design_flux_gfd and operating_flux_gfd > design_flux_gfd:
            st.warning(f"Operating flux ({operating_flux_gfd:.1f} gfd) is above the design flux "
                       f"({design_flux_gfd:.1f} gfd). Add modules or units.")
        if modules_required > online_modules:
            st.warning(f"Design needs {modules_required} modules online; this configuration has only {online_modules}.")

    # ---- hydraulics ----
    bw_gfd = ss.get("uf_backwash_gfd", module_data.get("backwash_gfd", 58.9))
    ceb_gfd = ss.get("uf_ceb_gfd", module_data.get("ceb_gfd", bw_gfd))
    ff_gpm_module = ss.get("uf_forward_flush", module_data.get("forward_flush", 0.0))
    cip_recycle = ss.get("cip_recycle_input", module_data.get("cip_recycle", 6.6))

    unit_area_m2 = modules_per_unit * module_area_m2
    backwash_flow = unit_area_m2 * (bw_gfd * 1.699) / 1000
    ff_flow = modules_per_unit * ff_gpm_module * 0.2271
    cip_flow = modules_per_unit * cip_recycle * 0.2271

    # ---- recommended configurations ----
    candidates = rules["sizes"] or [x for x in (6, 8, 12, 16, 18, 22, 24, 30, 36, 40, 48, 60)
                                    if rules["min"] <= x <= rules["max"]]
    rows = []
    for racks_unit in (1, 2):
        for mpr in candidates:
            mod_unit = mpr * racks_unit
            online = max(1, math.ceil(modules_required / mod_unit))
            flux_opt = flux_model(feed_flow, online * mod_unit, module_area_m2, cl0)["op_flux_gfd"]
            rows.append([online, 0, online + 1, 1, mpr, racks_unit, mod_unit,
                         online * mod_unit, (online + 1) * mod_unit,
                         round(flux_opt, 1), online * mod_unit - modules_required])
    config_df = pd.DataFrame(rows, columns=[
        "Online Units", "Standby Units", "Total Units", "Max Offline BW/CEB",
        "Modules/Rack", unit_label, "Modules/Unit", "Online Modules",
        "Total Modules", "Flux (gfd)", "Spare Modules vs Design"])
    config_df = config_df.sort_values(["Total Modules", "Online Units"]).head(12)

    with card(f"Recommended Configurations - {module_name or 'selected module'}", "⭐"):
        st.caption(f"Based on {modules_required} modules required by the Design section "
                   f"(1 redundant unit for BW/CEB).")
        show_df(config_df, hide_index=True)

    # ---- UF recovery (water balance: strainer + backwash + forward flush + CEB) ----
    cl = compute_cleaning(mods_unit=modules_per_unit, online_units=online_units, total_units=total_units)
    strainer_loss = feed_flow * (1 - float(ss.get("strainer_recovery", 100.0)) / 100)
    bw_loss_per_hr = cl["bw"]["loss_hr"]
    ff_loss_per_hr = cl["bw"]["ff_loss_hr"]
    ceb_loss_per_hr = cl["ceb"]["loss_per_hr"]
    waste_flow = strainer_loss + bw_loss_per_hr + ff_loss_per_hr + ceb_loss_per_hr
    gross_permeate = feed_flow - strainer_loss - ff_loss_per_hr - cl["ceb"]["ff_loss_hr"]
    net_permeate = feed_flow - waste_flow
    uf_recovery = max(0, min(99.9, (net_permeate / feed_flow) * 100))

    with card("Results", "📈"):
        tiles([("UF recovery", f"{uf_recovery:.1f} %"), ("Net permeate", f"{net_permeate:.1f} m³/hr"),
               ("Gross permeate", f"{gross_permeate:.1f} m³/hr"), ("Waste (strainer+BW+FF+CEB)", f"{waste_flow:.2f} m³/hr"),
               ("Backwash flow", f"{backwash_flow:.1f} m³/hr"),
               ("CIP flow", f"{cip_flow:.1f} m³/hr"), ("Operating trains", trains_online),
               ("Standby trains", standby_trains), ("Total trains", total_trains),
               ("Modules / train", math.ceil(modules_required / trains_online))])

    check_box = st.container()          # design check goes BELOW the configuration cards
    with check_box:
        render_design_check(design_check(live={
            "online_modules": online_modules, "total_modules": total_modules, "uf_recovery_calc": uf_recovery,
            "uf_recovery_input": uf_recovery_input, "cfg_online_units": online_units,
            "cfg_standby_units": standby_units, "cfg_redundant_units": redundant_units,
            "trains_online": trains_online, "standby_trains": standby_trains}))

    ss.update({
        "uf_recovery": uf_recovery_input, "uf_recovery_calc": uf_recovery,
        "uf_trains_online": trains_online, "uf_trains_standby": standby_trains,
        "uf_modules_per_train": modules_per_unit,
        "uf_backwash_flow": backwash_flow, "uf_cip_flow": cip_flow,
        "online_modules": online_modules, "total_modules": total_modules,
        "operating_flux_gfd": operating_flux_gfd, "unit_availability": cl["avail"]["A"],
        "gross_permeate": gross_permeate,
        "cfg_modules_per_rack": modules_per_rack, "cfg_standby_option": standby_option,
    })


def view_uf_backwash():
    page_title("🔄 UF · Backwash")
    uf_strip()

    c1, c2, c3 = st.columns(3)
    with c1:
        with card("Backwash Temperature", "🌡"):
            w_number("Temperature (°F)", "bw_temperature", 66.0)
            w_check("Use design temperature from feed water", "bw_use_design_temp", True)
    with c2:
        with card("Water Source", "🚰"):
            w_select("Backwash Water Source", ["UF Filtrate", "RO Permeate (external)"], "bw_source")
            w_select("Forward Flush Water Source", ["UF Filtrate", "RO Permeate (external)"], "ff_source")
    with c3:
        with card("Backwash Protocol", "📜"):
            w_select("Protocol", ["Normal Protocol", "Short Protocol"], "bw_protocol")

    with card("Backwash Oxidant", "🧴"):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: oxidant_on = w_toggle("Oxidant", "oxidant_enabled", False)
        with c2:
            w_select("Chemical", ["Sodium Hypochlorite", "Hydrogen Peroxide", "Chloramine"],
                     "bw_oxidant_chem", disabled=not oxidant_on)
        with c3: w_number("mg/L", "bw_oxidant_dose", 0.0, disabled=not oxidant_on)

    sel = ss.get("selected_module_data", {})
    air_off = bool(sel) and sel.get("verified", True) and sel.get("air_flow", 1) == 0
    ff_off = bool(sel) and sel.get("verified", True) and sel.get("forward_flush", 1) == 0

    def dur(label, key, default, off=False):
        if off:
            return st.number_input(label, value=0.0, disabled=True, key=key + "_off")
        return w_number(label, key, float(default))

    with card("Durations (seconds)", "⏱"):
        if sel:
            st.caption(f"Module: {ss.get('selected_module', '')}"
                       + ("  |  no air scour for this module" if air_off else "")
                       + ("  |  no forward flush for this module" if ff_off else ""))
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            dur("Filtrate to Level (sec)", "bw_filtrate_to_level", 0.0)
            dur("Bottom Backwash (sec)", "bw_bottom_backwash", 30.0)
        with d2:
            dur("Air Scour (sec)", "bw_air_scour", 20.0, air_off)
            dur("Forward Flush (sec)", "bw_forward_flush", 45.0, ff_off)
        with d3:
            dur("Drain (sec)", "bw_drain", 30.0)
            dur("Lumen Fill (sec)", "bw_lumen_fill", 0.0)
        with d4:
            dur("Top Backwash (sec)", "bw_top_backwash", 30.0)
            w_number("Backwashes Between Air Scour", "bw_between_air_scour", 1, min_value=0)

    cl = compute_cleaning()
    u, b = cl["unit"], cl["bw"]
    with card("Unit Hydraulics (one unit)", "💧"):
        tiles([("Backwash flow", f"{u['bw_flow']:.1f} m³/hr · {u['bw_flow'] * 4.4029:.0f} gpm"),
               ("Backwash water / event", f"{b['event_vol']:.2f} m³"),
               ("Backwash water loss (all online units)", f"{b['loss_hr']:.2f} m³/hr"),
               ("Forward flush flow", f"{u['ff_flow']:.1f} m³/hr · {u['ff_flow'] * 4.4029:.0f} gpm"),
               ("Air scour flow", f"{u['air_scfm']:.0f} scfm"),
               ("Backwash sequence time", f"{cl['avail']['t_bw_s'] / 60:.1f} min"),
               ("Backwash cycles / hr / unit", f"{cl['avail']['cycles_hr']:.2f}"),
               ("Filtering time (unit availability)", f"{cl['avail']['A'] * 100:.1f} %")])


def view_uf_ceb():
    page_title("🧪 UF · CEB")
    uf_strip()

    c1, c2 = st.columns(2)
    with c1:
        with card("CEB Temperature", "🌡"):
            use_feed_t = w_check("Use design temperature from feed water", "ceb_use_feed_temp", True)
            if use_feed_t:
                ss["ui_view_ceb_temp"] = float(ss.get("temperature", 25.0)) * 1.8 + 32
                st.number_input("Temperature (°F)", key="ui_view_ceb_temp", disabled=True)
            else:
                w_number("Temperature (°F)", "ceb_temperature", 66.0)
            st.caption("Used for the hydroxide needed at the target pH (Kw changes with temperature).")
    with c2:
        with card("Water Source", "🚰"):
            w_select("CEB Water Source", ["UF Filtrate", "RO Permeate"], "ceb_water_source")

    acid_col, alk_col, dis_col = st.columns(3)
    with acid_col:
        with card("Acid CEB", "🧪"):
            mineral_on = w_toggle("Mineral Acid", "mineral_acid_enabled", True)
            w_select("Acid", ["HCl(32)", "H2SO4(98)"], "acid_type", disabled=not mineral_on)
            w_number("Target pH", "acid_ph", 2.0, min_value=2.0, max_value=7.0, disabled=not mineral_on)
            organic_on = w_toggle("Organic Acid", "organic_acid_enabled", False)
            organic_acid = w_select("Organic Chemical", ["Citric Acid 100", "Oxalic Acid 100"],
                                    "organic_acid", disabled=not organic_on)
            if organic_acid == "Citric Acid 100":
                w_number("Citric Acid Dose (mg/L)", "citric_dose", 20000.0, disabled=not organic_on)
            else:
                w_number("Oxalic Acid Dose (mg/L)", "oxalic_dose", 10000.0, disabled=not organic_on)
    with alk_col:
        with card("Alkali / Oxidant CEB", "🧫"):
            alkali_on = w_toggle("Alkali", "alkali_enabled", True)
            w_select("Alkali", ["NaOH(50)"], "alkali_type", disabled=not alkali_on)
            w_number("Target pH", "alkali_ph", 12.0, min_value=7.0, max_value=12.0, disabled=not alkali_on)
            ox_on = w_toggle("Oxidant", "alkali_oxidant_enabled", True)
            w_select("Oxidant Type", ["NaOCl(12)"], "oxidant_type", disabled=not ox_on)
            w_number("Oxidant Dose (mg/L)", "oxidant_dose", 350.0, min_value=0.0, disabled=not ox_on)
            w_number("LSI", "ceb_lsi", 0.0)
    with dis_col:
        with card("Disinfection CEB", "🦠"):
            dis_on = w_toggle("Oxidant", "disinfection_enabled", False)
            w_select("Chemical", ["NaOCl", "Chlorine Dioxide", "Peroxide"], "disinfection_chemical",
                     disabled=not dis_on)
            w_number("Dose (mg/L)", "disinfection_dose", 0.0, disabled=not dis_on)

    cl = compute_cleaning()
    u, ceb = cl["unit"], cl["ceb"]
    dem = ceb["demand"]

    with card("CEB Chemical Consumption (one unit cleaned at a time)", "⚗️"):
        tiles([("CEB flow / unit", f"{u['ceb_flow']:.1f} m³/hr · {u['ceb_flow'] * 4.4029:.0f} gpm"),
               ("Feed alkalinity", f"{dem['alk_feed_caco3']:.1f} mg/L CaCO3"),
               ("Acid demand", f"{dem['acid_meq']:.2f} meq/L = {dem['acid_h_meq']:.2f} (pH {float(cv('acid_ph')):.1f}) "
                               f"+ {max(dem['acid_meq'] - dem['acid_h_meq'], 0):.2f} alkalinity"),
               ("Base demand", f"{dem['base_meq']:.2f} meq/L = {dem['base_oh_meq']:.2f} (pH {float(cv('alkali_ph')):.1f}, "
                               f"{ceb['temp_c'] * 1.8 + 32:.0f} °F) + {max(dem['base_meq'] - dem['base_oh_meq'], 0):.2f} carbonate"),
               ("Water per CEB event", f"{ceb['event_vol']:.2f} m³"),
               ("CEB water loss", f"{ceb['loss_per_hr']:.2f} m³/hr"),
               ("Unit offline per CEB", f"{cl['avail']['t_ceb_s'] / 60:.1f} min")])
        if ceb["rows"]:
            show_df(pd.DataFrame([{
                "Step": r["step"], "Chemical": r["chem"], "Dose (mg/L, 100%)": round(r["dose"]),
                "Feed rate while dosing": amt(r["kg_h"], r["gal_h"], True),
                "Per CEB (one unit)": amt(r["kg_event"], r["gal_event"]),
                "Per month (all units)": amt(r["kg_month"], r["gal_month"]),
            } for r in ceb["rows"]]), hide_index=True)
        else:
            st.info("No CEB chemical is switched on.")
        if not ceb["enabled"]:
            st.info("UF Special Features is 'mini-CIP only' - no CEB events are counted in the water balance.")
        st.caption("Doses are 100 % chemical and follow the Target pH set above. Water per CEB = chemical backwash + "
                   "rinse + forward flush (soaking uses no water). Monthly amounts assume every online unit is "
                   "cleaned at the acid / alkali CEB intervals set on the Design page.")

    with card("Duration", "⏱"):
        same_as_bw = w_check("Same as Backwash", "ceb_same_as_backwash", False)

        def ceb_dur(label, key, bw_key, bw_default, own_default):
            if same_as_bw:
                ss["ui_view_" + key] = float(ss.get(bw_key, bw_default))
                return st.number_input(label, key="ui_view_" + key, disabled=True)
            return w_number(label, key, float(own_default))

        d1, d2, d3, d4, d5 = st.columns(5)
        with d1:
            ceb_dur("Air Scour (sec)", "ceb_air_scour", "bw_air_scour", 20.0, 20.0)
            w_number("Soak (min)", "chemical_soak", 10.0)
        with d2:
            ceb_dur("Drain (sec)", "ceb_drain", "bw_drain", 30.0, 30.0)
            w_number("BW Rinse Drain Bottom (sec)", "bw_rinse_bottom", 0.0)
        with d3:
            ceb_dur("Top Backwash (sec)", "ceb_top_bw", "bw_top_backwash", 30.0, 45.0)
            w_number("BW Rinse Drain Top (sec)", "bw_rinse_top", 0.0)
        with d4:
            ceb_dur("Bottom Backwash (sec)", "ceb_bottom_bw", "bw_bottom_backwash", 30.0, 45.0)
        with d5:
            ceb_dur("Forward Flush (sec)", "ceb_forward_flush", "bw_forward_flush", 45.0, 45.0)


def view_uf_cip():
    page_title("🧼 UF · CIP")
    uf_strip()

    c1, c2, c3 = st.columns(3)
    with c1:
        with card("CIP Temperature", "🌡"):
            w_number("Recycle Temperature (°F)", "cip_temperature", 95.0, min_value=66.0, max_value=104.0)
        with card("Water Source", "🚰"):
            w_select("CIP Water Source", ["UF Filtrate", "RO Permeate"], "cip_water_source")
    with c2:
        with card("Cycles", "🔁"):
            w_number("Initial BW Cycles", "cip_initial_bw_cycles", 2, min_value=1, max_value=10)
            w_number("Rinse/Soak Cycles", "cip_rinse_soak_cycles", 1, min_value=1, max_value=10)
            w_number("Rinse BW Cycles", "cip_rinse_bw_cycles", 1, min_value=1, max_value=10)
    with c3:
        with card("CIP Tank", "💧"):
            md_sel = ss.get("selected_module_data", {}) or {}
            w_number("Module volume (L/module)", module_volume_key(),
                     round(float(md_sel.get("area", 77.0)) * 0.688, 1), min_value=0.1)
            tiles([("Tank size factor", f"{float(ss.get('cip_tank_factor', 200.0)):.0f} % of module volume"),
                   ("CIP interval", f"{float(ss.get('uf_cip_interval', 30.0)):.0f} days")])
            st.caption("Enter the vendor's module volume. The default is an estimate (0.688 L per m² of membrane). "
                       "The tank size factor is set under Additional Settings.")

    acid_col, alk_col = st.columns(2)
    with acid_col:
        with card("Acid CIP", "🧪"):
            mineral_on = w_toggle("Mineral Acid", "cip_mineral_acid_enabled", True)
            w_select("Acid", ["HCl(32)", "H2SO4(98)"], "cip_acid_type", disabled=not mineral_on)
            w_number("Target pH", "cip_acid_ph", 2.0, min_value=2.0, max_value=7.0, disabled=not mineral_on)
            organic_on = w_toggle("Organic Acid", "cip_organic_acid_enabled", False)
            organic_acid = w_select("Organic Acid", ["Citric Acid", "Oxalic Acid"], "cip_organic_acid",
                                    disabled=not organic_on)
            if organic_acid == "Citric Acid":
                w_number("Citric Acid Dose (mg/L)", "cip_citric_dose", 20000.0, disabled=not organic_on)
            else:
                w_number("Oxalic Acid Dose (mg/L)", "cip_oxalic_dose", 10000.0, disabled=not organic_on)
    with alk_col:
        with card("Alkali / Oxidant CIP", "🧫"):
            alkali_on = w_toggle("Alkali", "cip_alkali_enabled", True)
            w_select("Alkali", ["NaOH(50)"], "cip_alkali_type", disabled=not alkali_on)
            w_number("Target pH", "cip_alkali_ph", 12.0, min_value=7.0, max_value=12.0, disabled=not alkali_on)
            ox_on = w_toggle("Oxidant", "cip_oxidant_enabled", True)
            w_select("Oxidant", ["NaOCl(12)"], "cip_oxidant_type", disabled=not ox_on)
            w_number("Oxidant Dose (mg/L)", "cip_oxidant_dose", 2000.0, min_value=0.0, max_value=2500.0,
                     disabled=not ox_on)
            w_number("LSI", "cip_lsi", 0.0)

    cl = compute_cleaning()
    cip, u = cl["cip"], cl["unit"]
    with card("CIP Tank & Chemical Consumption (one unit cleaned at a time)", "🧴"):
        tiles([("CIP tank volume", f"{cip['tank_gal']:,.0f} gal · {cip['tank_l']:,.0f} L"),
               ("CIP flow / unit", f"{u['cip_flow']:.1f} m³/hr · {u['cip_flow'] * 4.4029:.0f} gpm"),
               ("Tank turnover", f"{cip['turnover_min']:.1f} min"),
               ("Chemical solution / CIP", f"{cip['solution_vol']:.2f} m³ ({cip['steps']} step"
                                           f"{'s' if cip['steps'] != 1 else ''})"),
               ("Backwash water / CIP", f"{cip['bw_vol']:.2f} m³"),
               ("Heat-up", f"+{cip['d_t']:.1f} °C · {cip['heater_kwh']:.1f} kWh / CIP"),
               ("CIP duration", f"{float(ss.get('cfg_cip_duration', 4.0)):.1f} hr"),
               ("CIPs / month (all units)", f"{cip['events_month']:.2f}")])
        if cip["rows"]:
            show_df(pd.DataFrame([{
                "Step": r["step"], "Chemical": r["chem"], "Dose (mg/L, 100%)": round(r["dose"]),
                "Per CIP (one unit)": amt(r["kg_event"], r["gal_event"]),
                "Per month (all units)": amt(r["kg_month"], r["gal_month"]),
            } for r in cip["rows"]]), hide_index=True)
        else:
            st.info("No CIP chemical is switched on.")
        st.caption("Tank volume = modules per unit × module volume × tank size factor. Acid and alkali doses follow the "
                   "Target pH and the feed alkalinity. Heat-up is from the feed temperature to the CIP recycle "
                   "temperature. Every unit is assumed to be cleaned once per CIP interval. "
                   "Rinse/soak water is not included.")


def view_uf_additional():
    page_title("🛠 UF · Additional Settings")
    uf_strip()

    def sv(label, key, default, as_int=False):
        return w_number(label, key, int(default) if as_int else float(default))

    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        with card("Pressure", "🔧"):
            sv("Average Air Scour Pressure (psi)", "avg_air_pressure", 7.25)
            sv("Maximum Process Air Pressure (psi)", "max_air_pressure", 0.0)
            filtrate_pressure = sv("Filtrate Pressure (psi)", "filtrate_pressure", 0.0)
            filtration_piping_dp = sv("Filtration Piping ΔP (psi)", "filtration_piping_dp", 1.45)
            strainer_dp = sv("Strainer ΔP (psi)", "strainer_dp", 0.0)
            bw_piping_dp = sv("Backwash Piping ΔP (psi)", "bw_piping_dp", 4.35)
            cip_piping_dp = sv("CIP Piping ΔP (psi)", "cip_piping_dp", 21.76)
    with c2:
        with card("Tank Storage & Strainer", "🛢"):
            sv("Chemical Storage Time (Days)", "chemical_storage_time", 30.0)
            sv("BW Only Tank Refill Rate (% of filtrate)", "bw_refill_rate", 0.0)
            sv("BW + Filtrate Tank Size (%)", "bw_filtrate_factor", 100.0)
            sv("BW Only Tank Size (%)", "bw_only_factor", 100.0)
            sv("CIP Tank (% of module volume)", "cip_tank_factor", 200.0)
            sv("Strainer Recovery (%)", "strainer_recovery", 100.0)
            sv("Strainer Size (µm)", "strainer_size", 150.0)
            sv("TOC Rejection (%)", "TOC_rejection", 0.0)
    with c3:
        with card("Power & Timings", "⚡"):
            sv("PLC Power per Train (hp)", "plc_power", 0.09)
            sv("Valve Power per Valve (hp)", "valve_power", 0.0)
            sv("Valves per Unit", "valves_per_unit", 6, as_int=True)
            sv("Valve Open/Close Duration (sec)", "valve_open_close", 5.0)
            sv("Typical Wait Duration (sec)", "typical_wait", 0.0)
            sv("Typical Pump Ramp (sec)", "pump_ramp", 0.0)

    with card("Filtration TMP Increase Between Processes", "📈"):
        t1, t2, t3, t4, t5 = st.columns(5)
        with t1: sv("Backwash", "bw_tmp", 0.0)
        with t2: sv("Acid CEB", "acid_ceb_tmp", 0.0)
        with t3: sv("Mini-CIP", "mini_cip_tmp", 0.0)
        with t4: sv("Alkali CEB", "alk_ceb_tmp", 0.0)
        with t5: sv("CIP", "cip_tmp", 0.0)

    with card("Pump Pressures", "🔩"):
        pp1, pp2, pp3 = st.columns(3)
        with pp1: feed_tmp = sv("Feed TMP (psi)", "feed_tmp", 8.0)
        with pp2: bw_module_pressure = sv("Backwash Module Pressure (psi)", "bw_module_pressure", 10.0)
        with pp3: cip_module_pressure = sv("CIP Module Pressure (psi)", "cip_module_pressure", 5.0)

    feed_pump_psi = feed_tmp + filtration_piping_dp + strainer_dp + filtrate_pressure
    backwash_pump_psi = bw_module_pressure + bw_piping_dp
    cip_pump_psi = cip_module_pressure + cip_piping_dp

    feed_head_ft = feed_pump_psi * 2.31
    bw_head_ft = backwash_pump_psi * 2.31
    cip_head_ft = cip_pump_psi * 2.31

    # Pumps are sized for the MAXIMUM flow (as WAVE does), and the BW / CIP pumps serve ONE unit:
    #   feed pump     = design flux x online membrane area   (never less than the average feed flow)
    #   backwash pump = larger of the BW and CEB flow of one unit
    #   CIP pump      = recycle flow of one unit
    cl = compute_cleaning()
    u = cl["unit"]
    md_area = float((ss.get("selected_module_data") or {}).get("area", 77.0))
    on_mod = int(ss.get("online_modules", 0) or 0)
    d_flux = float(ss.get("uf_flux_gfd", 0) or 0)
    avg_feed_gpm = ss["uf_feed_flow"] * 4.4029
    design_feed_gpm = d_flux * on_mod * md_area * 10.764 / 1440 if (on_mod and d_flux) else 0.0
    feed_flow_gpm = max(avg_feed_gpm, design_feed_gpm)
    bw_gpm, ceb_gpm = u["bw_flow"] * 4.4029, u["ceb_flow"] * 4.4029
    bw_flow_gpm = max(bw_gpm, ceb_gpm)
    cip_flow_gpm = u["cip_flow"] * 4.4029

    pump_efficiency = 0.70
    feed_hp = feed_flow_gpm * feed_head_ft / (3960 * pump_efficiency)
    bw_hp = bw_flow_gpm * bw_head_ft / (3960 * pump_efficiency)
    cip_hp = cip_flow_gpm * cip_head_ft / (3960 * pump_efficiency)

    ss.update({
        "feed_pump_psi": feed_pump_psi, "backwash_pump_psi": backwash_pump_psi, "cip_pump_psi": cip_pump_psi,
        "feed_pump_head_ft": feed_head_ft, "bw_pump_head_ft": bw_head_ft, "cip_pump_head_ft": cip_head_ft,
        "feed_pump_hp": feed_hp, "bw_pump_hp": bw_hp, "cip_pump_hp": cip_hp,
        "feed_pump_gpm": feed_flow_gpm, "bw_pump_gpm": bw_flow_gpm, "cip_pump_gpm": cip_flow_gpm,
    })

    with card("Pump Sizing Summary", "📋"):
        sub("Feed pump")
        tiles([("Pressure", f"{feed_pump_psi:.1f} psi"), ("Head", f"{feed_head_ft:.1f} ft"),
               ("Max flow (design flux × online area)", f"{feed_flow_gpm:.0f} gpm"),
               ("Average feed flow", f"{avg_feed_gpm:.0f} gpm"), ("Power", f"{feed_hp:.2f} hp")])
        sub("Backwash pump")
        tiles([("Pressure", f"{backwash_pump_psi:.1f} psi"), ("Head", f"{bw_head_ft:.1f} ft"),
               ("BW / CEB flow (one unit)", f"{bw_gpm:.0f} / {ceb_gpm:.0f} gpm"), ("Power", f"{bw_hp:.2f} hp")])
        sub("CIP pump")
        tiles([("Pressure", f"{cip_pump_psi:.1f} psi"), ("Head", f"{cip_head_ft:.1f} ft"),
               ("Flow (one unit)", f"{cip_flow_gpm:.0f} gpm"), ("Power", f"{cip_hp:.2f} hp")])
        st.caption(f"Backwash and CIP pumps serve one unit of {u['modules']} modules, so their flow scales with the "
                   f"modules per unit set on the Configuration page.")


# =====================================================
# VIEW: REPORT
# =====================================================
def view_report():
    page_title("📄 Report")
    g = ss.get
    feed, perm = compute_permeate()

    with card("Get Report", "🖨"):
        c = st.columns([1.3, 1.3, 2])
        try:
            pdf = build_pdf_report()
            with c[0]:
                st.download_button("📄 Download PDF Report", data=pdf,
                                   file_name=f"{_safe_name(g('project_name', 'Project'))}_Report.pdf",
                                   mime="application/pdf", key="ui_report_pdf")
            with c[1]:
                if st.button("💾 Save PDF in project folder", key="ui_pdf_folder"):
                    try:
                        p = project_path().parent / f"{_safe_name(g('project_name'))}_Report.pdf"
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(pdf)
                        st.success(f"Saved: {p}")
                    except OSError as e:
                        st.error(f"Could not save: {e}")
        except Exception as e:
            st.error(f"Could not build the PDF report: {e}")
        st.caption("Open the PDF and print it, or e-mail it. The report always uses the latest values.")

    page_title_effluent = "Effluent"                      # heading for the treated-water (effluent) section
    md(f'<div class="page-h" style="font-size:19px">💧 {page_title_effluent}</div>')
    render_treated_water()

    with card("Design Summary", "📋"):
        sub("Feed water")
        tiles([("TDS", f"{g('calculated_tds', 0):.1f} mg/L"), ("Hardness", f"{g('hardness', 0):.1f} mg/L"),
               ("Alkalinity", f"{g('alkalinity', 0):.1f} mg/L"), ("Conductivity", f"{g('conductivity', 0):.0f} µS/cm"),
               ("Turbidity", f"{g('Turbidity', 0):.2f} NTU"), ("TOC", f"{g('TOC', 0):.1f} mg/L"),
               ("SDI", f"{g('sdi', 0):.1f}"), ("pH", f"{g('feed_ph', 7):.2f}")])
        sub("Effluent (UF permeate)")
        tiles([("Effluent flow (net)", f"{g('uf_feed_flow', 0) * g('uf_recovery_calc', 0) / 100:.1f} m³/hr"),
               ("TDS", f"{g('ufp_tds', 0):.1f} mg/L"), ("Turbidity", f"{g('ufp_turbidity', 0):.3f} NTU"),
               ("TSS", f"{g('ufp_tss', 0):.3f} mg/L"), ("TOC", f"{g('ufp_toc', 0):.2f} mg/L"),
               ("SDI15", f"{g('ufp_sdi', 0):.1f}"), ("pH", f"{g('ufp_ph', 7):.2f}")])
        sub("UF design & configuration")
        tiles([("Vendor", g("uf_vendor_saved", "")), ("Module", g("selected_module", "")),
               ("Feed flow", f"{g('uf_feed_flow', 0):.1f} m³/hr"), ("Total modules", g("total_modules", 0)),
               ("Online / standby / redundant",
                f"{g('cfg_online_units', 0)} / {g('cfg_standby_units', 0)} / {g('cfg_redundant_units', 0)}"),
               ("Racks / unit", g("cfg_racks_per_unit", 0)), ("Modules / rack", g("cfg_modules_per_rack", 0)),
               ("Operating flux", f"{g('operating_flux_gfd', 0):.1f} gfd"),
               ("Recovery", f"{g('uf_recovery_calc', 0):.1f} %")])
        sub("Pumps")
        tiles([("Feed pump", f"{g('feed_pump_psi', 0):.1f} psi"), ("Backwash pump", f"{g('backwash_pump_psi', 0):.1f} psi"),
               ("CIP pump", f"{g('cip_pump_psi', 0):.1f} psi")])
        sub("Backwash")
        tiles([("Backwash flow", f"{g('uf_backwash_flow', 0):.1f} m³/hr"), ("Air scour", f"{g('bw_air_scour', 0)} sec"),
               ("Drain", f"{g('bw_drain', 0)} sec"), ("Forward flush", f"{g('bw_forward_flush', 0)} sec")])
        cl = compute_cleaning()
        sub("CEB chemicals (one unit)")
        tiles([(f"{r['step']} · {r['chem']}", f"{r['dose']:.0f} mg/L · {amt(r['kg_h'], r['gal_h'], True)}")
               for r in cl["ceb"]["rows"]] or [("CEB", "no chemical switched on")])
        sub("CIP")
        tiles([("CIP flow / unit", f"{cl['unit']['cip_flow']:.1f} m³/hr"),
               ("CIP tank", f"{cl['cip']['tank_gal']:,.0f} gal"),
               ("CIP interval", f"{g('uf_cip_interval', 30)} days")]
              + [(f"{r['step']} · {r['chem']}", f"{r['dose']:.0f} mg/L · {amt(r['kg_event'], r['gal_event'])} / CIP")
                 for r in cl["cip"]["rows"]])


# =====================================================
# DISPATCH
# =====================================================
UF_VIEWS = {"Design": view_uf_design, "Configuration": view_uf_configuration, "Backwash": view_uf_backwash,
            "CEB": view_uf_ceb, "CIP": view_uf_cip, "Additional Settings": view_uf_additional}

if main == "Projects":
    view_projects()
elif main == "System Design":
    view_system()
elif main == "Feed":
    view_feed()
elif main == "UF":
    UF_VIEWS[uf_page]()
else:
    view_report()

fill_flow_diagram()          # flow diagram under the page title (every page except System Design, which has its own)


# =====================================================
# AUTO-SAVE TO DISK (every run, writes only when something changed) + HEADER / STATUS
# =====================================================
save_clicked = ss.pop("_save_clicked", False)
autosave_disk = ss.get("autosave_disk", True)

body_hash = hashlib.md5(json.dumps(collect_project(), sort_keys=True, default=str).encode()).hexdigest()
target = str(project_path())
if save_clicked or (autosave_disk and (body_hash != ss.get("_last_hash") or target != ss.get("_last_path"))):
    if save_to_disk() is not None:
        ss["_last_hash"] = body_hash

if ss.get("_disk_error"):
    status_txt = "⚠ not saved to folder"
    side_html = (f'<div class="sb-status">⚠ Cannot write to the projects folder.<br>'
                 f'Use “Download .uff” on the Projects tab.</div>')
    chip_cls = "chip"
else:
    status_txt = f"✅ Auto-saved {ss['_last_saved_at']}" if ss.get("_last_saved_at") else "Auto-save ready"
    side_html = (f'<div class="sb-status"><b>{hesc(str(ss.get("project_name", "")))}</b><br>'
                 f'{status_txt}</div>')
    chip_cls = "chip ok"

_dc = design_check()
design_chip = {"ok": '<div class="chip dgood">✅ Size OK</div>',
               "warn": '<div class="chip dwarn">⚠ Check design</div>',
               "bad": '<div class="chip dbad">❌ Size too small</div>'}.get(_dc["status"], "")
hdr_ph.markdown(
    f'<div class="mdw"><div class="hdr"><div><div class="hdr-title">{APP_TITLE}</div>'
    f'<div class="hdr-sub">UF system design software</div></div>'
    f'</div></div>',
    unsafe_allow_html=True)
side_status.markdown(f'<div class="mdw">{side_html}</div>', unsafe_allow_html=True)
