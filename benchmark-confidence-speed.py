"""Measure serial confidence replay and check every packet against the published benchmark."""
import csv
import hashlib
from importlib import import_module
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parent


def read_results(name):
    with (ROOT / 'results' / f'rsp03-final-{name}.csv').open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    if repeats < 1:
        raise SystemExit('Repeat count must be positive.')

    runtime = import_module('benchmark-rsp03-runtime')
    tracking = runtime.load('tracking')
    confidence = runtime.load('confidence')
    manifest = read_results('manifest')
    tracking.d.CHECKSUMS.update({row['observation']: row['iq_sha256'] for row in manifest})
    expected = {row['observation']: [] for row in manifest}
    for row in read_results('packets'):
        if row['mode'] == 'confidence':
            expected[row['observation']].append((
                float(row['seconds']), int(row['payload_bytes']), row['sha256'],
                row['station_match'] == 'True',
            ))

    totals = []
    for trial in range(1, repeats + 1):
        total = 0.
        for row in manifest:
            observation = row['observation']
            packets, timing = runtime.run(observation, False, tracking, confidence)
            references = tracking.d.station_frames(
                observation, ROOT / 'replays/rsp03/references', allow_empty=True,
            )
            actual = [(seconds, len(payload), hashlib.sha256(payload).hexdigest(),
                       payload in references) for seconds, payload in sorted(packets)]
            if actual != expected[observation]:
                raise RuntimeError(f'Confidence packet output changed for {observation}')
            total += timing['local_replay_seconds']
        totals.append(total)
        print(f'Run {trial}: {total:.2f} s', flush=True)
    print(f'Median: {median(totals):.2f} s. Packet outputs match on all {len(manifest)} recordings.')


if __name__ == '__main__':
    main()
