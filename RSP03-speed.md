# Confidence receiver replay speed

Replacing the Python bit-by-bit AX.25 unstuffing loop with byte operations cut median serial replay from **111.05 s to 68.40 s** on the same 12 recordings. That is **1.62× the replay speed**, or 38.4% less time.

| Implementation | Run 1 | Run 2 | Run 3 | Median |
| --- | ---: | ---: | ---: | ---: |
| Original | 111.05 s | 114.59 s | 110.75 s | 111.05 s |
| Optimized | 68.88 s | 68.35 s | 68.40 s | 68.40 s |

Each run emitted the same 56 recording-level packet occurrences, including unmatched candidates. The comparison checked raw payload bytes, exact sample-relative timestamps, and the station-match result. The 52 station matches count as 40 distinct verified occurrences after pass-level deduplication.

A profile of recording 13009022 attributed 17.31 of 23.74 instrumented seconds to frame decoding, including 6.16 seconds appending bits to Python lists. The optimized implementation rejects invalid runs of six ones and removes stuffed zeroes before applying the same frame-length and FCS checks.

The measurements use Python 3.13.5, NumPy 2.1.3, and SciPy 1.15.3 on the same Apple Silicon Mac. All three original runs preceded the three optimized runs. The timer includes file checksum verification, local reads, burst detection, decoding, and deduplication. It excludes downloads and station scoring.

After fetching the benchmark captures, run `python -B benchmark-confidence-speed.py` to measure three serial runs and verify the outputs against the published packet table. The [original source revision](https://github.com/VakKai/Sideband/tree/46553105022f1652b00d815f6fa282832aaf04c1) reproduces the before timings. The [original benchmark report](RSP03-final.md) preserves its single-run measurements for all three receiver modes.
