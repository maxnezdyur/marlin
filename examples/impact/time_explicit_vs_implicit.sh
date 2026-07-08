#!/usr/bin/env bash
# Timed head-to-head: the calibrated frictionless RZ slug, explicit vs implicit.
# Same mesh, same NEML2 model, same anvil; only the solve strategy differs.
# Run from this directory with the moose env active:
#   ./time_explicit_vs_implicit.sh
set -u
cd "$(dirname "$0")"

echo "=== EXPLICIT: reduced integration + central difference ==="
time ../../marlin-opt -i rz_slug_thermal_mult_ri_calibrated.i \
    Outputs/file_base=rz_explicit_timed > rz_explicit_timed.log 2>&1
awk -F, 'END{printf "  arrest at %.1f us, %d steps\n", $1*1e6, NR-2}' rz_explicit_timed.csv

echo "=== IMPLICIT: full integration + F-bar + Newmark-beta ==="
time ../../marlin-opt -i rz_slug_thermal_mult_implicit.i \
    Outputs/file_base=rz_implicit_timed > rz_implicit_timed.log 2>&1
awk -F, 'END{printf "  arrest at %.1f us, %d steps\n", $1*1e6, NR-2}' rz_implicit_timed.csv
