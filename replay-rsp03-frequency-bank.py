#!/usr/bin/env python3
"""Reference-free CRC-selected frequency/timing search; development-tuned grid.
Loads station references only AFTER decoding. Includes an identical zero-shift arm.
"""
import argparse,csv,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
spec=importlib.util.spec_from_file_location('bank',Path(__file__).with_name('replay-rsp03-clock-bank.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
SHIFTS=(-50,-25,0,25,50)
RATES=(-200,-100,0)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    p.add_argument('--observation',choices=list(b.d.CHECKSUMS),required=True)
    a=p.parse_args();root=a.root;obs=a.observation
    path=root/'replays/rsp03'/f'iq_{obs}.raw'
    with path.open('rb') as f:
        if hashlib.sha256(f.read()).hexdigest()!=b.d.CHECKSUMS[obs]:raise ValueError('checksum')
    raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
    bursts=list(csv.DictReader((root/'results'/f'rsp03-tracking-{obs}-bursts.csv').open()))
    found={shift:[] for shift in SHIFTS};elapsed={};hits=[]
    for shift in SHIFTS:
        began=time.perf_counter()
        for burst in bursts:
            begin=round(float(burst['start_seconds'])*b.d.RATE);end=round(float(burst['stop_seconds'])*b.d.RATE)
            for start in range(begin,end,b.d.RATE//2):
                x=raw[start:min(start+b.d.RATE,end)].astype(np.float32)
                if len(x)<100:continue
                iq=(x[:,0]+1j*x[:,1])/32767
                # Same arithmetic path even for zero; phase continuous relative
                # to the segment origin across overlapping windows.
                iq=iq*np.exp(2j*np.pi*shift*(np.arange(len(iq))+start-begin)/b.d.RATE)
                z=fftconvolve(iq,b.d.FILTER,mode='same')
                y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
                for ppm in RATES:
                    for phase in np.arange(0,6,.25):
                        for t,payload in b.decode(y,ppm,phase):
                            absolute=start/b.d.RATE+t
                            hits.append((shift,ppm,float(phase),absolute,payload))
                            if not any(payload==old and abs(absolute-ot)<.002 for ot,old in found[shift]):
                                found[shift].append((absolute,payload))
        elapsed[shift]=time.perf_counter()-began
        print(obs,shift,'Hz',len(found[shift]),'CRC-valid occurrences',flush=True)
    # References cannot affect candidate discovery or parameter selection here.
    refs=b.d.station_frames(obs,root/'replays/rsp03/references')
    union=[]
    for shift in SHIFTS:
        for t,payload in found[shift]:
            if not any(payload==old and abs(t-ot)<.002 for ot,old in union):union.append((t,payload))
    prefix=root/'results'/f'rsp03-frequency-bank-{obs}'
    with prefix.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['shift_hz','spacing_ppm','phase_samples','seconds','bytes','sha256','station_match'])
        w.writerows([shift,ppm,phase,t,len(payload),hashlib.sha256(payload).hexdigest(),payload in refs] for shift,ppm,phase,t,payload in hits)
    with Path(str(prefix)+'-occurrences.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['seconds','bytes','sha256','station_match','recovered_at_zero'])
        for t,payload in sorted(union):
            at_zero=any(payload==old and abs(t-ot)<.002 for ot,old in found[0])
            w.writerow([t,len(payload),hashlib.sha256(payload).hexdigest(),payload in refs,at_zero])
    summary=dict(observation=obs,shift_hz=SHIFTS,spacing_ppm=RATES,phase_step_samples=.25,per_shift=[dict(shift_hz=s,crc_valid_occurrences=len(found[s]),station_matches=sum(f in refs for _,f in found[s]),processing_seconds=elapsed[s]) for s in SHIFTS],union_occurrences=len(union),union_station_matches=sum(f in refs for _,f in union),zero_shift_occurrences=len(found[0]),processing_seconds=sum(elapsed.values()),limitation='CRC-only search at inference, but grid tuned on October development data. Not an independently estimated frequency tracker or held-out benchmark. Timings exclude detector and reference loading.')
    prefix.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
