"""Compare the zero-shift arm with CRC-selected union, preserving per-pass grouping."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'results'
observations=['12511021','12511022','12511719','12511720','13415454','13415455']
manifest=json.loads((out/'rsp03-split-v1.json').read_text())
pass_of={obs:p['pass_start_utc'] for p in manifest['passes'] for obs in p['observations']}
rows=[];pass_packets={}
for obs in observations:
    s=json.loads((out/f'rsp03-frequency-bank-{obs}.json').read_text())
    packets=list(csv.DictReader((out/f'rsp03-frequency-bank-{obs}-occurrences.csv').open()))
    zero=next(v for v in s['per_shift'] if v['shift_hz']==0)
    new=[r for r in packets if r['recovered_at_zero']=='False' and r['station_match']=='True']
    rows.append([obs,zero['station_matches'],s['union_station_matches'],len(new),sum(r['station_match']!='True' for r in packets),zero['processing_seconds'],s['processing_seconds']])
    group=pass_of[obs]
    items=pass_packets.setdefault(group,[])
    for r in packets:
        if r['station_match']!='True':continue
        t=float(r['seconds'])
        if not any(r['sha256']==old['sha256'] and abs(t-float(old['seconds']))<.002 for old in items):items.append(r)
with (out/'rsp03-frequency-bank-comparison.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['observation','zero_shift_matches','frequency_bank_matches','new_verified_occurrences','unmatched_crc_occurrences','zero_shift_seconds','frequency_bank_seconds']);w.writerows(rows)
print(json.dumps({'recordings':rows,'per_pass_verified_union_counts':{p:len(items) for p,items in pass_packets.items()},'deduplication':'same payload within 2 ms; assumes the already-established shared capture alignment within each pass'},indent=2))
