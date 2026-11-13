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

report=json.loads((root/'results/rsp03-zero-diagnosis.json').read_text())
z=fftconvolve(iq,b.d.FILTER,mode='same')
y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
rows=[]
for r in report['results']:
    if r['shift_hz']!=0:continue
    template=next(t for name,_,t in templates if name==r['reference'])
    pos=np.arange(r['phase_samples'],len(y)-1,6*(1+r['spacing_ppm']*1e-6))
    levels=np.interp(pos,np.arange(len(y)),y)>0
    nrzi=levels[1:]==levels[:-1];bits=nrzi[17:]^nrzi[5:-12]^nrzi[:-17]
    scores=correlate(bits.astype(float)*2-1,template,mode='valid',method='fft');left=int(np.argmax(scores))
    indices=np.flatnonzero(bits[left:left+len(template)]!=(template>0)).tolist()
    r['mismatch_bit_indices']=indices
    rows.append(r)
    print(r['bytes'],indices)
(root/'results/rsp03-zero-error-locations.json').write_text(json.dumps(rows,indent=2)+'\n')
