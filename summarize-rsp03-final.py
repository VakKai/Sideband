"""Aggregate same-observation matches and pass-level unique occurrences."""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(directory, name):
    with (directory / f'rsp03-final-{name}.csv').open() as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    args = parser.parse_args()
    packets = read(args.run_directory, 'packets')
    timings = read(args.run_directory, 'timings')
    manifest = read(ROOT / 'results', 'manifest')
    passes = dict.fromkeys(row['pass_start_utc'] for row in manifest)
    with (args.run_directory / 'rsp03-final-passes.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['pass_start_utc', 'mode', 'station_matched_occurrences',
                         'recording_matches', 'unmatched_recording_occurrences', 'replay_seconds'])
        for start in passes:
            ids = {row['observation'] for row in manifest if row['pass_start_utc'] == start}
            for mode in ('hard', 'confidence', 'selective'):
                rows = [row for row in packets if row['observation'] in ids and row['mode'] == mode]
                matched = [row for row in rows if row['station_match'] == 'True']
                # The two archive captures start together. Across polarizations,
                # count matching payloads within 50 ms as one occurrence.
                unique = []
                for row in sorted(matched, key=lambda r: float(r['seconds'])):
                    if not any(row['sha256'] == old['sha256'] and
                               row['observation'] != old['observation'] and
                               abs(float(row['seconds']) - float(old['seconds'])) <= .05
                               for old in unique):
                        unique.append(row)
                elapsed = sum(float(row['local_replay_seconds']) for row in timings
                              if row['observation'] in ids and row['mode'] == mode)
                writer.writerow([start, mode, len(unique), len(matched),
                                 len(rows) - len(matched), f'{elapsed:.6f}'])


if __name__ == '__main__':
    main()
