#!/bin/zsh
# Серия роликов по темам 1–2 (решение команды 11:48): строго по одному.
cd ~/KMG-HACKATHON
while kill -0 39300 2>/dev/null; do sleep 5; done
V=.venv/bin/python
$V -m kmg_course video out/bas-4/layer.json bas-4.n-315-bec0ef --format short --template claim_steps > runs/video/bas_close.out 2>&1; echo "bas_close exit $? $(date +%H:%M)"
$V -m kmg_course video out/slatt-9/layer.json slatt-9.n-411-51705f --format long --template claim_steps > runs/video/slatt_facies.out 2>&1; echo "slatt_facies exit $? $(date +%H:%M)"
$V -m kmg_course video out/slatt-9/layer.json slatt-9.n-411-51705f-b --format short --template claim_steps > runs/video/slatt_coarse.out 2>&1; echo "slatt_coarse exit $? $(date +%H:%M)"
