#!/usr/bin/env python3
"""Unguided, overlapping whole-pass control using the original fixed clock decoder.
Not a timing-recovery or burst-detection benchmark. Reference bytes only score output.
"""
import argparse, csv, hashlib, importlib.util, json, time
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('diagnostic', Path(__file__).with_name('replay-rsp03.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recording_dir', type=Path)
    p.add_argument('--observation', choices=d.CHECKSUMS, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--decoder', choices=['fixed', 'timing'], default='fixed')
    p.add_argument('--shift-hz', type=float, default=0.)
    a = p.parse_args()
    obs = a.observation
    decoder = d
    if a.decoder == 'timing':
        spec = importlib.util.spec_from_file_location('timing', Path(__file__).with_name('rsp03-timing.py'))
        decoder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decoder)
    path = a.recording_dir / ('iq_' + obs + '.raw')
    with path.open('rb') as f:
        if hashlib.sha256(f.read()).hexdigest() != d.CHECKSUMS[obs]:
            raise ValueError('Recording checksum mismatch')
    refs = d.station_frames(obs, a.recording_dir / 'references')
    samples = np.memmap(path, dtype='<i2', mode='r').reshape(-1, 2)
    # Accept every CRC-valid frame; references never control candidate selection.
    class AcceptValid:
        def __contains__(self, frame):
            return frame is not None
    found = []
    started = time.perf_counter()
    # One second overlap exceeds the longest supported 2500-symbol frame.
    for start in range(0, len(samples), 5 * d.RATE):
        x = samples[start:start + 6 * d.RATE].astype(np.float32)
        if len(x) < 100:
            continue
        iq = (x[:, 0] + 1j * x[:, 1]) / 32767
        for relative, frame in decoder.recover(iq, a.shift_hz, AcceptValid()):
            seconds = start / d.RATE + relative
            if not any(frame == prev and abs(seconds - t) < .002 for t, prev in found):
                found.append((seconds, frame))
    elapsed = time.perf_counter() - started
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('w') as f:
        w = csv.writer(f)
        w.writerow(['observation', 'seconds_from_iq_start', 'payload_bytes', 'payload_sha256', 'station_match'])
        for seconds, frame in sorted(found):
            w.writerow([obs, f'{seconds:.6f}', len(frame), hashlib.sha256(frame).hexdigest(), frame in refs])
    summary = dict(decoder=a.decoder, shift_hz=a.shift_hz, observation=obs, sample_rate=d.RATE, duration_seconds=len(samples)/d.RATE,
                   processing_seconds=elapsed, crc_valid_occurrences=len(found),
                   station_matched_occurrences=sum(frame in refs for _, frame in found),
                   reference_unique_payloads=len(refs), recovered_reference_unique_payloads=len({f for _, f in found if f in refs}),
                   limitation='Experimental clock recovery when selected. Payload matching does not establish station occurrence timing.')
    a.output.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
