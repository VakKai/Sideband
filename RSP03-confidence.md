# RSP-03 confidence-based demodulation

The zero-shift confidence retry recovered four additional station-matched recording occurrences across eight recordings from four development passes. It recovered the 250-byte packet on 12511021 that previously required +25 Hz in the hard-decision receiver, one of the three misses on 12511720, and two packets on the newly added pass. No new unmatched candidates were accepted by the retry in this comparison.

| Observation | Hard decisions, 0 Hz | With confidence retry, 0 Hz |
| --- | ---: | ---: |
| 12511021 | 3 | 4 |
| 12511022 | 3 | 3 |
| 12511719 | 3 | 3 |
| 12511720 | 0 | 1 |
| 12512296 | 2 | 4 |
| 12512297 | 0 | 0 |
| 13415454 | 3 | 3 |
| 13415455 | 3 | 3 |

Counts are per recording. Paired polarizations can recover the same transmission, as in the February pass. The 12512297 station record has no frame files, so its scoring used the six payloads from its same-pass peer 12512296. No frame passed CRC in that recording under either method at any tested shift.

## How the retry works

The frequency discriminator produces a signed value at each hypothesized symbol center. The hard decoder uses the sign alone. The retry ranks symbol decisions by absolute magnitude and, between two intact HDLC flags, tests a single flip at each of the eight least confident interior positions. One changed symbol affects two NRZI decisions, and the G3RUH descrambler spreads those changes across six bits. A retry must pass the AX.25 FCS and the RSP-03 housekeeping header, type and length checks. A timing hypothesis with multiple acceptable repairs is rejected. The existing hard-decoder outputs are retained. Station payloads are loaded only after candidate discovery.

The retry was designed using development failures. Its scope is single-symbol errors inside frames with intact flags. The remaining two misses on 12511720 are unresolved. The additional retry time was about 60% of the measured hard-path time in the sequential six-recording run, based on time spent inside the retry calls. This excludes burst detection, checksum checks and station-file loading. Timings for the fourth-pass shift sweep were concurrent and should not be used as standalone latency measurements.

## Fourth development pass

The paired observations 12512296 and 12512297 were already assigned to development. Both waterfall artifacts have 1,024 bins spaced 56.25 Hz apart, and the I/Q sample counts at 57,600 samples/s agree with the waterfall durations within 0.17 s. The burst detector settings and frequency grid were carried forward. [Rate evidence](results/rsp03-rate-12512296-12512297.json) · [Station observations](https://network.satnogs.org/observations/12512296/)

| Translation | Hard, verified | With retry, verified | Added / lost vs. 0 Hz with retry |
| ---: | ---: | ---: | ---: |
| 0 Hz | 2 | 4 | 0 / 0 |
| −25 Hz | 2 | 5 | 1 / 0 |
| +25 Hz | 1 | 3 | 0 / 1 |
| −50 Hz | 1 | 4 | 1 / 1 |
| +50 Hz | 1 | 1 | 0 / 3 |

All verified packets in the table are from 12512296. The −25 Hz branch added the 101-byte frame at 221.494 s. Shift selection by replay sweep establishes sensitivity to recentering. It provides no signal-derived estimate for that frame, and the best shift can also compensate discriminator bias or interact with timing and noise.

The signal-derived control used the median spectral centroid of active blocks in each burst, clipped to ±50 Hz, with phase continuous across overlapping replay windows. It returned the same four verified occurrences on 12511021. On 12512296 it still recovered four, gaining one packet and losing another compared with zero shift. It did not reproduce the sweep’s five-packet total. The fourth-pass sweep shows that a useful correction exists in the tested grid. Selecting that correction from the signal remains the development gate for a learned tracker. [Centroid results](results/rsp03-confidence-centroid.json)

## Reproduce

With Python 3.12+, NumPy and SciPy, run from Sideband. The script checks the capture hash and reads the saved automatic detections. The larger I/Q files are excluded by the existing replay directory ignore rule.

```sh
python -B replay-rsp03-confidence.py . \
  --observation 12511720 --observation 12512296 --observation 12512297 \
  --output replays/rsp03/confidence-zero
python -B replay-rsp03-confidence.py . \
  --observation 12512296 --observation 12512297 --shift=-25 \
  --output replays/rsp03/confidence-minus25
```

[Measured counts and timings](results/rsp03-confidence-summary.csv) · [Packet times and hashes](results/rsp03-confidence-occurrences.csv)
