# Selective frequency retry

The receiver now has an experimental `--selective` mode. It keeps all zero-shift confidence-decoder outputs and retries detected bursts with a peak signal-band to comparison-band power ratio of at least 10 (10 dB). The retry uses the existing clipped symbol-level midpoint and the same timing bank and confidence rules. The gate uses only the burst detector output. Station references are used after decoding.

Across eleven recordings from six development passes, the receiver retried 72 of 460 detected segments (15.7%). It increased the same-recording verified count from **38 to 40**, retained all baseline outputs by construction, and produced one additional unmatched CRC-valid candidate on 12511720. The additional verified packets were the two previously observed gains on 12512296 and 12512778. The threshold was chosen with those development cases in view. The earlier zero-output peer 12512297 was outside this comparison.

Decoder processing increased from 95.3 s to 139.0 s in aggregate. Retried segments consumed about 46% of baseline processing time even though only 16% of segments were selected. Segment durations differ, and a longer segment requires more overlapping decoder windows. Times exclude burst detection, file hashing and reference loading. Some runs overlapped, so these figures describe measured processing overhead in this experiment and are not a controlled latency benchmark. A full five-shift sweep runs the timing and confidence search five times over every segment.

## Sixth development pass

Both polarizations were designated development in the frozen split. The station waterfall frequency bins and capture duration independently confirmed 57.6 ksample/s for both recordings. [Rate evidence](results/rsp03-rate-12579357-12579358.json)

| Observation | Detected segments | Retried | Zero-shift verified | Selective verified | Five-shift union verified |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12579357 | 99 | 8 | 6 | 6 | 6 |
| 12579358 | 56 | 3 | 8 | 8 | 8 |
| Pass, deduplicated by payload and time | | | 9 | 9 | 9 |

Both methods were scored against the same-observation station packets before pass-level deduplication. The five-shift union includes zero and the four existing ±25/±50 Hz branches with the confidence decoder enabled. Each nonzero branch recovered only a subset of the verified zero-shift packets on this pass. The station reference inventory is incomplete and provides no denominator for packet reception rate.

The selective mode is a candidate conventional baseline for a future frozen comparison. The fresh pass provided no verified frequency rescue for either method. For the next development check, keep the current threshold fixed and target total replay cost per verified gain across further passes. The present evidence does not justify training a learned tracker.

## Reproduce

With Python 3.12+, NumPy and SciPy, run from Sideband using the two saved captures and automatic burst tables. Omit `--selective` and use `--shift` for the sweep branches.

```sh
python -B replay-rsp03-confidence.py . \
  --observation 12579357 --observation 12579358 --selective \
  --output replays/rsp03/sixth-selective
```

[Counts and timing](results/rsp03-selective-comparison.csv) · [Packet occurrences](results/rsp03-selective-occurrences.csv) · [Sweep packet occurrences](results/rsp03-sixth-pass-sweep-occurrences.csv)
