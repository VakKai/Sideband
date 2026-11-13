"""Download checksum-pinned held-out I/Q captures to Sideband's replay directory."""
import csv
import hashlib
from pathlib import Path
import shutil
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    target = ROOT / 'replays/rsp03'
    target.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'results/rsp03-final-manifest.csv').open() as stream:
        for row in csv.DictReader(stream):
            path = target / f"iq_{row['observation']}.raw"
            expected = row['iq_sha256']
            if path.exists():
                if checksum(path) != expected:
                    raise ValueError(f'Existing file has the wrong checksum: {path}')
                continue
            partial = path.with_suffix('.part')
            with urlopen(row['iq_url'], timeout=60) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output)
            if checksum(partial) != expected:
                raise ValueError(f'Download has the wrong checksum: {partial}')
            partial.replace(path)
            print(path.name, flush=True)


if __name__ == '__main__':
    main()
