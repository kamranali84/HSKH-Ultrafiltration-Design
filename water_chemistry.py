"""
water_chemistry.py - ion / charge-balance / pH helpers for HSKH Ultrafiltration Design.

Pure Python (no Streamlit), so it can be tested on its own.  Water is a dict of mg/L values using
the same keys as the app:  ca mg na k ammonium ba sr iron manganese  (cations)
                           hco3 co3 so4 cl no3 fluoride              (anions)
                           silica boron                              (weak acids, neutral at feed pH)
"""
from math import log10

# key: (label, type, molar mass g/mol, charge, equivalent conductance S·cm²/eq at 25 °C)
IONS = {
    "ca":         ("Calcium (Ca²⁺)",       "cation", 40.078, 2, 59.5),
    "mg":         ("Magnesium (Mg²⁺)",     "cation", 24.305, 2, 53.1),
    "na":         ("Sodium (Na⁺)",         "cation", 22.990, 1, 50.1),
    "k":          ("Potassium (K⁺)",       "cation", 39.098, 1, 73.5),
    "ammonium":   ("Ammonium (NH₄⁺)",      "cation", 18.039, 1, 73.5),
    "ba":         ("Barium (Ba²⁺)",        "cation", 137.327, 2, 63.6),
    "sr":         ("Strontium (Sr²⁺)",     "cation", 87.620, 2, 59.4),
    "iron":       ("Iron (Fe²⁺)",          "cation", 55.845, 2, 54.0),
    "manganese":  ("Manganese (Mn²⁺)",     "cation", 54.938, 2, 53.5),
    "hco3":       ("Bicarbonate (HCO₃⁻)",  "anion", 61.017, 1, 44.5),
    "co3":        ("Carbonate (CO₃²⁻)",    "anion", 60.009, 2, 69.3),
    "so4":        ("Sulfate (SO₄²⁻)",      "anion", 96.060, 2, 80.0),
    "cl":         ("Chloride (Cl⁻)",       "anion", 35.453, 1, 76.3),
    "no3":        ("Nitrate (NO₃⁻)",       "anion", 62.005, 1, 71.4),
    "fluoride":   ("Fluoride (F⁻)",        "anion", 18.998, 1, 54.4),
}
ION_KEYS = tuple(IONS)

SILICA_MW, SILICA_PKA = 60.084, 9.80      # SiO2 -> HSiO3-
BORON_MW, BORON_PKA = 10.811, 9.24        # B    -> B(OH)4-
AMMONIUM_PKA = 9.25                        # NH4+ <-> NH3

# balancing methods: (cation to add, anion to add) or "hco3"
BALANCE_METHODS = {
    "Na⁺ / Cl⁻  (add salt)": ("na", "cl"),
    "Ca²⁺ / SO₄²⁻  (add gypsum-type ions)": ("ca", "so4"),
    "HCO₃⁻  (adjust bicarbonate)": "hco3",
}


