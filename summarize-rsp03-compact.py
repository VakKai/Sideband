"""Summarize compact timing experiment and compare occurrence identities."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'results'
rows=[]
for obs in ['12511021','12511022','13415454','13415455']:
    def read(mode):
        prefix=out/f'rsp03-clock-bank-{obs}-compact-{mode}'
        return json.loads(prefix.with_suffix('.json').read_text()),list(csv.DictReader(Path(str(prefix)+'-occurrences.csv').open()))
    raw,r=read('none');corr,c=read('burst-median')
    def exists(packet,items):
        return any(packet['sha256']==v['sha256'] and abs(float(packet['seconds'])-float(v['seconds']))<.002 for v in items)
    rows.append([obs,raw['station_matched_occurrences'],corr['station_matched_occurrences'],sum(not exists(v,r) for v in c),sum(not exists(v,c) for v in r),raw['processing_seconds'],corr['processing_seconds']])
with (out/'rsp03-compact-comparison.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['observation','uncorrected_matches','corrected_matches','new_corrected_occurrences','lost_occurrences','uncorrected_processing_seconds','corrected_processing_seconds']);w.writerows(rows)
for row in rows:print(row)
