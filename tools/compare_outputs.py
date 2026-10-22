"""Regression check: are two result folders numerically identical?

    python tools/compare_outputs.py  <folder_A>  <folder_B>  [--tol 1e-9]

Compares every CSV present in both folders cell by cell (numbers within
--tol, text exactly). Use it after ANY code change: run the experiments
into a fresh results folder and compare against the last trusted one. If a
change was meant to be "refactor only", every file must report IDENTICAL.
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd


def compare(a_dir, b_dir, tol):
    a = {os.path.basename(p) for p in glob.glob(os.path.join(a_dir, "*.csv"))}
    b = {os.path.basename(p) for p in glob.glob(os.path.join(b_dir, "*.csv"))}
    ok = True
    for name in sorted(a | b):
        if name not in a or name not in b:
            print(f"  MISSING   {name}  (only in {'A' if name in a else 'B'})")
            ok = False
            continue
        x = pd.read_csv(os.path.join(a_dir, name))
        y = pd.read_csv(os.path.join(b_dir, name))
        if x.shape != y.shape or list(x.columns) != list(y.columns):
            print(f"  DIFFERENT {name}  shape/columns {x.shape} vs {y.shape}")
            ok = False
            continue
        worst = 0.0
        same = True
        for c in x.columns:
            if pd.api.types.is_numeric_dtype(x[c]) and pd.api.types.is_numeric_dtype(y[c]):
                diff = np.nanmax(np.abs(x[c].to_numpy(float) - y[c].to_numpy(float))) \
                    if len(x) else 0.0
                both_nan = (x[c].isna() == y[c].isna()).all()
                worst = max(worst, 0.0 if np.isnan(diff) else diff)
                same &= both_nan and (np.isnan(diff) or diff <= tol)
            else:
                same &= x[c].astype(str).equals(y[c].astype(str))
        print(f"  {'IDENTICAL' if same else 'DIFFERENT'} {name:<40} max |diff| = {worst:.3g}")
        ok &= same
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--tol", type=float, default=1e-9)
    args = ap.parse_args()
    good = compare(args.a, args.b, args.tol)
    print("\nRESULT:", "ALL IDENTICAL" if good else "DIFFERENCES FOUND")
    sys.exit(0 if good else 1)
