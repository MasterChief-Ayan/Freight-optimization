#!/usr/bin/env bash
# Reproduce every result of the project, in dependency order.
#   bash run_all.sh            full run  (~6 min on a 2-core cloud machine; Layer 3 is the slowest)
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
echo ">>> done - see results/"
