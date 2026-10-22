"""
rr_register.py  -  load, clean and DECODE the FOIS 'Inward Freight Register (RR-base)'.

    from tools.rr_register import load_register
    d = load_register()                 # cleaned, decoded DataFrame, one row per RR

Source files: monthly FOIS MIS exports 'MisOwtdFrgtRgtr', Eastern Railway, paid
traffic, Jan-2022 .. Aug-2026 (data/raw/RR_base_IN_freight_details/<year>/<Mon YY>.xls[x]).

Cleaning rules (each found during the audit of 22-Oct-2026)
-----------------------------------------------------------
C1  Header is on spreadsheet row 3 (rows 1-2 are a title and a filter line).
C2  Each file ends with sub-total rows ('TOTAL', 'GRAND TOTAL' in STATION FROM,
    blank DVSN). They are not RRs and are dropped (338 rows).
C3  The commodity column was renamed from 'CMDT CODE' to 'CMDT CODE-CODE' in the
    Dec-2024 export; both are merged into `cmdt`.
C4  From Dec-2024 three useful columns appear: WAGON TYPE, RAKE TYPE, SIDING TYPE.
    Earlier months have them blank; for analysis they are back-filled per commodity
    code from the later months where a code maps to one dominant value (>= 90 %).
C5  Charge heads were added over time (93 columns per file, 120 in the union);
    a missing head means 'not levied', so charges are NaN -> 0.

Decoding
--------
Every code table below states MEANING, BASIS (how it was established) and a
CONFIDENCE grade:
    A  confirmed by an official source AND by the data's own arithmetic
    B  confirmed by the data's arithmetic / converging evidence, consistent with
       IR policy, but the FOIS master list itself was not available
    C  plausible reading, needs confirmation from the FOIS code master
The FOIS code masters (commodity, charge head) are not publicly downloadable
(FOIS pages disallow automated access), so B/C items should be confirmed once,
via the PhD students or the FOIS 'Goods Tariff' screen, and this file updated.
"""
import glob
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "RR_base_IN_freight_details")

# ---------------------------------------------------------------------------
# column-level code tables
# ---------------------------------------------------------------------------
TRAFFIC_TYPE = {   # TRFC TYPE  (verified on the cleaned register, 22-Oct-2026)
    "GC": ("coal consigned by Coal India subsidiaries (government coal)", "B",
           "100 % coal codes; consignors ECL/BCCL/CCL/MCL 86 %; consignees DVC/NTPC/WBPDCL/CESC 95 %; "
           "75 % hopper, 96 % private siding, median 116 km"),
    "PC": ("captive / private coal (consignor is the consuming company's own mine)", "B",
           "100 % coal codes; consignor = consignee family (WBPDCL 31 %, SAIL, DVC, NTPC, ADPL); "
           "71 % open BOXN, 18 % via goods sheds, median 233 km"),
    "GG": ("general goods (all non-coal commercial traffic)", "B",
           "cement, clinker, ores, steel, foodgrain, fertiliser, salt; median 20 wagons"),
    "RM": ("railway material (railway's own consignments)", "A",
           "consignee RAIL on 99.1 % of RM RRs (ballast, rails, sleepers)"),
    "ML": ("military", "C", "single RR"),
}
FLI_FLAG = {       # F/L/I FLAG
    "F": ("foreign: originates on another zone, terminates on ER", "B",
          "median lead 418 km; origins outside ER (e.g. BBN Barbil) carry F"),
    "L": ("local: originates and terminates on ER", "B",
          "median lead 127 km; short-lead ECL/BCCL coal to DVC/WBPDCL plants"),
    "I": ("(not present in 2022-26 data)", "-", ""),
}
PAYMENT_MODE = {   # PYMT MODE
    "E": ("electronic payment (e-payment / FOIS e-pay)", "A", "81 % of RRs; EPAYMENT ID present on 99 % of E and 0 % of all other modes"),
    "O": ("other / on-account (credit, freight account)", "C", ""),
    "M": ("manual (cash/cheque/DD at station)", "C", ""),
    "C": ("cash", "C", ""), "L": ("(rare, unknown)", "C", ""),
}
PAID_BY = {"CNSR": "consignor (freight paid at booking)",
           "CNSG": "consignee (freight 'to pay', paid at destination)"}

