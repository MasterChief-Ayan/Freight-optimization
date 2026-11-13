# MTP Part I report (final, 41 pages), Ayan Ahmed 22MF3IM04

Signed by the supervisor on 12-Nov-2026. Built in LaTeX in the format of Ayan's BTP report
(`../btp_format_reference/btp_main.tex`: report class, 12 pt, A4, 1 in margins, Times, 1.5 spacing).

## Files
| File | What it is |
|---|---|
| `main.tex` | title page (dated 12 November 2026), Declaration, Certificate, Acknowledgements (names research scholar Mr. Ranit Senapati), 3-paragraph Abstract, Contents, LoF, LoT, Abbreviations, then `\input` of the chapters |
| `ch1_introduction.tex` | Ch 1 Introduction: 1.1 Background, 1.2 Siding and charging rules (Table 1.1 graded bands), 1.3 Literature review (1.3.1-1.3.5, research gap), 1.4 Problem, 1.5 Objectives, 1.6 Scope, 1.7 Organisation |
| `ch2_modelling.tex` | Ch 2 Modelling: 2.1 approach (Fig 2.1 layers), 2.2 system (Fig 2.2 siding, Table 2.1 M1-M8), 2.3 variable selection (Tables 2.2 filters, 2.3 23 factors), 2.4 field data (Table 2.4 ten commodities), 2.5 formulation (Table 2.5 notation, Eqs 2.1-2.17), 2.6 parameters (Table 2.6), 2.7 experimental design (Table 2.7), 2.8 implementation and verification (Table 2.8) |
| `ch3_results.tex` | Ch 3 Results: 3.1 baseline, 3.2 sources of detention, 3.3 procedural vs capital (Fig 3.1), 3.4 individual effects (Figs 3.2, 3.3), 3.5 materials and labour (Fig 3.4), 3.6 breakdown (Fig 3.5, Tables 3.3-3.4), 3.7 capacity (Fig 3.6, Tables 3.5-3.6), 3.8 wagon damage and locomotive, 3.9 sufficiency (Table 3.8), 3.10 summary (Table 3.9) |
| `ch4_conclusion.tex` | Ch 4: 4.1 findings (7), 4.2 recommendations, 4.3 limitations, 4.4 future work (Part II) |
| `references.tex` | 29 references, all cited |
| `figures/gen_figs.py` | regenerates Figs 3.1-3.6 from `results/`: `python figures/gen_figs.py ../../results` |
| `audit_numbers.py` | checks 122 quoted numbers against `results/`: `python audit_numbers.py ../../results` |
| `MTP1_Report_Final_Ayan_Ahmed.pdf` | the compiled report (current source) |
| `outline/` | heading-only outline (.docx) and its generator (`NODE_PATH=$(npm root -g) node build_outline.js out.docx`) |

Build: `latexmk -pdf main.tex` (or Overleaf, pdfLaTeX, main file `main.tex`).

## Known errata (the printed, signed copy) - fix in the MTP-2 thesis
1. The printed copy said **nine** stress tests; the correct count is **eight** (the ninth row is the model
   as built). Fixed in this source after printing (abstract, Table 2.7, §3.9, §4.1).
2. Abstract: "Procedural levers save about 15.5 times more detention than capital ones" -> should be
   "Digitalising the paperwork saves about 15.5 times more detention than a second line with a second
   crew". Against the best capital lever (50 % faster loading) it is 4.3x (Layer 4) / 4.4x (Layer 7).
3. §2.7: Layers 3/4 line utilisation "about 0.7" -> about 0.8 (line hold 17.9 h / 22 h gap).
4. §4.1 finding 4: money falls faster than time **mainly because the first 8 h are free** (billed hours
   per rake 9.6 -> 2.2, -77 %); the graded bands add only ~1 point (-> -78 %). §3.6.2 states it correctly.
5. Minor: M8 (truck gate) is Erlang, not lognormal (§2.2, §2.5.1); "15 largest sidings" in §2.4 includes
   2 goods sheds; Table 3.8 "All together" combines O1+O2 (+1 h), O4, O5 (not +50 % traffic);
   §3.4 "each extra hour helps less" has one flat step (19->20 h, within noise); §3.5 "pays for every
   material" holds only for the 7 with a published handling rate.
