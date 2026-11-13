#!/usr/bin/env python3
"""Reference-assisted bit-error diagnosis; never use as benchmark performance."""
import binascii,csv,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve,correlate
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bank',root/'replay-rsp03-clock-bank.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
path=root/'replays/rsp03/iq_12511021.raw'
with path.open('rb') as f:
    if hashlib.sha256(f.read()).hexdigest()!=b.d.CHECKSUMS['12511021']:raise ValueError('checksum')
frame=(root/'replays/rsp03/references/data_12511021_2025-10-06T09-09-37_1').read_bytes()
crc=binascii.crc_hqx(frame.translate(b.d.BIT_REVERSE),0xffff)
crc=((b.d.BIT_REVERSE[crc&255]<<8)|b.d.BIT_REVERSE[crc>>8])^0xffff
rawbits=np.unpackbits(np.frombuffer(frame+crc.to_bytes(2,'little'),dtype=np.uint8),bitorder='little')
expected=[];ones=0
for bit in rawbits:
    expected.append(int(bit));ones=ones+1 if bit else 0
    if ones==5:expected.append(0);ones=0
assert b.d.decode_frame(expected)==frame
expected=np.asarray(expected,dtype=np.int8);template=expected.astype(float)*2-1
raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
start=96.32;x=raw[round(start*b.d.RATE):round(97.34*b.d.RATE)].astype(np.float32)
iq=(x[:,0]+1j*x[:,1])/32767
rows=[];began=time.perf_counter()
for shift in (-100,-75,-50,-25,0,25,50,75,100):
    z=fftconvolve(iq*np.exp(2j*np.pi*shift*np.arange(len(iq))/b.d.RATE),b.d.FILTER,mode='same')
    y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
    best=None
    for ppm in range(-400,201,50):
        for phase in np.arange(0,6,.25):
            pos=np.arange(phase,len(y)-1,6*(1+ppm*1e-6))
            levels=np.interp(pos,np.arange(len(y)),y)>0
            nrzi=levels[1:]==levels[:-1]
            bits=nrzi[17:]^nrzi[5:-12]^nrzi[:-17]
            scores=correlate(bits.astype(float)*2-1,template,mode='valid',method='fft')
            left=int(np.argmax(scores));errors=int(round((len(template)-scores[left])/2))
            if best is None or errors<best['bit_errors']:
                mismatch=np.flatnonzero(bits[left:left+len(expected)]!=expected).tolist()
                best=dict(shift_hz=shift,spacing_ppm=ppm,phase_samples=float(phase),payload_start_seconds=start+pos[left+18]/b.d.RATE,bit_errors=errors,stuffed_bits=len(expected),mismatch_bit_indices=mismatch)
    rows.append(best)
report=dict(limitation='Reference-assisted minimum-error search. Alignment and parameters use known payload. Not blind decoding or a tracking estimate.',processing_seconds=time.perf_counter()-began,results=rows)
(root/'results/rsp03-miss-bit-errors.json').write_text(json.dumps(report,indent=2)+'\n')
for row in rows:print({k:v for k,v in row.items() if k!='mismatch_bit_indices'})
