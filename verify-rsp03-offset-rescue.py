#!/usr/bin/env python3
"""Controlled CRC-decoder verification of a reference-discovered offset hypothesis.
Settings were selected on this development burst. Not a blind tracker benchmark.
"""
import csv,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bank',root/'replay-rsp03-clock-bank.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
path=root/'replays/rsp03/iq_12511021.raw'
with path.open('rb') as f:
    if hashlib.sha256(f.read()).hexdigest()!=b.d.CHECKSUMS['12511021']:raise ValueError('checksum')
raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
start=96.32;x=raw[round(start*b.d.RATE):round(97.34*b.d.RATE)].astype(np.float32)
iq=(x[:,0]+1j*x[:,1])/32767
refs=b.d.station_frames('12511021',root/'replays/rsp03/references')
rows=[]
for shift in (0,25):
    z=fftconvolve(iq*np.exp(2j*np.pi*shift*np.arange(len(iq))/b.d.RATE),b.d.FILTER,mode='same')
    y=np.convolve(np.angle(z[1:]*z[:-1].conj()),[.5,.5],mode='same')
    frames=b.decode(y,-100,4.25) # identical downstream settings in both arms
    rows.append(dict(shift_hz=shift,spacing_ppm=-100,phase_samples=4.25,frames=[dict(seconds=start+t,bytes=len(f),sha256=hashlib.sha256(f).hexdigest(),station_match=f in refs) for t,f in frames]))
target='dba6a7c96660f16e458891120c1101480801f7020d12c420064faf90edc1921c'
assert not any(f['sha256']==target for f in rows[0]['frames'])
assert any(f['sha256']==target and f['station_match'] for f in rows[1]['frames'])
result=dict(limitation='Targeted development rescue; frequency/timing settings selected using known reference. Offset not independently estimated. No held-out performance claim.',results=rows)
(root/'results/rsp03-offset-rescue.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
