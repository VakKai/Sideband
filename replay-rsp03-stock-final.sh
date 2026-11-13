#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
out=${1:-replays/rsp03/final-stock}
mkdir -p "$out"
tail -n +2 results/rsp03-final-manifest.csv | while IFS=, read -r obs rest; do
    GR_SATELLITES_SUBMIT_TLM=0 /usr/bin/time -p gr_satellites RSP-03 \
        --rawint16 "replays/rsp03/iq_$obs.raw" --iq --samp_rate 57600 \
        --kiss_out "$out/$obs.kiss" --hexdump > "$out/$obs.log" 2>&1
done
