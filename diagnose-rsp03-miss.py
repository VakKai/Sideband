#!/usr/bin/env python3
"""Targeted DEVELOPMENT search around the last October miss; not benchmark data.
Window selected from the detector and known neighbouring reference recoveries.
"""
import csv,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve,firwin
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bank',root/'replay-rsp03-clock-bank.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
obs='12511021';start=96.32;stop=97.34
path=root/'replays/rsp03'/f'iq_{obs}.raw'
with path.open('rb') as f:
    if hashlib.sha256(f.read()).hexdigest()!=b.d.CHECKSUMS[obs]:raise ValueError('checksum')
raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
x=raw[round(start*b.d.RATE):round(stop*b.d.RATE)].astype(np.float32)
iq=(x[:,0]+1j*x[:,1])/32767
refs=b.d.station_frames(obs,root/'replays/rsp03/references')
target='dba6a7c96660f16e458891120c1101480801f7020d12c420064faf90edc1921c'
rows=[];began=time.perf_counter()
for cutoff in (3500,4000,4500,5000,5500,6000,6500,7000):
    z=fftconvolve(iq,firwin(65,cutoff,fs=b.d.RATE),mode='same')
    y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
    for ppm in range(-400,201,50):
        for phase in np.arange(0,6,.25):
            for t,f in b.decode(y,ppm,phase):
                digest=hashlib.sha256(f).hexdigest()
                rows.append([cutoff,ppm,phase,start+t,len(f),digest,f in refs,digest==target])
with (root/'results/rsp03-miss-filter-timing.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['filter_cutoff_hz','spacing_ppm','phase_samples','seconds','bytes','sha256','station_match','target']);w.writerows(rows)
summary=dict(observation=obs,window=[start,stop],processing_seconds=time.perf_counter()-began,target_recovered=any(r[-1] for r in rows),target_hypotheses=[r[:4] for r in rows if r[-1]],unique_payloads=sorted({r[5] for r in rows}),limitation='Targeted development parameter search; no frequency correction; not benchmark performance.')
(root/'results/rsp03-miss-filter-timing.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
