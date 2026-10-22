"""Step-0 data audit of the RR-base Inward Freight Register (no modelling).

    python tools/audit_rr_register.py  [path/to/"RR base IN freight details"]

Default input folder: data/raw/RR_base_IN_freight_details/  (one sub-folder
per year, one .xls/.xlsx per month, as exported from FOIS MIS).
Writes data/processed/rr_all.pkl (all months stacked, header row 3) and
prints coverage, flags, wagon counts, RR-vs-invoice lag, overloading
incidence, e-RR uptake, commodity/consignee mix and every charge head.
The raw files are NOT committed to git (see .gitignore).
"""
import glob, os, sys, warnings
import pandas as pd
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "data", "raw", "RR_base_IN_freight_details")
OUT = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)
frames = []
for f in sorted(glob.glob(os.path.join(base, "*", "*.xls*"))):
    df = pd.read_excel(f, header=2)
    df["src_file"] = os.path.relpath(f, base)
    frames.append(df)
d = pd.concat(frames, ignore_index=True)
d.columns = [str(c).strip() for c in d.columns]
d.to_pickle(os.path.join(OUT, "rr_all.pkl"))
print("rows", len(d), "files", len(frames), "cols", d.shape[1])
print("columns identical across files:",
      all(list(f.columns) == list(frames[0].columns) for f in frames))
d["RR DATE"] = pd.to_datetime(d["RR DATE"], errors="coerce")
d["INVOICE DATE"] = pd.to_datetime(d["INVOICE DATE"], errors="coerce")
print("RR date range", d["RR DATE"].min(), d["RR DATE"].max())
print("\nF/L/I FLAG\n", d["F/L/I FLAG"].value_counts().to_string())
print("\nTRFC TYPE\n", d["TRFC TYPE"].value_counts().to_string())
print("\nwagons (8-WHLR) describe\n", d["8-WHLR"].describe().round(1).to_string())
d["lag_days"] = (d["RR DATE"] - d["INVOICE DATE"]).dt.days
print("\nRR minus invoice (days) quantiles\n", d["lag_days"].quantile([.05,.25,.5,.75,.95,.99]).to_string())
pol = (d["WEIGHT POL1"].fillna(0) + d["WEIGHT POL2"].fillna(0)) > 0
print(f"\nrecords with overloading (POL1/POL2>0): {pol.mean():.1%}")
print("\ne-RR share by year\n", d.groupby(d["RR DATE"].dt.year)["RR E-RR"].apply(lambda s: (s=="Y").mean()).round(3).to_string())
print("\ntop 10 commodity codes by tonnes\n",
      d.groupby("CMDT CODE")["WEIGHT ACTL"].sum().sort_values(ascending=False).head(10).round(0).to_string())
print("\ntop 10 destination stations by rakes\n", d["STATION TO"].value_counts().head(10).to_string())
print("\ntop 10 consignees by records\n", d["CNSG CODE"].value_counts().head(10).to_string())
oc = [c for c in d.columns if c.startswith("OTHER CHARGE") and c != "OTHER CHARGE TOTAL"]
nz = {c.replace("OTHER CHARGE ",""): ((d[c].fillna(0)!=0).mean(), d[c].fillna(0).sum()/1e7) for c in oc}
print("\nother-charge heads: share of RRs non-zero, total Rs crore")
for k,(a,b) in sorted(nz.items(), key=lambda kv:-kv[1][1]):
    print(f"  {k:6s} {a:6.1%} {b:10.2f}")
print("\ntotals (Rs crore): basic", round(d["BASIC FRGT"].sum()/1e7,1),
      " other", round(d["OTHER CHARGE TOTAL"].sum()/1e7,1),
      " rebate", round(d["REBATE TOTAL"].sum()/1e7,1),
      " final", round(d["FINAL FRGT (incl.SrvcTax/GST)"].sum()/1e7,1))
