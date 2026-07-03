#!/bin/zsh
# Collect sweep metrics: ./sweep_collect.sh sw_s090 sw_s085 ...
PY=~/miniforge3/envs/moose-cylinder-equal-val/bin/python
STL=stl_results/CuH04_235.9.stl
printf "%-10s %10s %10s %10s %8s\n" case len_mm foot_mm rear_mm rms_mm
for c in "$@"; do
  [ -f "$c.e" ] || { echo "$c: missing"; continue; }
  $PY rz_profile_compare.py "$c.e" $STL --out "/tmp/$c" 2>/dev/null | awk -v c="$c" '
    /final length/ {len=$3} /foot \(max\) radius/ {foot=$4} /rear radius/ {rear=$3}
    /profile RMS/ {rms=$4}
    END {printf "%-10s %10s %10s %10s %8s\n", c, len, foot, rear, rms}'
done
echo "experiment      22.083      9.061      4.152        -"
