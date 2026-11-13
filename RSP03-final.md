# RSP-03 held-out benchmark

Across six held-out RSP-03 passes and 12 Dwingeloo I/Q recordings, the confidence decoder recovered **40 distinct station-matched packet occurrences**, up from **36** with hard decisions using the same symbol timing. Selective frequency retry recovered the same 40 and increased replay time from 110.0 to 176.9 seconds, about 61%. Confidence retry is the default receiver mode for this dataset. No model was trained.

The six pass groups were frozen before this replay. Both Dwingeloo polarizations of each pass share the same split. The receiver uses the same automatic burst detector and timing bank in all three modes. Hard decisions disable the confidence retry. Confidence adds a bounded single-symbol retry at zero shift. Selective adds one corrected attempt on detected bursts whose peak power ratio is at least 10, keeping the zero-shift output.

The benchmark counts packet occurrences whose payload bytes match station records for the same observation. Identical matches across polarizations within 50 ms count once at pass level. Station references are loaded after the receiver has emitted its candidates. Unmatched checksum-passing candidates are retained in the packet table. The available station files provide no denominator for a reception percentage.

Replay timing includes checksum verification, local I/Q reads, burst detection, decoding, and deduplication. It excludes downloads, process startup, station scoring and result serialization. Each arm ran once per recording on Apple Silicon with macOS 26.6, Python 3.13.5, NumPy 2.1.3 and SciPy 1.15.3. The arms ran in fixed order with normal filesystem caching. Use the timing as a cost estimate for these captures.

## Results

| Held-out pass (UTC) | Hard | Confidence | Selective | Hard s | Confidence s | Selective s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-12-05 09:59:45 | 6 | 6 | 6 | 11.32 | 18.54 | 31.84 |
| 2025-12-07 09:27:43 | 6 | 6 | 6 | 9.36 | 14.73 | 23.36 |
| 2025-12-19 09:03:53 | 4 | 5 | 5 | 13.55 | 21.22 | 36.07 |
| 2026-01-09 18:25:24 | 6 | 8 | 8 | 14.51 | 21.78 | 32.83 |
| 2026-01-15 17:11:56 | 9 | 9 | 9 | 11.50 | 17.56 | 25.81 |
| 2026-02-15 09:03:37 | 5 | 6 | 6 | 10.49 | 16.17 | 27.02 |

Confidence retry added four distinct occurrences across three passes and preserved every hard-decision recovery. Neither added mode had a zero-recovery pass. Selective retry preserved all confidence outputs. Two additional CRC-passing candidates from the confidence decoder did not match a station payload and are excluded from the verified totals. Counts are limited to Dwingeloo recordings and the available station reference files.

The replay example uses observation 13009022 on the December 19 pass. The dashed marker at 116.774 s identifies a verified packet recovered by the confidence and selective modes. [Watch the 24-second demo](results/Sideband-demo.mp4) · [Spectrogram and packet markers](results/rsp03-final-demo.png)

Stock gr-satellites 5.9.0 produced four checksum-passing candidates and zero same-observation matches across all six passes at 57.6 ksample/s. Its wall time includes process startup and uses a different timing boundary. [Stock replay results](results/rsp03-final-stock.csv)

## Reproduce

From Sideband, with Python 3.12+, NumPy, and SciPy:

```sh
python fetch-rsp03-final.py
python -B benchmark-rsp03-final.py --output replays/rsp03/final-run
python summarize-rsp03-final.py replays/rsp03/final-run
```

The fetcher verifies the capture checksums in the manifest. The runner checks the frozen decoder source hashes and fetches any uncached public SatNOGS reference frames. Use a new output directory to start a fresh timing run. The plot requires Matplotlib.

[Recording manifest](results/rsp03-final-manifest.csv) · [Per-pass results](results/rsp03-final-passes.csv) · [Packets](results/rsp03-final-packets.csv) · [Timings](results/rsp03-final-timings.csv)
