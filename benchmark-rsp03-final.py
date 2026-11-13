"""Replay the frozen held-out split without consulting station data during decoding."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_runtime():
    spec = importlib.util.spec_from_file_location('runtime', ROOT / 'benchmark-rsp03-runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    split = json.loads((ROOT / 'results/rsp03-split-v1.json').read_text())
    manifest = read_csv(ROOT / 'results/rsp03-final-manifest.csv')
    hashes = {row['observation']: row['iq_sha256'] for row in manifest}
    expected = {obs for group in split['passes'] if group['split'] == 'held-out'
                for obs in group['observations']}
    if len(manifest) != len(expected) or set(hashes) != expected:
        raise ValueError('The manifest must contain exactly the frozen held-out observations.')
    for entry in (ROOT / 'results/rsp03-final-frozen.sha256').read_text().splitlines():
        digest, name = entry.split()
        source = ROOT / ('results' if name.endswith('.json') else '') / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen source changed: {source}')
    runtime = load_runtime()
    tracking = runtime.load('tracking')
    confidence = runtime.load('confidence')
    tracking.d.CHECKSUMS.update(hashes)
    args.output.mkdir(parents=True, exist_ok=True)

    for group in split['passes']:
        if group['split'] != 'held-out':
            continue
        for obs in group['observations']:
            checkpoint = args.output / f'{obs}.json'
            if checkpoint.exists():
                continue
            modes = {}
            # Keep identical timing hypotheses. Suppress only single-symbol retries.
            retry_frame = confidence.retry_frame
            confidence.retry_frame = lambda *args: ()
            try:
                modes['hard'], hard_timing = runtime.run(obs, False, tracking, confidence)
            finally:
                confidence.retry_frame = retry_frame
            modes['confidence'], confidence_timing = runtime.run(obs, False, tracking, confidence)
            modes['selective'], selective_timing = runtime.run(obs, True, tracking, confidence)
            references = tracking.d.station_frames(
                obs, ROOT / 'replays/rsp03/references', allow_empty=True
            )
            timing = dict(hard=hard_timing, confidence=confidence_timing, selective=selective_timing)
            rows = [dict(observation=obs, pass_start_utc=group['pass_start_utc'],
                         mode=mode, seconds=seconds, payload_bytes=len(payload),
                         sha256=hashlib.sha256(payload).hexdigest(),
                         station_match=payload in references)
                    for mode, frames in modes.items() for seconds, payload in sorted(frames)]
            temporary = checkpoint.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(timing=timing, packets=rows), indent=2))
            temporary.replace(checkpoint)
            print(obs, {mode: sum(r['mode'] == mode and r['station_match'] for r in rows)
                        for mode in modes}, flush=True)

    records = [json.loads((args.output / f'{obs}.json').read_text())
               for group in split['passes'] if group['split'] == 'held-out'
               for obs in group['observations']]
    packets = [row for record in records for row in record['packets']]
    timings = [dict(observation=obs, mode=mode, **timing)
               for obs in hashes for mode, timing in
               json.loads((args.output / f'{obs}.json').read_text())['timing'].items()]
    write_csv(args.output / 'rsp03-final-packets.csv',
              ['observation', 'pass_start_utc', 'mode', 'seconds', 'payload_bytes', 'sha256',
               'station_match'], packets)
    write_csv(args.output / 'rsp03-final-timings.csv', list(timings[0]), timings)


if __name__ == '__main__':
    main()
