#!/bin/bash
# Full test suite: engine balance sims + scripted TUI sessions.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== engine simulations =="
for seed in 7 13 42 99; do
    python3 tests/sim.py "$seed" 100 > /dev/null && echo "sim seed $seed ok"
done
echo "== peace pressure mechanics =="
python3 tests/test_peace.py | tail -1
echo "== supply & attrition mechanics =="
python3 tests/test_attrition.py | tail -1
echo "== rivalries, war goals, stability scaling =="
python3 tests/test_rivals.py | tail -1
echo "== TUI: scripted session =="
python3 tests/tui_driver.py | tail -1
echo "== TUI: war & peace flow =="
python3 tests/tui_war.py | tail -1
echo "== TUI: campaign playthrough =="
python3 tests/tui_campaign.py | tail -1
echo "== TUI: fuzz =="
python3 tests/tui_fuzz.py 1 | tail -1
echo "ALL SUITES PASSED"