def _f(w, key):
    try:
        return float(w.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def eq_weight(key):
    """mg per meq for an ion."""
    _, _, mw, z, _ = IONS[key]
    return mw / z


def meq_per_l(key, mgl):
    return mgl / eq_weight(key)


def pkw(temp_c=25.0):
    t = temp_c + 273.15
    return 4470.99 / t - 6.0875 + 0.01706 * t


def pk1(temp_c=25.0):
    """First dissociation constant of carbonic acid (H2CO3* <-> H+ + HCO3-)."""
    t = temp_c + 273.15
    return 3404.71 / t + 0.032786 * t - 14.8435


# -----------------------------------------------------
# Charge balance
# -----------------------------------------------------
def analyze(w, ph=7.0, temp_c=25.0):
    """Full ion balance. Returns a dict with meq/L per ion, totals, charge-balance error and
    the derived quantities (TDS, hardness, alkalinity, conductivity, ionic strength)."""
    cations, anions, rows = {}, {}, []

    for key, (label, kind, mw, z, lam) in IONS.items():
        mg_l = _f(w, key)
        meq = mg_l * z / mw
        if key == "ammonium":                       # only NH4+ is charged; NH3 is neutral
            meq *= 1 / (1 + 10 ** (ph - AMMONIUM_PKA))
        (cations if kind == "cation" else anions)[key] = meq
        rows.append((key, label, kind, mg_l, meq))

    # H+ / OH-
    h_meq = 1000 * 10 ** (-ph)
    oh_meq = 1000 * 10 ** (ph - pkw(temp_c))
    cations["h"], anions["oh"] = h_meq, oh_meq
    rows.append(("h", "Hydrogen (H⁺)", "cation", h_meq * 1.008, h_meq))
    rows.append(("oh", "Hydroxide (OH⁻)", "anion", oh_meq * 17.007, oh_meq))

    # weak acids: only the ionised fraction carries charge (matters above pH ~8.5)
    si_frac = 1 / (1 + 10 ** (SILICA_PKA - ph))
    b_frac = 1 / (1 + 10 ** (BORON_PKA - ph))
    anions["silicate"] = _f(w, "silica") / SILICA_MW * si_frac
    anions["borate"] = _f(w, "boron") / BORON_MW * b_frac
    rows.append(("silicate", "Silicate (HSiO₃⁻)", "anion", _f(w, "silica") * si_frac, anions["silicate"]))
    rows.append(("borate", "Borate (B(OH)₄⁻)", "anion", _f(w, "boron") * b_frac, anions["borate"]))

    cat_total = sum(cations.values())
    an_total = sum(anions.values())
    diff = cat_total - an_total
    cbe = diff / (cat_total + an_total) * 100 if (cat_total + an_total) > 0 else 0.0
    status = "OK" if abs(cbe) <= 5 else ("Review" if abs(cbe) <= 10 else "Fail")

    tds = sum(_f(w, k) for k in ION_KEYS) + _f(w, "silica") + _f(w, "boron")
    hardness = _f(w, "ca") * 2.497 + _f(w, "mg") * 4.118                     # mg/L as CaCO3
    alkalinity = (anions["hco3"] + anions["co3"] + oh_meq - h_meq) * 50.04     # mg/L as CaCO3

    # equivalent-conductance estimate (+/- 10 %)
    conductivity = sum(meq * IONS[k][4] for k, meq in {**cations, **anions}.items() if k in IONS)
    conductivity += h_meq * 349.8 + oh_meq * 198.6

    ionic_strength = 0.5 * sum(_f(w, k) / 1000 / IONS[k][2] * IONS[k][3] ** 2 for k in ION_KEYS)

    return {
        "cations": cations, "anions": anions, "rows": rows,
        "cation_total": cat_total, "anion_total": an_total, "diff_meq": diff,
        "cbe_pct": cbe, "status": status,
        "tds": tds, "hardness": hardness, "alkalinity": alkalinity,
        "conductivity": conductivity, "ionic_strength": ionic_strength,
        "h_meq": h_meq, "oh_meq": oh_meq,
    }


def auto_balance(w, ph=7.0, temp_c=25.0, method=None):
    """Return the change (mg/L) needed to make cations = anions.
    {"changes": {key: new_mgl}, "residual_meq": float, "diff_meq": float}"""
    method = method or next(iter(BALANCE_METHODS))
    res = analyze(w, ph, temp_c)
    diff = res["diff_meq"]                 # + = excess cations, - = excess anions
    out = {"changes": {}, "residual_meq": 0.0, "diff_meq": diff, "method": method}
    if abs(diff) < 1e-9:
        return out

    target = BALANCE_METHODS[method]
    if target == "hco3":
        cur = _f(w, "hco3")
        new = max(0.0, cur + diff * eq_weight("hco3"))
        out["changes"]["hco3"] = new
        out["residual_meq"] = diff - (new - cur) / eq_weight("hco3")
    else:
        cation_key, anion_key = target
        if diff > 0:                       # too many cations -> add anion
            out["changes"][anion_key] = _f(w, anion_key) + diff * eq_weight(anion_key)
        else:                              # too many anions  -> add cation
            out["changes"][cation_key] = _f(w, cation_key) - diff * eq_weight(cation_key)
    return out


# -----------------------------------------------------
# pH / carbonate system
# -----------------------------------------------------
def co2_from_ph(hco3_mgl, ph, temp_c=25.0):
    """Free CO2 (mg/L) in equilibrium with HCO3- at a given pH."""
    mol_hco3 = hco3_mgl / 1000 / IONS["hco3"][2]
    return mol_hco3 * 10 ** (pk1(temp_c) - ph) * 44.009 * 1000


def ph_from_co2(hco3_mgl, co2_mgl, temp_c=25.0):
    """pH from HCO3- and free CO2 (None if either is zero)."""
    if hco3_mgl <= 0 or co2_mgl <= 0:
        return None
    mol_hco3 = hco3_mgl / 1000 / IONS["hco3"][2]
    mol_co2 = co2_mgl / 1000 / 44.009
    return pk1(temp_c) + log10(mol_hco3 / mol_co2)


def ph_for_neutrality(w, temp_c=25.0, lo=2.0, hi=12.0):
    """pH at which cations = anions (None when the ions alone cannot be balanced by pH)."""
    f = lambda p: analyze(w, p, temp_c)["diff_meq"]
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


# -----------------------------------------------------
# Cleaning chemistry (CEB / CIP): strong acid / base needed to reach a target pH
# -----------------------------------------------------
def pk2(temp_c=25.0):
    """Second dissociation constant of carbonic acid (HCO3- <-> H+ + CO3 2-)."""
    t = temp_c + 273.15
    return 2902.39 / t + 0.02379 * t - 6.4980


def carbonate_alk_meq(ct_mmol, ph, temp_c=25.0):
    """Carbonate alkalinity (meq/L) of a closed carbonate system with total carbonate ct (mmol/L)."""
    h = 10 ** (-ph)
    k1, k2 = 10 ** (-pk1(temp_c)), 10 ** (-pk2(temp_c))
    d = h * h + k1 * h + k1 * k2
    return ct_mmol * (k1 * h + 2 * k1 * k2) / d


def weak_alk_meq(w, ph):
    """Alkalinity (meq/L) carried by borate, silicate and ammonia at a given pH."""
    borate = _f(w, "boron") / BORON_MW / (1 + 10 ** (BORON_PKA - ph))
    silicate = _f(w, "silica") / SILICA_MW / (1 + 10 ** (SILICA_PKA - ph))
    ammonia = _f(w, "ammonium") / IONS["ammonium"][2] / (1 + 10 ** (AMMONIUM_PKA - ph))   # NH3 is the base
    return borate + silicate + ammonia


def cleaning_demand(w, feed_ph, acid_ph=2.0, base_ph=12.0, temp_c=25.0, feed_temp_c=None):
    """Strong acid and strong base (meq/L = mmol/L) needed to bring the feed/filtrate to a target pH.

    Uses alkalinity balance: acid = Alk(feed) - Alk(acid pH),  base = Alk(base pH) - Alk(feed).
    Total carbonate (HCO3 + CO3 + CO2) is conserved, so:
      * pH 2  : acid = alkalinity + 10 mmol/L H+           (works even when no carbonate is entered)
      * pH 12 : base = HCO3 + 2 x CO2 + 10 mmol/L OH- (+ borate / silicate / ammonia)  - carbonate counts 0
    temp_c = temperature of the cleaning solution (sets Kw: pH 12 needs 10 mmol/L OH- at 25 C but only ~6 at 19 C);
    feed_temp_c = temperature at which the feed pH was measured (defaults to temp_c).
    w needs keys hco3, co3, co2, boron, silica, ammonium (mg/L)."""
    hco3 = _f(w, "hco3") / IONS["hco3"][2]
    co3 = _f(w, "co3") / IONS["co3"][2]
    co2 = _f(w, "co2") / 44.009
    ct = hco3 + co3 + co2

    ft = temp_c if feed_temp_c is None else feed_temp_c

    def oh_minus_h(ph, t):
        return 1000 * (10 ** (ph - pkw(t)) - 10 ** (-ph))

    alk_feed = hco3 + 2 * co3 + weak_alk_meq(w, feed_ph) + oh_minus_h(feed_ph, ft)

    def alk_at(ph):
        return carbonate_alk_meq(ct, ph, temp_c) + weak_alk_meq(w, ph) + oh_minus_h(ph, temp_c)

    return {"acid_meq": max(0.0, alk_feed - alk_at(acid_ph)),
            "base_meq": max(0.0, alk_at(base_ph) - alk_feed),
            "acid_h_meq": 1000 * 10 ** (-acid_ph),                     # free H+ left at the target pH
            "base_oh_meq": 1000 * 10 ** (base_ph - pkw(temp_c)),      # free OH- at the target pH and temperature
            "alk_feed_meq": alk_feed, "alk_feed_caco3": alk_feed * 50.04}


if __name__ == "__main__":
    water = {"ca": 40, "mg": 12, "na": 30, "k": 5, "hco3": 150, "so4": 40, "cl": 40, "no3": 5}
    r = analyze(water, 7.5)
    print(f"cations {r['cation_total']:.3f}  anions {r['anion_total']:.3f}  CBE {r['cbe_pct']:.2f}% ({r['status']})")
    print(f"TDS {r['tds']:.1f}  hardness {r['hardness']:.1f}  alk {r['alkalinity']:.1f}  "
          f"EC {r['conductivity']:.0f}  I {r['ionic_strength']:.4f}")
    b = auto_balance(water, 7.5)
    print("balance:", b["changes"])
    print("CO2 @ pH 7.5:", round(co2_from_ph(150, 7.5), 2), "mg/L")