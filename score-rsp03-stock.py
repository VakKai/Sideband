"""Score stock KISS packet payloads against the saved station records."""
import argparse
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def packets(path):
    for frame in path.read_bytes().split(b'\xc0'):
        if frame[:1] == b'\x00':
            yield frame[1:].replace(b'\xdb\xdc', b'\xc0').replace(b'\xdb\xdd', b'\xdb')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_directory', type=Path)
    args = parser.parse_args()
    with (ROOT / 'results/rsp03-final-manifest.csv').open() as stream:
        manifest = list(csv.DictReader(stream))
    refs = ROOT / 'replays/rsp03/references'
    with (args.stock_directory / 'rsp03-final-stock.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['observation', 'crc_candidates', 'station_matches', 'wall_seconds',
                         'matched_payload_sha256'])
        for row in manifest:
            obs = row['observation']
            reference = {path.read_bytes() for path in refs.glob(f'data_{obs}_*')}
            if row['reference_files'] != '0' and not reference:
                raise ValueError(f'Station references are missing for {obs}')
            candidates = list(packets(args.stock_directory / f'{obs}.kiss'))
            elapsed = next(line.split()[1] for line in
                           (args.stock_directory / f'{obs}.log').read_text().splitlines()
                           if line.startswith('real '))
            matched = [hashlib.sha256(payload).hexdigest() for payload in candidates
                       if payload in reference]
            writer.writerow([obs, len(candidates), len(matched), elapsed, ' '.join(matched)])


if __name__ == '__main__':
    main()
