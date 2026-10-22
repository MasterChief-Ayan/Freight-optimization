# data/

Field data lives here **locally only** — `raw/` and `processed/` are in
`.gitignore`, because the files are railway commercial records shared through
the department. Ask your supervisor before putting any of it on a public repository.

    data/
    ├── raw/
    │   └── RR_base_IN_freight_details/      ← extract the RAR here
    │       ├── 2022/ Jan 22.xls … Dec 22.xls
    │       ├── …
    │       └── 2026/ Jan 26.xls … Aug 26.xls
    └── processed/
        └── rr_all.pkl                       ← written by tools/audit_rr_register.py

## What the first dataset is (audited 22-Oct-2026)

**Eastern Railway, Inward Freight Register, RR-base, paid traffic** — the FOIS MIS
export `MisOwtdFrgtRgtr`. Contents:

- 56 monthly files, Jan-2022 to Aug-2026, with **220,733 Railway Receipts (RRs)**.
- 93 columns per file, but the union is 120 because charge heads were added over time.
- **Present:** division, station from/to, RR no. and date, invoice no. and date,
  e-RR and eT-RR flags, traffic type, F/L/I flag, commodity code, consignor and
  consignee, number of 8-wheelers, distance, weight charged/actual, overloading
  weights (POL1/POL2), rate per tonne, basic freight, ~45 "other charge" heads,
  rebates, GST, final freight.
- **Absent:** placement, release and removal timestamps; demurrage and wharfage
  (these are billed at the terminal, not on the RR); hourly time stamps of any kind.
  RR date and invoice date are day-granular only.

So this dataset can calibrate **money, volume, commodity mix, wagon counts and
overloading**. It cannot calibrate **detention hours**. See `docs/PROJECT_STORY.md` §6
for the plan.