# ---------------------------------------------------------------------------
# charge heads  (OTHER CHARGE xxx  and  REBATE xxx)
# basis column = what the head is a multiple of, measured on the data
# ---------------------------------------------------------------------------
CHARGE_HEADS = {
    # statutory surcharges -------------------------------------------------
    "DS":   ("development surcharge", "surcharge", "~5 % of freight (median 5.75 % of basic: levied on basic+other); rarely on coal", "B"),
    "DPO":  ("busy season charge (dynamic pricing), general goods", "surcharge", "exactly 15 % of basic; never on coal (coal exempt from 01.10.2022, RailSAHAY)", "A"),
    "DPFG": ("busy season charge, foodgrains", "surcharge", "exactly 15 % of basic; foodgrain codes only", "A"),
    "DPCM": ("busy season charge, chemical manure/fertiliser", "surcharge", "exactly 15 % of basic; fertiliser codes", "B"),
    "DPCN": ("busy season charge, containers", "surcharge", "exactly 10 % of basic; container code only (10 % per RailSAHAY)", "A"),
    "PBA":  ("busy season charge on iron ore (retained for iron ore, RailSAHAY)", "surcharge", "15 % of basic; iron ore only", "B"),
    "MNRK": ("mini-rake supplementary charge", "surcharge", "5 % of basic (5-10 % by distance, RailSAHAY)", "A"),
    "TPRO": ("two-point rake supplementary charge (origin side)", "surcharge", "exactly 5 % of basic", "A"),
    "TPRC": ("two-point rake supplementary charge (combination)", "surcharge", "exactly 5 % of basic", "A"),
    "GWIS": ("surcharge on iron ore, 10 %", "surcharge", "exactly 10 % of basic; iron ore to steel plants", "C"),
    "SFC":  ("supplementary/station facility charge, 5 %", "surcharge", "5 % of basic, rare", "C"),
    "LPO":  ("5 % surcharge, rare", "surcharge", "5 % of basic", "C"),
    "DCS":  ("5 % surcharge, 2022 only", "surcharge", "5 % of basic", "C"),
    "TORC": ("5 % surcharge, rare", "surcharge", "5 % of basic", "C"),
    "RR":   ("20 % surcharge, rare (railway material)", "surcharge", "20 % of basic", "C"),
    "MPRO": ("20 % surcharge, rare (containers)", "surcharge", "20 % of basic", "C"),
    # terminal charges -----------------------------------------------------
    "OTC":  ("terminal charge at originating goods shed/PFT", "terminal", "exactly Rs 20/t (RailSAHAY: Rs 20/t at goods sheds and PFTs)", "A"),
    "DTC":  ("terminal charge at destination goods shed/PFT", "terminal", "exactly Rs 20/t", "A"),
    "OTAC": ("terminal access charge, originating (Gati Shakti / private terminal)", "terminal", "Rs 2,760/wagon = Rs 1.6 lakh per 58-wagon rake; from 2024", "B"),
    "DTAC": ("terminal access charge, destination", "terminal", "Rs 2,760/wagon; from 2024", "B"),
    "TAC":  ("terminal access charge (older head)", "terminal", "Rs 1.6 lakh per rake mode", "B"),
    "TC":   ("terminal/handling charge per wagon (siding-specific)", "terminal", "Rs 150-300/wagon", "C"),
    # siding / haulage (the model's siding_charge) -------------------------
    "SD":   ("siding charge (engine-hour cost x trip time) collected on RR", "siding", "median Rs 1,965/wagon; concentrated at private sidings", "B"),
    "SDCC": ("siding charge, coal sidings (lump)", "siding", "Rs 0.9-13 k/wagon; coal to power sidings", "C"),
    "ENHC": ("engine haulage charge (railway loco working the siding)", "siding", "Rs 266-532/wagon; coal to MTPS/FSTP sidings", "C"),
    "ST":   ("stacking/shunting charge (small, flat Rs 1,000 mode)", "siding", "flat amounts", "C"),
    "BVC":  ("brake-van charge", "siding", "exactly Rs 300/wagon", "C"),
    # punitive -------------------------------------------------------------
    "POL1": ("punitive charge, overloading within tolerance band 1", "punitive", "proportional to WEIGHT POL1 (overload tonnes)", "A"),
    "POL2": ("punitive charge, overloading band 2", "punitive", "proportional to WEIGHT POL2", "A"),
    "POLA": ("punitive charge, overloading (aggregate/additional)", "punitive", "iron ore and coal; scales with overload", "B"),
    "FAUC": ("freight on under-utilised carrying capacity (under-loading charge)", "punitive", "small Rs/t; coal and iron ore", "C"),
    "PCLA": ("congestion levy, originating (per wagon)", "levy", "Rs 150/300/450 per wagon; ore and coal routes", "C"),
    "DCLA": ("congestion levy, destination (per wagon)", "levy", "Rs 150/300 per wagon; from 2024", "C"),
    # demurrage / wharfage collected on the RR (rare) ----------------------
    "DW":   ("demurrage collected on RR", "detention", "multiples of Rs 150 (wagon-hours x 150); 0.3 % of RRs", "B"),
    "DWC":  ("wharfage collected on RR", "detention", "rare", "C"),
}
REBATE_HEADS = {
    "TEFD": ("Traditional Empty Flow Direction concession", "15-20 % off NTR (RailSAHAY); data median 18 %", "A"),
    "STS":  ("Station-to-Station rate concession", "O-D specific (RailSAHAY)", "A"),
    "LBBS": ("long-lead / loyalty discount", "~20 % of basic", "C"),
    "NRS2": ("incremental-traffic rebate scheme, tier 2", "10-12 %", "C"),
    "NRS3": ("incremental-traffic rebate scheme, tier 3", "15-17 %", "C"),
    "NRS4": ("incremental-traffic rebate scheme, tier 4", "23 %", "C"),
    "GR":   ("rebate (round-trip / return-direction tariff, cement & slag)", "up to 60 %", "C"),
    "GR1":  ("rebate tier 1 (same family as GR)", "~29 %", "C"),
    "GR2":  ("rebate tier 2", "~12 %", "C"),
    "FAOC": ("freight adjustment / overcharge refund", "variable", "C"),
    "FIFA": ("rebate on a single commodity code (4011208)", "23-46 %", "C"),
    "DBGC": ("discount, bulk (2022 only)", "17-23 %", "C"),
    "NE":   ("rebate (North-East bound traffic)", "6 %", "C"),
    "SFTO": ("rebate on iron & steel (12 %)", "12 %", "C"),
    "PIWS": ("rebate (rare)", "11 %", "C"),
}

