# data/

The raw field data **is committed** (`raw/`, 159 MB, 56 files; not confidential, confirmed by
the owner 22-Oct-2026). `processed/` is a regenerable cache and stays in `.gitignore`:
`python tools/analyse_rr_register.py` rebuilds it from `raw/` in about 1 minute.

    data/
    ├── raw/
    │   └── RR_base_IN_freight_details/      ← committed (monthly FOIS exports)
    │       ├── 2022/ Jan 22.xls … Dec 22.xls
    │       ├── …
    │       └── 2026/ Jan 26.xls … Aug 26.xls
    └── processed/                             ← git-ignored, rebuilt automatically
        ├── rr_clean.pkl                     ← cleaned + decoded cache (tools/rr_register.py)
        └── terminal_*.csv                   ← terminal-level detail (tools/analyse_rr_register.py)

## What the first dataset is (audited 22-Oct-2026)

**Eastern Railway, Inward Freight Register, RR-base, paid traffic** — the FOIS MIS
export `MisOwtdFrgtRgtr`. Contents:

- 56 monthly files, Jan-2022 to Aug-2026: **220,395 Railway Receipts (RRs), 508.5 Mt** after removing
  338 sub-total rows ('TOTAL' / 'GRAND TOTAL') that each file carries.
- 93 columns per file, but the union is 120 because charge heads were added over time. From
  Dec-2024 the commodity column is `CMDT CODE-CODE`, and WAGON TYPE, RAKE TYPE and SIDING TYPE appear.
- **Present:** division, station from/to, RR no. and date, invoice no. and date,
  e-RR and eT-RR flags, traffic type, F/L/I flag, commodity code, consignor and
  consignee, number of 8-wheelers, distance, weight charged/actual, overloading
  weights (POL1/POL2), rate per tonne, basic freight, ~45 "other charge" heads,
  rebates, GST, final freight.
- **Absent:** placement, release and removal timestamps; demurrage and wharfage
  (these are billed at the terminal, not on the RR); hourly time stamps of any kind.
  RR date and invoice date are day-granular only.

So this dataset can calibrate **money, volume, commodity mix, wagon type and counts, and
overloading**. It cannot calibrate **detention hours**. Decoding: `tools/rr_register.py`
(confidence-graded code tables); analysis: `tools/analyse_rr_register.py`; findings:
`docs/PROJECT_STORY.md` §6C.
