#!/usr/bin/env python3
"""Development diagnostic: fractional phase / symbol-rate bank, no frequency correction.
CRC selects valid packets. Station payloads only label results. Not an online clock loop.
"""
import argparse,csv,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
spec=importlib.util.spec_from_file_location('d',Path(__file__).with_name('replay-rsp03.py'))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
PPM=(-1000,-500,-200,-100,0,100,200,500,1000)

def decode(y,ppm,phase):
    # ppm refers to sample spacing; positive means a slower recovered symbol clock.
    positions=np.arange(phase,len(y)-1,6*(1+ppm*1e-6))
    levels=np.interp(positions,np.arange(len(y)),y)>0
    nrzi=levels[1:]==levels[:-1]
    bits=nrzi[17:] ^ nrzi[5:-12] ^ nrzi[:-17]
    flags=np.flatnonzero(np.convolve(bits.astype(np.int8),[-1,1,1,1,1,1,1,-1],mode='valid')==6)
    result=[]
    for left,right in zip(flags,flags[1:]):
        if right-left>2500:continue
        f=d.decode_frame(bits[left+8:right])
        if f is not None:result.append((positions[left+18]/d.RATE,f))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('--observation',choices=list(d.CHECKSUMS),required=True)
    p.add_argument('--profile',choices=['wide','compact'],default='wide')
    p.add_argument('--correction',choices=['none','burst-median'],default='none')
    a=p.parse_args();obs=a.observation;root=a.root
    rates=PPM if a.profile=='wide' else (-200,-100,0)
    frequency=None
    if a.correction=='burst-median':
        frequency=list(csv.DictReader((root/'results'/f'rsp03-tracking-{obs}-frequency.csv').open()))
    path=root/'replays/rsp03'/f'iq_{obs}.raw'
    with path.open('rb') as f:
        if hashlib.sha256(f.read()).hexdigest()!=d.CHECKSUMS[obs]:raise ValueError('checksum')
    refs=d.station_frames(obs,root/'replays/rsp03/references')
    raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
    bursts=list(csv.DictReader((root/'results'/f'rsp03-tracking-{obs}-bursts.csv').open()))
    hits=[];occurrences=[];started=time.perf_counter();windows=0
    for b in bursts:
        begin=round(float(b['start_seconds'])*d.RATE);end=round(float(b['stop_seconds'])*d.RATE)
        # Signal-only median over active spectral blocks, fixed for this segment.
        hz=0.
        if frequency is not None:
            first=round(begin/1152);last=round(end/1152)
            active=[float(r['raw_centroid_hz']) for r in frequency[first:last] if float(r['power_ratio'])>10**(.2)]
            hz=float(np.median(active)) if active else 0.
        # 0.5-second overlap exceeds max supported packet duration.
        for start in range(begin,end,d.RATE//2):
            x=raw[start:min(start+d.RATE,end)].astype(np.float32)
            if len(x)<100:continue
            windows+=1
            iq=(x[:,0]+1j*x[:,1])/32767
            if hz:
                iq=iq*np.exp(-2j*np.pi*hz*(np.arange(len(iq))+start-begin)/d.RATE).astype(np.complex64)
            z=fftconvolve(iq,d.FILTER,mode='same')
            y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
            for ppm in rates:
                for phase in np.arange(0,6,.5):
                    for relative,f in decode(y,ppm,phase):
                        t=start/d.RATE+relative;digest=hashlib.sha256(f).hexdigest()
                        hits.append([obs,t,len(f),digest,f in refs,ppm,phase,start/d.RATE])
                        if not any(f==prev and abs(t-old)<.002 for old,prev in occurrences):occurrences.append((t,f))
    elapsed=time.perf_counter()-started
    suffix='' if a.profile=='wide' and a.correction=='none' else f'-{a.profile}-{a.correction}'
    prefix=root/'results'/f'rsp03-clock-bank-{obs}{suffix}'
    with prefix.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['observation','seconds','bytes','sha256','station_match','spacing_ppm','phase_samples','window_start']);w.writerows(hits)
    with Path(str(prefix)+'-occurrences.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['observation','seconds','bytes','sha256','station_match'])
        w.writerows([obs,t,len(payload),hashlib.sha256(payload).hexdigest(),payload in refs] for t,payload in sorted(occurrences))
    summary=dict(profile=a.profile, correction=a.correction, observation=obs,windows=windows,processing_seconds=elapsed,crc_valid_occurrences=len(occurrences),station_matched_occurrences=sum(f in refs for _,f in occurrences),spacing_ppm=rates,phase_step_samples=.5,limitation='Offline bank search on automatically detected segments; not online timing recovery. Correction, if selected, is constant per detected burst.')
    prefix.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
