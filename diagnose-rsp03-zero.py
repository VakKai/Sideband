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
rows=[];hits=[];began=time.perf_counter()
for shift in (-200,-100,-50,-25,0,25,50,100,200):
    z=fftconvolve(iq*np.exp(2j*np.pi*shift*np.arange(len(iq))/b.d.RATE),b.d.FILTER,mode='same')
    y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
    best={}
    for ppm in range(-1000,1001,100):
        for phase in np.arange(0,6,.25):
            pos=np.arange(phase,len(y)-1,6*(1+ppm*1e-6))
            levels=np.interp(pos,np.arange(len(y)),y)>0
            nrzi=levels[1:]==levels[:-1];bits=nrzi[17:]^nrzi[5:-12]^nrzi[:-17]
            for name,frame,template in templates:
                scores=correlate(bits.astype(float)*2-1,template,mode='valid',method='fft')
                left=int(np.argmax(scores));errors=int(round((len(template)-scores[left])/2))
                if name not in best or errors<best[name]['bit_errors']:
                    best[name]=dict(reference=name,bytes=len(frame),shift_hz=shift,spacing_ppm=ppm,phase_samples=float(phase),payload_start_seconds=start+pos[left+18]/b.d.RATE,bit_errors=errors,stuffed_bits=len(template))
            for t,payload in b.decode(y,ppm,phase):
                hits.append(dict(shift_hz=shift,spacing_ppm=ppm,phase_samples=float(phase),seconds=start+t,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),station_match=any(payload==frame for _,frame,_ in templates)))
    rows.extend(best.values())
    print(shift,{r['bytes']:r['bit_errors'] for r in best.values()},flush=True)
report=dict(observation=obs,window=[start,stop],processing_seconds=time.perf_counter()-began,results=rows,crc_valid_hypotheses=hits,limitation='Targeted/reference-assisted search on first detected burst. Not benchmark performance; does not establish physical clock/frequency error.')
(root/'results/rsp03-zero-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
print('CRC-valid hypotheses',len(hits),flush=True)