# ---------------------------------------------------------------------------
# commodity groups  (code -> group). Built from converging evidence: freight
# class (CHBL CLASS), wagon type, consignor/consignee, origin, lead.
# ---------------------------------------------------------------------------
COMMODITY_RULES = [
    # (predicate on code string, group, sub-group, evidence, confidence)
    (lambda c: c.startswith("2991"), "COAL", "",
     "class 145A; hopper (BOBRN) + open (BOXN); consignors ECL/BCCL/CCL; consignees DVC, NTPC, WBPDCL, CESC, SAIL", "A"),
    (lambda c: c in {"1011290", "1011292", "1011319", "1421318", "1421317"}, "IRON ORE", "",
     "class 165; open BOXN; origins Barbil (BBN)/Odisha mines, consignor OMC; consignees SAIL/steel plants", "B"),
    (lambda c: c in {"1421968", "1421310"}, "STEEL-PLANT FLUX (limestone/dolomite)", "",
     "class 145; open; to SAIL/steel plants from Sonua/Daltonganj belts", "C"),
    (lambda c: c == "1061110", "MANGANESE ORE", "", "class 145; consignor MOIL/TISCO; to ferro-alloy/steel", "B"),
    (lambda c: c == "3241110", "CLINKER", "",
     "class 140A; open; consignor = consignee cement companies (UTCL, Ambuja, Nuvoco); 813 km from MP/CG belt", "B"),
    (lambda c: c.startswith("2891"), "CEMENT", "", "class 140A; covered BCN; cement companies both ends", "A"),
    (lambda c: c in {"3311292", "4021246"}, "SLAG", "",
     "class 140; open; consignor SAIL/TISCO/JSPL, consignee cement companies", "B"),
    (lambda c: c == "1491114", "GYPSUM", "", "class 150; consignor Paradeep Phosphates; to cement plants", "C"),
    (lambda c: c.startswith("1137") or c.startswith("1190") or c.startswith("1134"), "FOODGRAINS", "",
     "class 130A; covered; consignee FCI / state procurement agencies", "A"),
    (lambda c: c.startswith("4967") or c.startswith("2871"), "FERTILISER", "",
     "class 130A; covered; IFFCO, HURL, MFCL, IDRI, CFL, PPL", "A"),
    (lambda c: c.startswith("2062"), "SALT", "", "class 120A; covered; Gujarat origins (BGK, HRI), 1,300-2,000 km", "B"),
    (lambda c: c.startswith("3443") or c in {"3312746", "3312351", "3312528", "3312433", "3494331"},
     "IRON & STEEL", "", "class 165; flat/open; SAIL, BPSL, JSPL, JSW", "B"),
    (lambda c: c in {"3742520"}, "CONTAINERS", "", "flat; CONCOR, CWC; busy-season 10 % (container rate)", "A"),
    (lambda c: c in {"1421931", "3742909", "3271512"}, "RAILWAY MATERIAL", "",
     "consignee RAIL; traffic type RM; Pakur (ballast) and short-lead flats", "B"),
    (lambda c: c.startswith("2813"), "POL", "", "class 180A; tank wagons; HPCL, BPCL, NRL", "A"),
]


