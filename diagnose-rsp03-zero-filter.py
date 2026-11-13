#!/usr/bin/env python3
"""Reference-assisted investigation of 12511720; excluded from benchmark counts."""
import binascii,csv,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve,correlate
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bank',root/'replay-rsp03-clock-bank.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
obs='12511720';start=98.62;stop=99.64
path=root/'replays/rsp03'/f'iq_{obs}.raw'
with path.open('rb') as f:
    if hashlib.sha256(f.read()).hexdigest()!=b.d.CHECKSUMS[obs]:raise ValueError('checksum')
templates=[]
for p in sorted((root/'replays/rsp03/references').glob(f'data_{obs}_*')):
    frame=p.read_bytes();crc=binascii.crc_hqx(frame.translate(b.d.BIT_REVERSE),0xffff)
    crc=((b.d.BIT_REVERSE[crc&255]<<8)|b.d.BIT_REVERSE[crc>>8])^0xffff
    rawbits=np.unpackbits(np.frombuffer(frame+crc.to_bytes(2,'little'),dtype=np.uint8),bitorder='little')
    expected=[];ones=0
    for bit in rawbits:
        expected.append(int(bit));ones=ones+1 if bit else 0
        if ones==5:expected.append(0);ones=0
    assert b.d.decode_frame(expected)==frame
    templates.append((p.name,frame,np.asarray(expected,dtype=float)*2-1))
raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
x=raw[round(start*b.d.RATE):round(stop*b.d.RATE)].astype(np.float32)
iq=(x[:,0]+1j*x[:,1])/32767

from scipy.signal import firwin
hits=[];began=time.perf_counter()
for cutoff in (3500,4000,4500,5000,5500,6000,6500,7000):
    z=fftconvolve(iq,firwin(65,cutoff,fs=b.d.RATE),mode='same')
    discriminator=np.angle(z[1:]*z[:-1].conj())
    for smoothing in (1,2,3):
        y=np.convolve(discriminator,np.ones(smoothing)/smoothing,mode='same')
        for ppm in range(-400,201,50):
            for phase in np.arange(0,6,.25):
                for t,payload in b.decode(y,ppm,phase):
                    hits.append(dict(cutoff_hz=cutoff,smoothing_samples=smoothing,spacing_ppm=ppm,phase_samples=float(phase),seconds=start+t,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),station_match=any(payload==frame for _,frame,_ in templates)))
report=dict(observation=obs,window=[start,stop],shift_hz=0,processing_seconds=time.perf_counter()-began,hits=hits,limitation='Targeted development filter/smoothing/timing search; not benchmark performance.')
(root/'results/rsp03-zero-filter-search.json').write_text(json.dumps(report,indent=2)+'\n')
print('Successful hypotheses:',len(hits))
for digest in sorted({h['sha256'] for h in hits}):
    subset=[h for h in hits if h['sha256']==digest]
    print(subset[0], 'filter/smoothing pairs', sorted({(h['cutoff_hz'],h['smoothing_samples']) for h in subset}))
