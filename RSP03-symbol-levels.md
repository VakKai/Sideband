# RSP-03 residual correction from symbol levels

The discriminator midpoint recovered two additional verified recording occurrences and lost five against the zero-shift confidence decoder. Across nine compared recordings, verified occurrences fell from **24 to 21**. The midpoint is useful as an experimental second attempt. It does not earn a place as the default correction. Counts are by recording and may include the same transmission in both polarizations.

| Observation | Zero shift | Midpoint correction | Gained | Lost |
| --- | ---: | ---: | ---: | ---: |
| 12511021 | 4 | 4 | 0 | 0 |
| 12511022 | 3 | 2 | 0 | 1 |
| 12511719 | 3 | 2 | 0 | 1 |
| 12511720 | 1 | 1 | 0 | 0 |
| 12512296 | 4 | 4 | 1 | 1 |
| 13415454 | 3 | 2 | 0 | 1 |
| 13415455 | 3 | 2 | 0 | 1 |
| 12512778 | 1 | 2 | 1 | 0 |
| 12512779 | 2 | 2 | 0 | 0 |

The nine-recording comparison includes seven prior captures and both captures of a newly replayed fifth development pass. The earlier zero-output 12512297 peer was outside the midpoint run. The frozen split was used throughout.

## Estimator and controls

A small residual offset adds a roughly constant term to the quadrature discriminator. For each detected burst, the estimator low-pass filters the I/Q, divides it into 20 ms blocks, and keeps blocks with at least half the strongest block's mean power. It takes the midpoint of the 20th and 80th discriminator percentiles in each retained block, then the median midpoint across blocks. The receiver translates the burst by the negative estimate, limited to ±50 Hz, and runs the same timing bank and confidence retry. This is a single translation per burst, with phase continuous across overlapping windows. The percentiles are proxies for the two symbol levels and can be biased by data balance, pulse shaping, or noise.

In two known development bursts, injected −50 and +50 Hz shifts changed the estimates by −60.7/+49.4 Hz and −47.0/+51.8 Hz. The absolute unshifted estimates were +36.5 and +77.9 Hz. The injection verifies response to a change in frequency. The original residual is unknown. Across both runs, 155 of 305 detected segments hit the ±50 Hz translation cap, including segments without verified frames. This limits the resolution of this estimator as used here.

## Fifth development pass

Observations 12512778 and 12512779 were already assigned to development. Both rates are 57,600 samples/s based on their 56.25 Hz waterfall bins and I/Q duration agreement within 0.14 seconds. The midpoint rule was specified before scoring this pair. [Sample-rate evidence](results/rsp03-rate-12512778-12512779.json)

The midpoint recovered a 250-byte station packet at 378.548446 s on 12512778, taking the pair from three to four same-observation verified occurrences with no losses. The −50 Hz branch recovered the same packet and retained all three baseline occurrences. The −25 Hz branch gained that packet but lost a 200-byte packet from 12512779. The new packet was absent from all zero-shift candidates in either recording, so the gain is also present at pass level. The 101-byte frame at 379.003 s also appeared in both polarizations but only matched the station files for 12512778. The table uses same-observation references consistently.

## Decision

The frequency effect recurred on a fresh development pass with the stronger decoder, and a signal-derived correction reproduced that gain. The estimator's regressions across earlier passes are larger than its gains. Keep the zero-shift confidence receiver as the reference. The next conventional experiment is to test whether a second attempt can be restricted to a small fraction of candidate bursts using a signal-only reliability measure. Compare its verified gains, unmatched candidates and full replay cost with zero shift and the full frequency sweep before considering model training.

## Reproduce

Run from Sideband using Python 3.12+, NumPy and SciPy. The capture hashes and saved burst boundaries are checked or loaded by the replay command.

```sh
for obs in 12512778 12512779; do
  if [ ! -f "replays/rsp03/iq_${obs}.raw" ]; then
    curl -fLSs --retry 2 "https://data.camras.nl/satnogs/iq_${obs}.raw" \
      -o "replays/rsp03/iq_${obs}.raw"
  fi
done
python -B replay-rsp03-confidence.py . --observation 12512778 --observation 12512779 \
  --output replays/rsp03/fifth-zero
python -B replay-rsp03-confidence.py . --observation 12512778 --observation 12512779 \
  --symbol-levels --output replays/rsp03/fifth-levels
```

[Occurrence comparison](results/rsp03-levels-comparison.csv) · [Packet times and hashes](results/rsp03-levels-occurrences.csv) · [Estimated offsets](results/rsp03-symbol-level-estimates.csv) · [Injection check](results/rsp03-levels-injection.csv) · [Diagnostic timings](results/rsp03-levels-timings.json). Jobs overlapped during the experiment. The timings exclude burst detection and are unsuitable for measuring speedups.
