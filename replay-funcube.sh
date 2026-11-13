#!/usr/bin/env bash
set -euo pipefail

output_dir=${1:-replays/funcube}
mkdir -p "$output_dir"
sample="$output_dir/ao73.wav"
expected_sha=d8758c1a860309185dc2b863a431b2266e050fb0e7c8e8d6d1f67a5b206ace9c

if [[ ! -f "$sample" ]]; then
    curl -fLSs --retry 2 \
        https://raw.githubusercontent.com/daniestevez/satellite-recordings/master/ao73.wav \
        -o "$sample.part"
    mv "$sample.part" "$sample"
fi
printf '%s  %s\n' "$expected_sha" "$sample" | shasum -a 256 -c -

{
    uname -m
    sw_vers
    python --version
    gnuradio-config-info --version
    gr_satellites --version
} > "$output_dir/versions.txt"

GR_SATELLITES_SUBMIT_TLM=0 gr_satellites FUNcube-1 \
    --wavfile "$sample" --kiss_out "$output_dir/ao73.kiss" --hexdump \
    2>&1 | tee "$output_dir/ao73.log"

if [[ $(grep -cE '^pdu length = +256 bytes' "$output_dir/ao73.log") -ne 1 ]] ||
    [[ ! -s "$output_dir/ao73.kiss" ]]; then
    echo "Expected one 256-byte FUNcube-1 frame and nonempty KISS output." >&2
    exit 1
fi