def commodity_group(code) -> tuple:
    if pd.isna(code):
        return ("UNKNOWN", "", "", "-")
    c = str(int(code))
    for pred, grp, sub, ev, conf in COMMODITY_RULES:
        if pred(c):
            return (grp, sub, ev, conf)
    return ("OTHER", "", "", "-")


# wagon type -> free-time row of the MoR Compendium 2.2(a) (loading/unloading, h)
FREE_TIME_BY_WAGON = {
    "OPEN WAGON":    {"load_mech": 5.0, "unload_mech": 7.0, "load_manual": 9.0, "unload_manual": 9.0,
                      "note": "2.2(a); coal/iron ore: loading may be cut to 3:00, unloading to 5:00 (2.2(c)); +1:00 tarpaulin for coal/coke (2.7)"},
    "HOPPER WAGON":  {"load_mech": 5.0, "unload_mech": 2.5, "load_manual": None, "unload_manual": None,
                      "note": "2.2(a) BOBR/BOBRN; Durgapur/IISCO steel plants 4:30-5:30 unloading (2.3)"},
    "COVERED WAGON": {"load_mech": None, "unload_mech": None, "load_manual": 9.0, "unload_manual": 9.0,
                      "note": "2.2(a) manual, by rake size: 1-20 wagons 5:00, 21-30 7:00, 31+ 9:00 (BCNHL 46+ 11:00)"},
    "FLAT WAGON":    {"load_mech": 6.0, "unload_mech": None, "load_manual": 8.0, "unload_manual": 8.0,
                      "note": "2.2(a); containers 3:00 each way (2.2(b)); crane-handled 5-8 h"},
    "TANK WAGON":    {"load_mech": 6.0, "unload_mech": 6.0, "load_manual": None, "unload_manual": None,
                      "note": "2.2(a) non-black oil up to 29 wagons; black oil 7:00; 30+ wagons 8:00/9:00"},
}


