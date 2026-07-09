#!/usr/bin/env bash
# Timed head-to-head of the 3-D calibrated frictionless slug:
# explicit (reduced integration, central difference, dt = 5e-9)
# vs implicit (full integration + F-bar, Newmark-beta, dt capped at 5e-9).
# Wall times and endpoints are appended to timing_3d_results.txt.
# Run from this directory with the moose env active:
#   ./time_explicit_vs_implicit_3d.sh
set -u
cd "$(dirname "$0")"
RESULTS=timing_3d_results.txt

run_case () {
  local label=$1 input=$2 base=$3
  echo "=== $label ==="
  local t0=$SECONDS
  ../../marlin-opt -i "$input" Outputs/file_base="$base" > "$base.log" 2>&1
  local status=$?
  local wall=$((SECONDS - t0))
  local summary
  summary=$(awk -F, 'END{printf "arrest %.1f us, %d steps", $1*1e6, NR-2}' "$base.csv" 2>/dev/null)
  printf "%s  %-9s exit=%d  wall=%ds  %s\n" "$(date '+%Y-%m-%d %H:%M')" "$label" "$status" "$wall" "$summary" | tee -a "$RESULTS"
}

run_case explicit 3d_slug_thermal_mult_ri.i       3d_explicit_timed
run_case implicit 3d_slug_thermal_mult_implicit.i 3d_implicit_timed
echo "saved to $RESULTS"
