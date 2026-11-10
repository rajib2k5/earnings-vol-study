#!/bin/bash
# usage: run_all.sh  -- runs every data probe on the real reading, then the falsifier (mutated reading of the data)
P=/home/rajib2k5/dev/earnings-vol-study/.venv/bin/python
D=/home/rajib2k5/dev/earnings-vol-study/docs/validation/vx-egv/probes
for spec in "C5 normal" "C5 nodiv" "C6 normal" "C6 shift" "C7 normal" "C7 dmy" "C1C2 normal" "C1C2 shift"; do
  echo "### probe_data.py $spec"; timeout 120 $P -I $D/probe_data.py $spec 2>&1; echo "rc=$?"
done