# ---------------------------------------------------------------------------
def load_register(base: str = RAW, cache: bool = True) -> pd.DataFrame:
    """Read every monthly file, apply C1-C5, decode, return one row per RR."""
    pk = os.path.join(ROOT, "data", "processed", "rr_clean.pkl")
    if cache and os.path.exists(pk):
        return pd.read_pickle(pk)
    frames = []
    for f in sorted(glob.glob(os.path.join(base, "*", "*.xls*"))):
        df = pd.read_excel(f, header=2)                                  # C1
        df["src_file"] = os.path.relpath(f, base)
        frames.append(df)
    d = pd.concat(frames, ignore_index=True)
    d.columns = [str(c).strip() for c in d.columns]
    d = d[~d["STATION FROM"].astype(str).str.contains("TOTAL")
          & d["DVSN"].notna()].copy()                                    # C2
    d["cmdt"] = d["CMDT CODE"].fillna(d.get("CMDT CODE-CODE")).astype("Int64")   # C3
    d["rr_date"] = pd.to_datetime(d["RR DATE"], errors="coerce")
    d["inv_date"] = pd.to_datetime(d["INVOICE DATE"], errors="coerce")
    money = [c for c in d.columns if c.startswith(("OTHER CHARGE", "REBATE", "GST", "BASIC",
                                                  "TOTAL FRGT", "FINAL FRGT"))]
    d[money] = d[money].apply(pd.to_numeric, errors="coerce").fillna(0.0)   # C5

    g = d["cmdt"].map(lambda c: commodity_group(c)[0])
    d["group"] = g
    d["group_conf"] = d["cmdt"].map(lambda c: commodity_group(c)[3])

    for col in ("WAGON TYPE", "RAKE TYPE", "SIDING TYPE"):                # C4
        if col not in d.columns:
            d[col] = np.nan
        fill = {}
        for code, sub in d.dropna(subset=[col]).groupby("cmdt")[col]:
            vc = sub.value_counts(normalize=True)
            if vc.iloc[0] >= 0.90:
                fill[code] = vc.index[0]
        d[col.lower().replace(" ", "_") + "_filled"] = d[col].fillna(d["cmdt"].map(fill))

    d["wagons"] = pd.to_numeric(d["8-WHLR"], errors="coerce")
    d["tonnes"] = pd.to_numeric(d["WEIGHT ACTL"], errors="coerce")
    d["t_per_wagon"] = d.tonnes / d.wagons
    d["overload_t"] = d["WEIGHT POL1"].fillna(0) + d["WEIGHT POL2"].fillna(0)
    d["overloaded"] = d.overload_t > 0
    d["full_rake"] = d.wagons >= 40
    d["rr_lag_days"] = (d.rr_date - d.inv_date).dt.days
    d["surcharge"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "surcharge")
    d["terminal_chg"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "terminal")
    d["siding_chg"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "siding")
    d["punitive_chg"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "punitive")
    d["levy_chg"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "levy")
    d["detention_chg"] = sum(d.get(f"OTHER CHARGE {k}", 0) for k, v in CHARGE_HEADS.items() if v[1] == "detention")
    if cache:
        os.makedirs(os.path.dirname(pk), exist_ok=True)
        d.to_pickle(pk)
    return d


def code_tables() -> dict:
    """All decoding tables as DataFrames (for the thesis appendix / docs)."""
    return {
        "traffic_type": pd.DataFrame([(k, *v) for k, v in TRAFFIC_TYPE.items()],
                                     columns=["code", "meaning", "confidence", "evidence"]),
        "fli_flag": pd.DataFrame([(k, *v) for k, v in FLI_FLAG.items()],
                                 columns=["code", "meaning", "confidence", "evidence"]),
        "payment_mode": pd.DataFrame([(k, *v) for k, v in PAYMENT_MODE.items()],
                                     columns=["code", "meaning", "confidence", "evidence"]),
        "charge_heads": pd.DataFrame([(k, *v) for k, v in CHARGE_HEADS.items()],
                                     columns=["code", "meaning", "category", "basis_measured", "confidence"]),
        "rebate_heads": pd.DataFrame([(k, *v) for k, v in REBATE_HEADS.items()],
                                     columns=["code", "meaning", "basis_measured", "confidence"]),
        "commodity_rules": pd.DataFrame([(g, ev, cf) for _, g, _, ev, cf in COMMODITY_RULES],
                                        columns=["group", "evidence", "confidence"]),
        "free_time_by_wagon": pd.DataFrame(FREE_TIME_BY_WAGON).T.reset_index().rename(
            columns={"index": "wagon_type"}),
    }
