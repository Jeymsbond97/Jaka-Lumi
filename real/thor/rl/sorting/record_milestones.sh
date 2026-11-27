#!/bin/bash
# Records the learning-progress clips of one training run while it trains: at each milestone iteration, once its
# checkpoint is saved, the same close-up (stage 2, one ball, fixed seed), the training curves so far, and from 1000
# on a 16-scene grid (stage 3).
# Usage (from ~/isaaclab-spike, after `. ./env.sh`):  rl/sorting/record_milestones.sh logs/rsl_rl/lumi_sort/<run> [first]
RUN=$1
FROM=${2:-0}                 # a resumed run starts its checkpoints later: skip the milestones before this
PY=$HOME/isaaclab-spike/IsaacLab/.venv/bin/python
REC=$HOME/Dev/lumi-wave/rl/sorting/record_policy.py
for it in 0 100 200 300 500 800 1200 1600 2000 2500 3000 3099; do
  [ "$it" -lt "$FROM" ] && continue
  ck=$RUN/model_$it.pt
  while [ ! -f "$ck" ]; do
    pgrep -f "rl/sorting/[t]rain.py" >/dev/null || { [ -f "$ck" ] || break 2; }
    sleep 60
  done
  sleep 5
  echo "$(date +%H:%M) iteration $it"
  $PY $REC --checkpoint "$ck" --stage 2 --shot close --seconds 20 --viz newton 2>&1 | grep "^recorded"
  $PY $HOME/Dev/lumi-wave/rl/sorting/tb_export.py "$RUN" --tag it$it 2>&1 | grep "^wrote"
  if [ "$it" -ge 1000 ]; then
    $PY $REC --checkpoint "$ck" --stage 3 --shot grid --seconds 20 --viz newton 2>&1 | grep "^recorded"
  fi
done
echo "$(date +%H:%M) done"
