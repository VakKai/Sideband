# Seventh development pass and local replay cost

The selective receiver and the zero-shift confidence receiver recovered the same five distinct station-matched packets on the October 25 development pass. The retry rule stayed fixed at a detector peak power ratio of at least 10, followed by the existing clipped symbol-level correction. It selected seven of 94 detected segments and added no checksum-passing candidates.

| Observation | Detected / retried | Station matches, either mode | Zero-shift mean | Selective mean |
| --- | ---: | ---: | ---: | ---: |
| 12620260 | 63 / 5 | 4 | 8.18 s | 10.81 s |
| 12620261 | 31 / 2 | 1 | 8.37 s | 8.65 s |
| Paired replay | 94 / 7 | 5 | 16.56 s | 19.45 s |

These are means of two sequential runs per mode and capture, reversing the mode order for the second repeat. Each measured run verifies the file checksum, reads local I/Q, detects bursts, decodes, and deduplicates packets. Process startup, downloads, station scoring, and CSV output are outside the timer. The local file cache was left in its normal state. Both repetitions returned identical output within each mode. The two modes also returned identical candidates, including two checksum-passing candidates without a same-observation station match.

Station waterfalls confirmed 57.6 ksample/s for both recordings through their 56.25 Hz bin spacing and agreement with capture duration within 0.14 seconds. [Rate evidence](results/rsp03-rate-12620260-12620261.json)

Across the selective development comparisons to date, the count is 43 to 45 same-recording verified occurrences on 13 recordings from seven passes. Both gains came from passes already examined when choosing the gate. The sixth and seventh passes added no verified gain. The zero-shift confidence receiver remains the default candidate for the final benchmark, with selective retry as an experimental comparison. The frozen held-out recordings have yet to be run. No learned tracker has been trained.

## Reproduce

Run from Sideband with Python 3.12 or later, NumPy, and SciPy.

```sh
python -B benchmark-rsp03-runtime.py \
  --observation 12620260 --observation 12620261 \
  --output replays/rsp03/runtime-check
```

[Per-run measurements](results/rsp03-runtime-timings.csv) · [Packet times and hashes](results/rsp03-runtime-packets.csv)
