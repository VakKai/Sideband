# RSP-03 feasibility replay

The replay recovered seven distinct station-matched housekeeping frame occurrences from two independent passes. The two polarizations of the February pass contain the same three packets at the same sample times. They count once in a pass-level result.

| Observation | Pass UTC | Station reference files | Byte-matched occurrences at 0 Hz |
| --- | --- | ---: | ---: |
| 12511021 | 2025-10-06 09:07:43 | 4 | 2 |
| 12511022 | 2025-10-06 09:07:43 | 3 | 2 |
| 13415454 | 2026-02-16 07:03:15 | 3 | 3 |
| 13415455 | 2026-02-16 07:03:15 | 3 | 3 |

The [coverage inventory](results/rsp03-coverage.csv) groups 56 archive files into 28 start times. Twenty-three times are tagged GMSK 9600, and 22 of those have station frame files in at least one polarization. These are candidates for development and held-out passes. A station file count is an availability check. It does not verify the contents of every file or count every transmitted packet. [Dwingeloo archive](https://data.camras.nl/satnogs/) · [SatNOGS observation API example](https://network.satnogs.org/api/observations/12511021/)

## Sample rate and decoder

Use 57,600 complex samples/s for these four captures. The archive landing page gives a general 48,000 samples/s rate. The waterfall for 12511021 spans −28,800 to +28,743.75 Hz in 1,024 bins, and its time axis ends at 551.378 s. The corresponding I/Q file spans 551.532 s at 57.6 ksample/s, or 661.838 s at 48 ksample/s. All four captures produce exact station matches at 57.6 ksample/s. SatNOGS documents that its generic FSK I/Q dump is downstream of Doppler correction. Observation metadata reports an I/Q dump and rig-control settings. That evidence supports treating the remaining offset as residual, although the exact Dwingeloo flowgraph revision and tuning history were unavailable. [Station waterfall artifact](https://db-satnogs.freetls.fastly.net/media/artifacts/b6342567-e613-4647-9c03-249a22ee6c72.h5) · [SatNOGS flowgraph notes](https://wiki.satnogs.org/Understanding_satnogs-flowgraphs)

The earlier stock replay’s short payloads did not establish valid RSP-03 telemetry. On the four reference-bearing captures above, stock gr-satellites yielded zero exact station matches at both tested sample rates. The station reference frames are 101, 200, or 250 bytes. They carry the Rymansat housekeeping packet headers after the AX.25 header. [Housekeeping beacon specification](https://rsp03.rymansat.com/assets/pdfs/RSP-03_HK_Beacon_Format%28EN%29_Rev1R2.pdf)

The diagnostic decoder low-pass filters the complex signal, then converts the phase change between adjacent samples into a frequency discriminator. At 57.6 ksample/s it has exactly six samples per 9.6 kbaud symbol. It tries the six clock phases in each short window, then applies NRZI decoding, G3RUH descrambling, HDLC bit unstuffing and an AX.25 FCS check. The station frames enter only at the final byte comparison. Station packet times guided the choice of windows. The diagnostic therefore measures recovery on known burst windows and does not establish a whole-pass detection rate.

## Frequency sensitivity

I applied fixed shifts from ±50 Hz through ±1 kHz to the same burst windows with the same decoder. Zero shift gave the highest matched count on every capture. No shift of magnitude 250 Hz or greater recovered a station match. On two confirmed bursts in 12511021, excess power in a ±7 kHz band was about 3.8 and 3.3 dB above adjacent background power, measured over 80 ms at the matched frame start. Both frames decoded at zero shift. These examples show sensitivity to added offset. They do not establish that existing residual offset causes real frame losses.

Before training, replay whole development passes with a conventional burst and symbol timing detector. Look for station-confirmed misses where recentering a burst improves recovery using the same decoder. If that does not recur, the archive still supports receiver experiments, but it has yet to demonstrate the failure mode the learned tracker would address.

## Reproduce

Run from Sideband with Python 3.12 or later, NumPy and SciPy. The measured run used Python 3.13.5, NumPy 2.1.3 and SciPy 1.15.3. The script checks the four recording hashes and fetches public SatNOGS reference payloads on first use.

```sh
mkdir -p replays/rsp03
for obs in 12511021 12511022 13415454 13415455; do
  curl -fLSs --retry 2 "https://data.camras.nl/satnogs/iq_${obs}.raw" \
    -o "replays/rsp03/iq_${obs}.raw"
done
python replay-rsp03.py replays/rsp03 \
  --shift=-1000 --shift=-500 --shift=-250 --shift=-100 --shift=-50 \
  --shift=0 --shift=50 --shift=100 --shift=250 --shift=500 --shift=1000
```

[Saved packet matches](results/rsp03-reference-matches.csv) records sample-relative times and SHA-256 hashes for each decoded occurrence. A missing observation/shift combination represents zero exact matches.

## Whole-pass control — 2026-11-12

Added `replay-rsp03-whole.py`: scans the complete recording in six-second windows with a five-second stride, accepts all CRC-valid frames before reference comparison, and deduplicates overlapping detections. This is an unguided fixed-clock control, not yet automatic burst detection or symbol timing recovery. SHA-256 validation is mandatory. Processing time excludes download, checksum validation and reference loading.

Both polarizations of the October 6 09:07:43 development pass were replayed at the previously established 57,600 samples/s. Each recording is 551.532 seconds long. Observation 12511021 recovered two CRC-valid, station-matched occurrences (two of four unique station payloads) in 3.761 seconds. Observation 12511022 recovered two CRC-valid, station-matched occurrences (two of three unique station payloads) in 3.683 seconds. No additional CRC-valid payloads were found. Results and timing summaries are in `results/rsp03-whole-12511021.{csv,json}` and `results/rsp03-whole-12511022.{csv,json}`. These are payload matches; absolute station occurrence alignment still needs verification. Runtime environment: Python 3.9, NumPy 2.0.2, SciPy 1.13.1.

`results/rsp03-split-v1.json` freezes six held-out passes and sixteen development passes before tracking work. Both polarizations always share a split. Previously explored pass groups are forced into development. Only good GMSK archive passes are included. Sample rates for additional captures still require verification before use.

The whole-pass control reproduces the earlier recovery counts without station-selected windows. It does not yet explain the missing station payloads. Next: implement and validate symbol timing recovery, align station packet occurrences, then compare no correction against an independently estimated residual-frequency correction with identical downstream decoding. No learned tracker has been trained, and no frequency-recovery benefit has been established.

Example:

```sh
python -B replay-rsp03-whole.py replays/rsp03 \
  --observation 12511021 --output results/rsp03-whole-12511021.csv
```

### Timing candidate and whole-pass offset controls

Added experimental `rsp03-timing.py`, selected with `--decoder timing`. It estimates a symbol-clock tone from discriminator transition energy in 20 ms blocks, unwraps/interpolates clock phase, and tries six fixed sampling offsets. It consumes no station payloads or station timestamps. This candidate is not accepted as the baseline: full-pass recovery is one matched occurrence on 12511021 (a regression from two) and two on 12511022 (unchanged). Processing times were 4.747 and 4.779 seconds. The final runs used explicit summation for the clock-tone calculation after the platform's matrix multiplication emitted numerical warnings; final runs emitted none. This negative result does not establish that symbol timing is irrelevant, only that this candidate is inadequate.

`results/rsp03-reference-audit.csv` lists every downloaded station payload and whether the fixed-clock whole-pass control recovered it. Missing payloads are the 200-byte and 250-byte packets on 12511021 and the 250-byte packet on 12511022. These are concrete targets for subsequent diagnostics, with station filenames preserved for time alignment. Payload length alone does not establish the cause of failure.

The whole-pass runner now also accepts `--shift-hz`, applying the same constant translation in each overlapping window before unchanged downstream decoding. These are diagnostic constant-offset trials, not an estimated or phase-continuous whole-pass tracker. Their separate CSV/JSON files retain zero-frame outcomes and runtimes. Held-out passes remain untouched. Automatic burst detection, robust timing recovery, station occurrence alignment, and independently estimated time-varying frequency correction remain outstanding.

Completed fixed-offset controls (matched occurrences at −100, −50, 0, +50, +100 Hz): 12511021 = **0, 1, 2, 1, 0**; 12511022 = **1, 1, 2, 0, 0**. Every recovered payload in a shifted run was also recovered at zero shift. No missing station payload was restored. These whole-pass controls reinforce the earlier guided-window result, without ruling out a time-varying offset or better timing recovery.

### Automatic detection and signal-estimated correction — 2026-11-12

`replay-rsp03-tracking.py` now searches both entire development captures without station windows. A 20 ms spectral detector compares mean power within ±7 kHz with the 10–20 kHz background on either side; the threshold is 2 dB, with short gaps bridged and 100 ms padding. It returns 38 candidate segments on 12511021 and 34 on 12511022. These are energy detections, not 72 confirmed satellite transmissions. Both uncorrected detection runs preserve every baseline packet's payload and time to within 2 ms: two occurrences per polarization.

Two signal-only correction candidates use noise-subtracted spectral centroids within ±7 kHz. The varying candidate median-filters five centroid blocks and integrates an interpolated frequency into continuous phase within each detected segment. The steady candidate uses the median centroid of above-threshold blocks for one correction per segment. Neither consumes reference payloads or station timestamps. Neither restores a missed payload:

| Observation | Uncorrected | Varying centroid | Burst median |
| --- | ---: | ---: | ---: |
| 12511021 | 2 | 0 | 2 |
| 12511022 | 2 | 0 | 1 |

Every corrected recovery is a subset of the uncorrected recoveries. The varying estimator has large excursions and is unsuitable in its current form. The steady estimate reduces that instability but still regresses on the second polarization. Do not treat these candidates as an accepted conventional baseline or a reason to train a learned tracker. A centroid can reflect modulation, noise and interference as well as receiver frequency offset.

The full detector plus all three decode branches took 3.628 and 2.804 seconds respectively (excluding file validation/reference loading); these totals are not independent per-method runtime comparisons. `results/rsp03-tracking-<observation>-frequency.csv` retains every 20 ms centroid/power measurement and detector decision, `-bursts.csv` records segment boundaries and smoothed-estimate ranges, `-packets.csv` records all CRC-valid recoveries, and `.json` includes zero-frame branches. The steady correction can be reconstructed as the median raw centroid among detected segment blocks exceeding the threshold.

`check-rsp03-tracking.py` checks sign/units on ten-second symmetric band-limited synthetic noise: injected −500, 0, +500 Hz yielded mean estimates −495.6, 4.4, +504.4 Hz. It also verifies automatic detection preserves all baseline occurrences. This validates basic estimator arithmetic, not accuracy on real GMSK bursts. Held-out data remain untouched.

Remaining decision work: robust symbol timing recovery, station occurrence alignment, and a better validated offset estimator. The three missing reference payloads still have not been recovered. The frequency-tracking hypothesis remains open, with no positive evidence yet from these correction candidates.

### Timing bank restores two misses — 2026-11-12

**The first positive intervention is timing, not frequency correction.** `replay-rsp03-clock-bank.py` searches half-sample phases at nine symbol spacings (−1000, −500, −200, −100, 0, +100, +200, +500, +1000 ppm relative to six samples/symbol). It uses one-second windows with half-second overlap within all automatically detected segments. Filtering, discriminator, NRZI, descrambling, unstuffing and CRC remain the same as the diagnostic decoder. No frequency correction is applied. Station bytes label CRC-valid results only; they do not select windows or search parameters.

| Observation | Fixed-clock occurrences | Timing-bank occurrences | Newly restored reference |
| --- | ---: | ---: | --- |
| 12511021 | 2 | 3 | 200-byte packet at 96.6576 s |
| 12511022 | 2 | 3 | 250-byte packet at 216.2321 s |

All six timing-bank occurrences match station payloads byte for byte. Every earlier fixed-clock occurrence is retained with its time agreeing within 2 ms. The restored 200-byte packet decodes at −200 ppm sample spacing; the restored 250-byte packet at −100 ppm. Neither restored packet decodes at zero ppm in this half-sample phase bank. These search optima are not calibrated measurements of receiver oscillator error: noise and finite packet lengths can affect which hypotheses pass CRC. The 250-byte reference on 12511021 remains missing.

The search processed 338 windows in 25.529 seconds on 12511021 and 250 windows in 20.284 seconds on 12511022. This is an offline diagnostic bank, not an accepted online timing loop, and it is more costly than the fixed-clock baseline. Outputs `rsp03-clock-bank-<observation>.csv` retain every successful hypothesis, `-occurrences.csv` deduplicates packet occurrences, and `.json` records parameters and runtime. `rsp03-timing-restored.json` isolates the two new payloads.

`check-rsp03-clock-bank.py` builds a synthetic 250-byte packet with FCS, HDLC stuffing, G3RUH scrambling and NRZI levels. It verifies recovery at known −1000/0/+1000 ppm spacings and rejection of a corrupted frame. This exercises the timing/bit path, not a complete GMSK RF channel simulation.

Next priority: implement a practical timing-recovery method that retains these gains, then evaluate signal-estimated frequency correction using that same improved downstream decoder. The earlier negative frequency experiments used an incomplete timing decoder. No learned tracker is warranted yet, and held-out passes remain untouched.

Reproduce from Sideband:

```sh
python -B replay-rsp03-clock-bank.py . --observation 12511021
python -B replay-rsp03-clock-bank.py . --observation 12511022
python -B check-rsp03-clock-bank.py
```

### Compact timing bank and second development pass — 2026-11-12

The clock-bank runner now supports `--profile compact` (−200, −100, 0 ppm spacing, still twelve half-sample phases) and `--correction burst-median`. This compact profile was selected using the October development results, not independent validation. On October it retains all six wide-bank packet occurrences with no substitutions or time differences over 2 ms, while reducing decode time from 25.529/20.284 seconds to 8.759/5.966 seconds. It remains an offline hypothesis bank, not an adaptive timing loop.

Both February development recordings were restored, checksum-validated and replayed at their previously established 57,600 samples/s. Automatic detection produces 24 and 25 candidate segments. The compact profile was not retuned for February and preserves three station-matched occurrences in each polarization. These two polarizations contain duplicates and must not be counted as six distinct pass-level packets.

Frequency correction was reassessed using the same compact timing bank, identical detected segments, and identical window placement. The signal-only median estimator again fails to restore anything:

| Observation | No correction | Burst-median correction | Newly recovered | Lost | Decode seconds, uncorrected / corrected |
| --- | ---: | ---: | ---: | ---: | --- |
| 12511021 | 3 | 3 | 0 | 0 | 8.759 / 8.965 |
| 12511022 | 3 | 1 | 0 | 2 | 5.966 / 6.448 |
| 13415454 | 3 | 0 | 0 | 3 | 3.249 / 3.252 |
| 13415455 | 3 | 1 | 0 | 2 | 2.316 / 3.081 |

All outputs are CRC-valid and station matched; occurrence comparisons use payload identity and a 2 ms time tolerance. Runtime excludes checksum/reference loading and earlier detector/centroid generation; these are decode-stage comparisons, not end-to-end latency benchmarks. A single timing measurement is approximate. `results/rsp03-compact-comparison.csv` is generated by `summarize-rsp03-compact.py`; detailed per-hypothesis and per-occurrence files retain the `-compact-none` and `-compact-burst-median` suffixes.

This strengthens the case for keeping the compact, uncorrected timing bank as the current development control. It does not prove frequency tracking has no value; the tested centroid estimator is demonstrably unsuitable on these captures. Next, investigate the last October missing payload and evaluate timing/offset estimation on additional development passes with independently checked sample rates. A practical adaptive timing loop and a defensible conventional frequency tracker remain unfinished. Held-out passes have not been accessed or tuned against, and no learned tracker has been trained.

Example:

```sh
python -B replay-rsp03-clock-bank.py . --observation 13415454 --profile compact
python -B replay-rsp03-clock-bank.py . --observation 13415454 --profile compact --correction burst-median
python3 summarize-rsp03-compact.py
```

### First controlled frequency-assisted rescue — 2026-11-12

**A +25 Hz translation restores the remaining October 250-byte packet at a fixed downstream timing setting.** This is a targeted development finding, not a blind tracking result. The correction and timing were discovered using the known station payload; no claim about independent offset estimation or held-out performance follows.

First, `diagnose-rsp03-miss.py` searched the detected 96.32–97.34 s segment with eight FIR cutoffs from 3.5 to 7 kHz, 13 symbol spacings from −400 to +200 ppm, and quarter-sample phases. With no frequency correction, it recovered only the already-known 200-byte and 101-byte payloads, not the remaining 250-byte target. Results are in `results/rsp03-miss-filter-timing.{csv,json}`.

Next, `diagnose-rsp03-bits.py` reconstructed the target's FCS and stuffed bit sequence and aligned it against discriminator-derived bits, minimizing mismatches over timing hypotheses. This is explicitly reference-assisted analysis. Across shifts −100, −75, −50, −25, 0, +25, +50, +75, +100 Hz, minimum mismatches among 2,093 stuffed bits were respectively **16, 12, 6, 6, 6, 0, 6, 12, 24**. Each shift's minimum may use a different timing hypothesis. Detailed mismatch indices are retained in `results/rsp03-miss-bit-errors.json`.

Finally, `verify-rsp03-offset-rescue.py` passed both unshifted and +25 Hz signals through the ordinary framing/CRC decoder with **identical −100 ppm sample spacing and 4.25-sample phase**, the same 5 kHz filter, and the same segment. Unshifted yielded no CRC-valid packet at these settings. +25 Hz yielded the 250-byte station payload with SHA-256 `dba6a7c96660f16e458891120c1101480801f7020d12c420064faf90edc1921c` at 96.980633 s (opening flag time). `results/rsp03-offset-rescue.json` preserves both arms including the zero result. The earlier reference-bit alignment time refers to payload bits and is approximately eight symbols later, not a conflicting packet time.

This shows that a small frequency adjustment can rescue one real missed packet with this downstream decoder. It does not establish the physical offset as exactly −25 Hz: the optimum may also compensate discriminator bias or interact with noise/timing. All currently downloaded October station payloads have now been recovered across experiments, but the targeted rescue must not be added to the compact baseline's benchmark counts.

The next decision test is to estimate a useful correction without consulting the packet reference and reproduce this benefit on additional development bursts/passes. The existing spectral-centroid estimators fail that test. Training remains premature; held-out passes remain untouched.

### CRC-only frequency-bank comparison — 2026-11-12

`replay-rsp03-frequency-bank.py` now searches all automatically detected segments at shifts −50, −25, 0, +25, +50 Hz, using identical −200/−100/0 ppm timing hypotheses and quarter-sample phases in every branch. It loads reference payloads only after all decoding is complete. CRC selects candidates; references subsequently score them. The grid was nevertheless selected using October development findings, so this is not an independent or held-out validation and is not an estimated frequency tracker.

| Observation | Zero-shift verified | Bank-union verified | New verified | Zero-shift seconds | Full-bank seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12511021 | 3 | 4 | 1 | 16.807 | 86.397 |
| 12511022 | 3 | 3 | 0 | 12.793 | 64.984 |
| 13415454 | 3 | 3 | 0 | 6.334 | 30.041 |
| 13415455 | 3 | 3 | 0 | 4.680 | 24.271 |

The first recording's +25 Hz branch restores the same 250-byte target while the matched zero-shift branch does not. It is the only new station-verified occurrence across these four recordings. The bank union includes the zero-shift arm, so retaining baseline recoveries is guaranteed by construction and must not be described as proof that individual corrections avoid regressions. Most shifted branches lose packets. Runtime excludes detector generation and reference loading; full-bank cost is roughly five times the matched zero-shift arm.

A separate 30-byte CRC-valid candidate at 477.529336 s occurs in zero-shift and −25 Hz branches of 12511021. It matches no available station reference. It is retained in outputs but excluded from verified telemetry counts; CRC alone does not establish that it is valid RSP-03 telemetry. The zero-shift branch's four CRC-valid occurrences therefore represent only three verified packets, not recovery of the 250-byte target.

After deduplicating the two February polarizations, verified pass-level union counts are seven October occurrences and three February occurrences. These are development search results, not held-out benchmark figures. The apparent frequency benefit has not yet recurred on another packet or pass.

Detailed hypotheses, zero-shift membership, packet hashes and unmatched candidates are saved under `results/rsp03-frequency-bank-<observation>*`; the comparison CSV is produced by `summarize-rsp03-frequency-bank.py`. Next: additional development passes with independently verified sample rates, plus a signal-derived estimator that can obtain this benefit without the cost of a full frequency bank. No learned tracker is trained; held-out passes remain untouched.

### Third development pass, unchanged settings — 2026-11-12

Added both polarizations of the already-designated development pass starting 2025-10-06 10:43:07 UTC: 12511719 and 12511720. Both I/Q checksums are now registered. The latter also matches the checksum saved during the original setup work. Station metadata and HDF5 waterfall artifacts are archived in `replays/rsp03/metadata`.

Sample rate was checked independently of decoder success. Each numerical waterfall has 1,024 frequency bins spaced by 56.25 Hz, covering −28,800 to +28,743.75 Hz: 57,600 samples/s. The I/Q durations at that rate are 622.116979 and 621.992569 seconds; the corresponding waterfall relative-time endpoints are 621.955556 and 621.866667 seconds, consistent within 0.17 seconds. The HDF5 frequency labels misleadingly say kHz although the stored numbers are Hz; the rendered ±28.8 kHz images and sample-count/time checks resolve this. Upstream 1 MHz ADC metadata is not the dump rate. `check-rsp03-newpass-rate.py` reproduces these checks and writes `results/rsp03-rate-12511719-12511720.json` with source artifact URLs.

Detector and search parameters were unchanged from the preceding experiments. The same frequency bank, quarter-sample phase grid, symbol spacings and filtering were used, with references loaded only after decoding.

| Observation | Detected segments | Fixed timing, uncorrected | Timing bank, zero shift | Frequency-bank verified union | New verified from frequency search | Zero-shift / full-bank seconds |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 12511719 | 15 | 2 | 3 | 3 | 0 | 8.064 / 42.530 |
| 12511720 | 25 | 0 | 0 | 0 | 0 | 6.974 / 37.744 |

All three station reference payloads on 12511719 are recovered by timing search without a frequency shift. None of the three references on 12511720 are recovered by these detector/search settings. The −50 Hz branch on 12511720 produces one unmatched CRC-valid candidate; it remains excluded from verified telemetry counts. Preserve this zero-verified-frame recording in comparisons. The failure could still involve detection, signal quality or decoder limitations; it is not proof that its station packets are absent from the I/Q.

Across six recordings from three development passes, frequency search has added exactly one station-verified occurrence, on the original October pass. The benefit has not yet recurred on another pass. The six-recording comparison CSV now reports **new verified occurrences** explicitly and uses the frozen manifest for pass grouping. Held-out passes remain untouched. Next: investigate the zero-recovery polarization and broaden development coverage before accepting a tracker or initiating training.

### Zero-recovery polarization diagnosis — 2026-11-12

The three station payloads on 12511720 align within the **already detected 98.62–99.64 s segment**. `diagnose-rsp03-zero.py` reconstructs each reference's stuffed bits/FCS and minimizes bit mismatches across shifts −200, −100, −50, −25, 0, +25, +50, +100, +200 Hz, sample spacings −1000 through +1000 ppm in 100 ppm increments, and quarter-sample phases. It also runs ordinary HDLC/CRC decoding. This is targeted, reference-assisted diagnosis, not a benchmark or independently estimated timing/frequency result.

At zero shift, each reference can be aligned with just six mismatched stuffed bits:

| Payload | Payload-bit start (s) | Stuffed bits including FCS | Minimum mismatches at zero shift | Example spacing / phase |
| --- | ---: | ---: | ---: | --- |
| 101 bytes | 98.967808 | 825 | 6 | −400 ppm / 1.75 samples |
| 250 bytes | 99.087067 | 2092 | 6 | −100 ppm / 1.75 samples |
| 200 bytes | 99.338294 | 1637 | 6 | 0 ppm / 3.75 samples |

All packet spans fit inside the detector segment; these payloads were not lost because the detector excluded them. No tested frequency shift eliminates the errors, and the broad timing/frequency search produces **zero CRC-valid hypotheses**. Larger shifts generally worsen mismatch counts. `results/rsp03-zero-diagnosis.json` retains the complete per-reference/per-shift minima and search limits.

`inspect-rsp03-zero-errors.py` records zero-shift mismatch locations (zero-based, relative to stuffed payload bits): 101-byte packet `[585,586,597,598,602,603]`; 250-byte packet `[401,403,413,415,418,420]`; 200-byte packet `[1581,1582,1593,1594,1598,1599]`. The short paired clusters with 12- and 17-bit separations are consistent with a small number of bad symbol decisions propagated by differential decoding and descrambling. This pattern does not identify a physical cause such as fading, interference or receiver distortion; no error bits were repaired to claim a recovery.

A separate no-frequency-correction search (`diagnose-rsp03-zero-filter.py`) tried FIR cutoffs 3.5–7 kHz in 500 Hz steps, discriminator smoothing lengths 1/2/3 samples, spacings −400 through +200 ppm in 50 ppm steps, and quarter-sample phases. It also produced zero CRC-valid hypotheses. `results/rsp03-zero-filter-search.json` preserves the zero result. These negative searches do not exhaust receiver designs.

Conclusion: the zero result is now localized to bit decisions in known packet-bearing segments, not missing detection. It provides no new evidence for a frequency-tracking benefit. Keep 12511720 as a zero-verified-frame case in the unchanged benchmark. Next useful receiver experiment is soft-decision or sequence-aware demodulation, evaluated separately from frequency correction; additional development passes are still needed before a learned tracker is justified. Held-out passes remain untouched.

### Confidence-based demodulation follow-up

The single-symbol confidence retry and fourth development pass are documented in [RSP03-confidence.md](RSP03-confidence.md).

### Residual correction from symbol levels

See [RSP03-symbol-levels.md](RSP03-symbol-levels.md) for the fifth development pass, the signal-derived correction, and its verified gains and losses.

### Selective frequency retry

See [RSP03-selective.md](RSP03-selective.md) for the selective second attempt and the sixth development pass comparison.

### Seventh development pass and replay runtime

See [RSP03-runtime.md](RSP03-runtime.md) for the fixed-rule comparison and local replay timings.
