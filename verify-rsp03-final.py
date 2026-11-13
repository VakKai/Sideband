"""Verify the complete held-out benchmark and preservation across decoder modes."""
import csv
import json
from pathlib import Path


def read(name):
    with Path(f'results/rsp03-final-{name}.csv').open() as stream:
        return list(csv.DictReader(stream))


def main():
    split = json.loads(Path('results/rsp03-split-v1.json').read_text())
    expected = {obs for group in split['passes'] if group['split'] == 'held-out'
                for obs in group['observations']}
    manifest = read('manifest')
    timings = read('timings')
    packets = read('packets')
    modes = ('hard', 'confidence', 'selective')
    assert len(expected) == 12
    assert len(manifest) == len(expected) and {row['observation'] for row in manifest} == expected
    assert len(timings) == len(expected) * len(modes)
    assert {(row['observation'], row['mode']) for row in timings} == {
        (obs, mode) for obs in expected for mode in modes
    }
    for obs in expected:
        outputs = {mode: {(row['sha256'], float(row['seconds'])) for row in packets
                          if row['observation'] == obs and row['mode'] == mode}
                   for mode in modes}
        for baseline, extended in zip(modes, modes[1:]):
            assert all(any(digest == other and abs(seconds - when) < .002
                           for other, when in outputs[extended])
                       for digest, seconds in outputs[baseline]), (obs, baseline, extended)
    print(f'Verified {len(expected)} captures, {len(timings)} runs, and packet preservation.')


if __name__ == '__main__':
    main()
