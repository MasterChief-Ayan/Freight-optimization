#!/usr/bin/env bash
# Reproduce every result of the project, in dependency order.
#   bash run_all.sh            full run  (~17 min on a 2-core cloud machine; Layers 5-6 are the slowest)
#   bash run_all.sh quick      integrity checks + calibration report only (~1 min)
# All outputs (charts, CSVs, logs) are written to results/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results

echo ">>> integrity checks (57 in total)"
for m in verify verify_admin verify_trucks verify_optimiser; do
  python3 -m rtsim.$m
done 2>&1 | tee results/verify_all.log

python3 -m rtsim.calibration > results/calibration_report.txt
echo ">>> provenance table -> results/calibration_report.txt"

if [[ "${1:-}" == "quick" ]]; then exit 0; fi

for l in 0 1 2 3 4; do
  echo ">>> Layer $l"
  python3 experiments/run_layer$l.py > results/l$l.log 2>&1
done
echo ">>> decomposition"
python3 experiments/decompose.py > results/decompose.log 2>&1
python3 tools/make_slide_charts.py > /dev/null
echo ">>> Layer 5 (per-parameter sensitivity and bounds)"
python3 experiments/run_layer5_sensitivity.py > results/l5.log 2>&1
if [ -d data/raw/RR_base_IN_freight_details ]; then
  echo ">>> field data (decode + commodity profiles)"
  python3 tools/analyse_rr_register.py > results/field.log 2>&1
fi
echo ">>> Layer 5b (detention for every length of the terminal day)"
python3 experiments/run_layer5b_hours_sweep.py > results/l5b.log 2>&1
echo ">>> Layer 6 (multi-commodity levers)"
python3 experiments/run_layer6_commodities.py > results/l6.log 2>&1
echo ">>> Layer 7 (sufficiency: do conclusions survive omitted factors?)"
python3 experiments/run_layer7_sufficiency.py > results/l7.log 2>&1
echo ">>> extension checks"
python3 tools/verify_extensions.py | tee results/verify_extensions.log
python3 tools/make_prof_charts.py > /dev/null
echo ">>> done - see results/"
