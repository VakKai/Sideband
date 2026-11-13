#!/usr/bin/env python3
"""Compare zero-shift and selective replay from local I/Q, including detection."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'replay-rsp03-{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(obs, selective, tracking, confidence):
    started = perf_counter()
    path = ROOT / 'replays/rsp03' / f'iq_{obs}.raw'
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != tracking.d.CHECKSUMS[obs]:
            raise ValueError(f'Checksum mismatch for {path}')
    raw = np.memmap(path, dtype='<i2', mode='r').reshape(-1, 2)
    checked = perf_counter()
    ratios, _, _, labels, count = tracking.detect(raw)
    bursts = []
    for label in range(1, count + 1):
        indices = np.flatnonzero(labels == label)
        bursts.append(dict(start_seconds=indices[0] * .02,
                           stop_seconds=(indices[-1] + 1) * .02,
                           peak_power_ratio=float(ratios[indices].max())))
    detected = perf_counter()
    if selective:
        baseline, corrected, selected = confidence.replay_selective(raw, bursts, tracking.d)
    else:
        baseline = confidence.replay(raw, bursts, tracking.d, 0)
        selected = 0
    union = confidence.combined_occurrences(*baseline[:2])
    if selective:
        for seconds, payload in confidence.combined_occurrences(*corrected[:2]):
            confidence.add_occurrence(union, seconds, payload)
    finished = perf_counter()
    return union, dict(checksum_seconds=checked - started,
                       detector_seconds=detected - checked,
                       decoder_seconds=finished - detected,
                       local_replay_seconds=finished - started,
                       detected_bursts=len(bursts), selected_bursts=selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    split = json.loads((ROOT / 'results/rsp03-split-v1.json').read_text())
    development = {obs for group in split['passes'] if group['split'] == 'development'
                   for obs in group['observations']}
    if set(args.observation) - development:
        parser.error('This comparison is restricted to development observations.')
    tracking = load('tracking')
    confidence = load('confidence')
    runs, packets = [], []
    for obs in args.observation:
        observed = {}
        for trial in range(args.repeats):
            for selective in (False, True) if trial % 2 == 0 else (True, False):
                mode = 'selective' if selective else 'zero'
                decoded, timings = run(obs, selective, tracking, confidence)
                if mode in observed and observed[mode] != decoded:
                    raise RuntimeError(f'Replay changed between runs for {obs} {mode}')
                observed[mode] = decoded
                runs.append(dict(observation=obs, mode=mode, trial=trial + 1, **timings))
                print(obs, mode, trial + 1, round(timings['local_replay_seconds'], 3), flush=True)
        references = tracking.d.station_frames(obs, ROOT / 'replays/rsp03/references', allow_empty=True)
        for mode, occurrences in observed.items():
            packets.extend(dict(observation=obs, mode=mode, seconds=seconds,
                                sha256=hashlib.sha256(payload).hexdigest(), payload_bytes=len(payload),
                                station_match=payload in references)
                           for seconds, payload in sorted(occurrences))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in [('timings', runs), ('packets', packets)]:
        fields = list(rows[0]) if rows else [
            'observation', 'mode', 'seconds', 'sha256', 'payload_bytes', 'station_match'
        ]
        with (args.output / f'rsp03-runtime-{name}.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == '__main__':
    main()
