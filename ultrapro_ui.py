"""
ultrapro_ui.py  -  ONE file: theme + banner + top navigation + vendor database
Put next to your main script, then see the 4 small edits at the bottom.
"""
import streamlit as st
from streamlit_option_menu import option_menu


# =====================================================
# 1. PAGE SETUP  (call FIRST, before any other st.* command)
# =====================================================
def setup_page():
    st.set_page_config(page_title="UltraPRO", page_icon="🔷", layout="wide")


# =====================================================
# 2. THEME
# =====================================================
def apply_theme():
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg,#EAF1FA 0%,#F8FAFD 40%,#FFFFFF 100%); }
    .main .block-container { max-width:1200px; padding-top:1rem; padding-bottom:1rem; }

    .app-banner {
        background: linear-gradient(90deg,#0B2545 0%,#134074 60%,#0A6ED1 100%);
        color:white; padding:18px 28px; border-radius:12px; margin-bottom:14px;
        display:flex; justify-content:space-between; align-items:center;
        box-shadow:0 4px 14px rgba(11,37,69,.25);
    }
    .app-banner h1 { margin:0; font-size:30px; color:white; }
    .app-banner span { font-size:14px; opacity:.85; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background:white; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.06);
    }

    .stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:2px solid #D6E2F0; }
    .stTabs [data-baseweb="tab"] {
        background:#E3ECF7; border-radius:10px 10px 0 0;
        padding:10px 22px; font-weight:600; color:#134074;
    }
    .stTabs [aria-selected="true"] { background:#0A6ED1 !important; color:white !important; }

    [data-testid="stMetric"] {
        background:white; border-left:5px solid #0A6ED1;
        padding:10px 14px; border-radius:8px; box-shadow:0 1px 5px rgba(0,0,0,.08);
    }
    [data-testid="stMetricValue"] { font-size:30px !important; }
    [data-testid="stMetricLabel"] { font-size:16px !important; }

    .stButton>button {
        background:#0A6ED1; color:white; border-radius:8px; border:none;
        font-weight:600; padding:.5rem 1.2rem;
    }
    .stButton>button:hover { background:#134074; color:white; }

    h3 { font-size:24px !important; color:#0B2545; }
    label { font-size:15px !important; font-weight:600 !important; }
    div[data-testid="stNumberInput"], div[data-testid="stSelectbox"] { max-width:260px; }
    div[data-testid="stNumberInput"] input { text-align:center; }

    section[data-testid="stSidebar"] { background:#0B2545; }
    section[data-testid="stSidebar"] * { color:#E8F0FA; }

    #MainMenu, footer { visibility:hidden; }
    </style>
    """, unsafe_allow_html=True)


def banner(title="🔷 UltraPRO", subtitle="Ultrafiltration Design Software"):
    st.markdown(
        f'<div class="app-banner"><h1>{title}</h1><span>{subtitle}</span></div>',
        unsafe_allow_html=True,
    )


# =====================================================
# 3. TOP NAVIGATION
# =====================================================
PAGES = ["Feed Water", "Design", "Configuration", "Backwash", "CEB", "CIP",
         "Additional Settings", "Effluent Water", "Summary"]
ICONS = ["droplet", "diagram-3", "gear", "arrow-repeat", "beaker", "tools",
         "sliders", "droplet-fill", "file-earmark-text"]


def top_nav():
    return option_menu(
        menu_title=None, options=PAGES, icons=ICONS,
        orientation="horizontal", key="page",
        styles={
            "container": {"padding": "4px", "background-color": "#FFFFFF",
                          "border-radius": "12px",
                          "box-shadow": "0 2px 8px rgba(0,0,0,.08)"},
            "icon": {"color": "#0A6ED1", "font-size": "16px"},
            "nav-link": {"font-size": "14px", "font-weight": "600",
                         "margin": "2px", "--hover-color": "#E3ECF7"},
            "nav-link-selected": {"background-color": "#0A6ED1", "color": "white"},
        },
    )


# =====================================================
# 4. VENDOR DATABASE   Vendor -> Technology -> Module
# =====================================================
# verified=True  : process values (flux, backwash, CEB, forward flush, air, CIP)
#                  come from your own DuPont/WAVE data.
# verified=False : geometry/material taken from public manufacturer or regulator
#                  documents (see 'note'); process values are GENERIC placeholders
#                  -> confirm with the manufacturer's design guideline.
CUSTOM_VENDOR = "Other / Custom module"


def _m(area, length, tmp, material, mode, mounting, orient, fid,
       flux, bw, ceb, ff, air, cip, verified=True, note=""):
    return dict(area=area, length=length, tmp=tmp, material=material,
                mode=mode, mounting=mounting, orientation=orient, id=fid,
                flux_gfd=flux, backwash_gfd=bw, ceb_gfd=ceb,
                forward_flush=ff, air_flow=air, cip_recycle=cip,
                verified=verified, note=note)


GENERIC = dict(flux=40.0, bw=60.0, ceb=60.0, ff=0.0, air=0.0, cip=0.0)


def _ds(area, length, material, mode, orient, fid, note, tmp="N/A", mounting="N/A", **over):
    """Datasheet-only module: geometry is sourced, process values are placeholders."""
    p = {**GENERIC, **over}
    return _m(area, length, tmp, material, mode, mounting, orient, fid,
              p["flux"], p["bw"], p["ceb"], p["ff"], p["air"], p["cip"],
              verified=False, note=note)


def _pvdf(area, length, mounting, ff, air, cip, tmp=0.7, fid=0.7):
    return _m(area, length, tmp, "PVDF", "Out-In", mounting, "Vertical",
              fid, 41.23, 58.9, 58.9, ff, air, cip, note="From your DuPont/WAVE data")


def _pes(area, length, mounting, cip, orient="Vertical"):
    return _m(area, length, 1.0, "PESm", "In-Out", mounting, orient,
              0.9, 44.18, 135.474, 70.682, 0.0, 0.0, cip, note="From your DuPont/WAVE data")


VENDORS = {
    "DuPont (IntegraTec / Inge)": {
        "PVDF Out-In": {
            "IntegraTec XP 77 IP":     _pvdf(77, 2491, "Rack", 13.98, 7.61, 6.60),
            "IntegraTec XP 77 IP IG":  _pvdf(77, 2491, "Rack", 13.98, 7.61, 6.60),
            "IntegraTec XP 77":        _pvdf(77, 2363, "Open Platform", 13.98, 7.61, 6.60),
            "IntegraTec XP 77 IG":     _pvdf(77, 2363, "Open Platform", 13.98, 7.61, 6.60),
            "IntegraTec XP 51 IP":     _pvdf(51, 1991, "Rack", 9.26, 7.61, 6.60),
            "IntegraTec XP 51 IP IG":  _pvdf(51, 1991, "Rack", 9.26, 7.61, 6.60),
            "IntegraTec XP 51":        _pvdf(51, 1863, "Open Platform", 9.26, 7.61, 6.60),
            "IntegraTec XP 51 IG":     _pvdf(51, 1863, "Open Platform", 9.26, 7.61, 6.60),
            "IntegraTec XP 52 IC":     _pvdf(52, 2265, "Open Platform", 9.44, 4.44, 4.40),
            "IntegraTec XP 55 UXA":    _pvdf(55, 2332, "Open Platform", 9.98, 3.17, 6.60),
            "IntegraTec XTP 100 IG":   _pvdf(100, 2363, "Open Platform", 18.15, 7.61, 6.60, tmp="N/A", fid=0.6),
            "IntegraTec XTP 100":      _pvdf(100, 2363, "Open Platform", 18.15, 7.61, 6.60, tmp=0.6, fid=0.6),
            "IntegraTec XTP 100 IP":   _pvdf(100, 2491, "Rack", 18.15, 6.34, 6.60, tmp=0.6, fid=0.6),
            "IntegraTec XTP 100 IP IG": _pvdf(100, 2491, "Rack", 18.15, 6.34, 6.60, tmp=0.6, fid=0.6),
        },
        "PES In-Out": {
            "Inge MB 0.9 XL 80 TR":  _pes(80, 2101, "Rack", 8.81),
            "Inge MB 0.9 XL 60 TRs": _pes(60, 1879, "Rack", 6.60),
            "Inge MB 0.9 XL 80 OP":  _pes(80, 1914, "Open Platform", 8.81),
            "Inge MB 0.9 XL 60 OP":  _pes(60, 1679, "Open Platform", 6.60),
            "Inge MB 0.9 XL 38 OP":  _pes(38, 1179, "Open Platform", 4.40),
            "Inge MB 0.9 L 55 V":    _pes(55, 1898, "Open Platform", 6.16),
            "Inge MB 0.9 L 40 HB":   _pes(40, 1527, "Open Platform", 6.16, "Horizontal"),
            "Inge MB 0.9 L 55 H":    _pes(55, 1538, "Open Platform", 6.16, "Horizontal"),
            "Inge MB 0.9 XL 80 TR (Containerized)": _pes(80, 2101, "Rack", 8.81),
        },
    },

    "Toray": {
        "PVDF Out-In": {
            "HFU-2020N": _ds(72, "N/A", "PVDF", "Out-In", "Vertical", "N/A",
                             "Area 72 m2 (775 ft2), pressurized outside-in PVDF. "
                             "Air scour range 2.8-5.3 scfm per module (Toray instruction). "
                             "Air default = midpoint.", air=4.05),
            "HFUG-2020AN": _ds(72, 2160, "PVDF", "Out-In", "Vertical", "N/A",
                               "Area 72 m2 (775 ft2); overall length 2160 mm, dia 216 mm; "
                               "active length 1816 mm (Toray datasheet / TCEQ)."),
            "HFU-1020AN": _ds(29, "N/A", "PVDF", "Out-In", "Vertical", "N/A",
                              "Area 29 m2 (reseller listing of Toray data)."),
            "HFUG-B2315AN": _ds(60, "N/A", "PVDF", "Out-In", "Vertical", "N/A",
                                "Area 60 m2 (reseller listing of Toray data)."),
        },
    },

    "Hydranautics (Nitto)": {
        "PVDF (TIPS) Capillary": {
            "HYDRAcap MAX 40": _ds(52, "N/A", "PVDF (TIPS)", "N/A", "Vertical", "N/A",
                                   "Area 52 m2 (560 ft2). Published flux range 20-65 gfd; "
                                   "max pressure 73 psig; clean at TMP ~30 psi (TSB339). "
                                   "Flux default = range midpoint.", flux=42.5),
            "HYDRAcap MAX 60": _ds(78, "N/A", "PVDF (TIPS)", "N/A", "Vertical", "N/A",
                                   "Area 78 m2 (840 ft2). Published flux range 20-65 gfd; "
                                   "max pressure 73 psig. Flux default = range midpoint.", flux=42.5),
            "HYDRAcap MAX 80": _ds(105, "N/A", "PVDF (TIPS)", "N/A", "Vertical", "N/A",
                                   "Area 105 m2 (1130 ft2). Published flux range 20-65 gfd; "
                                   "max pressure 73 psig. Flux default = range midpoint.", flux=42.5),
        },
    },

    "Pentair X-Flow": {
        "PES In-Out": {
            "XF40 (Xiga 40 / Aquaflex 40)": _ds(40, 1527.5, "PES/PVP", "In-Out", "Vertical", 0.8,
                                                "Area 40 m2, 8 in x 1527.5 mm, 20 nm pore (Pentair)."),
            "XF64": _ds(64, 1537.5, "PES/PVP", "In-Out", "Vertical", 0.77,
                        "Area 64 m2, feed dia 220 mm, length 1537.5 mm (Pentair datasheet)."),
            "HFS60 (silica-tight)": _ds(60, 1540, "PES/mod. PES", "In-Out", "Vertical", 0.8,
                                        "Area 60 m2, 8.7 in x 1.54 m, pH 2-12 (Pentair)."),
            "Aquaflex 55": _ds(55, "N/A", "PES/PVP", "In-Out", "Vertical", "N/A",
                               "Area 55 m2, installed vertically (Pentair brochure)."),
        },
    },

    # Add more from official datasheets, e.g.:
    # VENDORS["Koch"] = {"PVDF Out-In": {"PURON MP ...": _ds(area, length, "PVDF", "Out-In", ...)}}
    # VENDORS["Veolia / SUEZ"] = {...}   # ZeeWeed
}


def _custom_module():
    """Manual entry for any vendor/module that is not in the database."""
    name = st.text_input("Module name", value=st.session_state.get("custom_name", "My module"),
                         key="custom_name")
    area = st.number_input("Membrane area (m²)", min_value=1.0,
                           value=float(st.session_state.get("custom_area", 50.0)), key="custom_area")
    length = st.number_input("Module length (mm)", min_value=0.0,
                             value=float(st.session_state.get("custom_length", 1500.0)),
                             key="custom_length")
    fid = st.number_input("Fiber ID (mm)", min_value=0.0,
                          value=float(st.session_state.get("custom_fid", 0.8)), key="custom_fid")
    tmp = st.number_input("Max TMP (bar)", min_value=0.0,
                          value=float(st.session_state.get("custom_tmp", 1.0)), key="custom_tmp")
    material = st.text_input("Membrane material", value=st.session_state.get("custom_mat", "PVDF"),
                             key="custom_mat")
    mode = st.selectbox("Filtration mode", ["Out-In", "In-Out"], key="custom_mode")
    mounting = st.selectbox("Mounting", ["Rack", "Open Platform"], key="custom_mounting")
    orient = st.selectbox("Orientation", ["Vertical", "Horizontal"], key="custom_orient")
    return _m(area, length, tmp, material, mode, mounting, orient, fid,
              GENERIC["flux"], GENERIC["bw"], GENERIC["ceb"], GENERIC["ff"],
              GENERIC["air"], GENERIC["cip"], verified=False,
              note="User-defined module. Set flux, backwash, CEB, air and CIP values on this page."), name


def vendor_selector():
    """Vendor -> Technology -> Module. Returns (vendor, technology, module, selected_dict)."""
    ss = st.session_state

    vendors = [v for v, t in VENDORS.items() if any(t.values())] + [CUSTOM_VENDOR]
    v_saved = ss.get("uf_vendor_saved", vendors[0])
    vendor = st.selectbox("Vendor", vendors,
                          index=vendors.index(v_saved) if v_saved in vendors else 0)
    ss["uf_vendor_saved"] = vendor

    if vendor == CUSTOM_VENDOR:
        selected, name = _custom_module()
        ss["uf_technology_saved"] = "Custom"
        ss["uf_module_saved"] = name
        st.warning(selected["note"])
        return vendor, "Custom", name, selected

    techs = [t for t, m in VENDORS[vendor].items() if m]
    t_saved = ss.get("uf_technology_saved", techs[0])
    tech = st.selectbox("UF Technology", techs,
                        index=techs.index(t_saved) if t_saved in techs else 0)

    modules = list(VENDORS[vendor][tech].keys())
    m_saved = ss.get("uf_module_saved", modules[0])
    module = st.selectbox("UF Module", modules,
                          index=modules.index(m_saved) if m_saved in modules else 0)

    ss["uf_technology_saved"] = tech
    ss["uf_module_saved"] = module
    selected = VENDORS[vendor][tech][module]

    if not selected.get("verified", True):
        st.warning("Geometry from public datasheets. Flux, backwash, CEB, forward flush, air "
                   "and CIP values are generic placeholders. Confirm with the manufacturer "
                   "before using results.")
    if selected.get("note"):
        st.caption(selected["note"])
    return vendor, tech, module, selected


# =====================================================
# 5. RACK / CONFIGURATION RULES PER VENDOR
# =====================================================
# Used by the Configuration page. 'sizes' = only these modules/rack are allowed.
RACK_RULES = {
    "DuPont (IntegraTec / Inge)": dict(
        min=6, max=22, default=18, sizes=None, verified=True,
        note="IP rack size 6-22 modules (from your DuPont/WAVE setup)."),
    "Hydranautics (Nitto)": dict(
        min=4, max=34, default=8, sizes=[4, 8, 16, 24, 34], verified=True,
        note="HYDRAcube racks: 2 rows x 2/4/8/12/17 modules (Hydranautics brochure, MAX 80 table)."),
}
GENERIC_RACK = dict(
    min=1, max=60, default=12, sizes=None, verified=False,
    note="No published rack limits loaded for this vendor - generic range. "
         "Confirm with the manufacturer.")


def rack_rules(vendor):
    return RACK_RULES.get(vendor, GENERIC_RACK)


# =====================================================
# HOW TO USE IN YOUR MAIN SCRIPT
# =====================================================
# 1) Top of file, right after "import streamlit as st":
#        from ultrapro_ui import (setup_page, apply_theme, banner,
#                                 top_nav, vendor_selector)
#        setup_page()          # remove your old st.set_page_config(...)
#        apply_theme()         # remove your old <style> st.markdown blocks
#
# 2) After the login check:
#        banner()
#        page = top_nav()      # replaces the sidebar option_menu block
#
# 3) In  elif page == "Design":  delete the technology/module dictionaries
#    and selectboxes, and use:
#        vendor, uf_technology, module, selected = vendor_selector()
#    (keep the lines after it that read selected["area"] etc.)
#
# 4) Delete pvdf_module_data and pes_module_data from the main file.